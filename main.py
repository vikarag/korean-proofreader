from __future__ import annotations

import logging
import time
from pathlib import Path
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, HTTPException

from models.request import ProofreadRequest, ProofreadMode
from models.response import ProofreadResponse, DiffItem
from core.detector import detect_korean
from core.segmenter import segment
from core.proofreader import proofread_segments
from core.reassembler import reassemble
from core.cache import Cache
from utils.diff import classify_error, generate_diffs
from utils.logging import CorrectionLogger

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
	with open(CONFIG_PATH, "r", encoding="utf-8") as f:
		return yaml.safe_load(f) or {}


config: dict = {}
cache: Cache | None = None
correction_logger: CorrectionLogger | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
	global config, cache, correction_logger
	config = load_config()

	cache_cfg = config.get("cache", {})
	cache = Cache(
		db_path=cache_cfg.get("db_path", "cache.db"),
		ttl_hours=cache_cfg.get("ttl_hours", 24),
		enabled=cache_cfg.get("enabled", True),
	)

	log_cfg = config.get("logging", {})
	correction_logger = CorrectionLogger(
		log_path=log_cfg.get("corrections_file", "logs/corrections.jsonl"),
	)

	logger.info("Korean Proofreading Server started")
	yield
	logger.info("Korean Proofreading Server shutting down")


app = FastAPI(
	title="Korean Output Proofreading Proxy",
	description="Corrects Korean output from Chinese LLMs",
	version="1.0.0",
	lifespan=lifespan,
)


def _get_api_keys() -> dict[str, str]:
	providers = config.get("providers", {})
	return {
		"gemini": providers.get("gemini", {}).get("api_key", ""),
		"openai": providers.get("openai", {}).get("api_key", ""),
	}


def _get_models() -> dict[str, str]:
	providers = config.get("providers", {})
	return {
		"gemini": providers.get("gemini", {}).get("model", "gemini-2.5-flash"),
		"openai": providers.get("openai", {}).get("model", "gpt-4o-mini"),
	}


def _get_base_urls() -> dict[str, str]:
	providers = config.get("providers", {})
	return {
		"gemini": providers.get("gemini", {}).get(
			"base_url", "https://generativelanguage.googleapis.com/v1beta"
		),
		"openai": providers.get("openai", {}).get(
			"base_url", "https://api.openai.com/v1"
		),
	}


@app.post("/proofread", response_model=ProofreadResponse)
async def proofread(req: ProofreadRequest):
	start_time = time.monotonic()

	detector_cfg = config.get("detector", {})
	threshold = detector_cfg.get("korean_ratio_threshold", 0.10)
	min_chars = detector_cfg.get("min_korean_chars", 10)

	detection = detect_korean(
		req.text, threshold=threshold, min_korean_chars=min_chars
	)

	if req.mode == ProofreadMode.AUTO and not detection.is_korean:
		elapsed = int((time.monotonic() - start_time) * 1000)
		return ProofreadResponse(
			corrected=req.text,
			was_modified=False,
			korean_ratio=detection.korean_ratio,
			segments_proofread=0,
			segments_skipped=0,
			provider_used=req.provider.value,
			latency_ms=elapsed,
			diff=None,
		)

	segments = segment(req.text)
	proofreadable = [s for s in segments if s.proofread]
	skippable = [s for s in segments if not s.proofread]

	if not proofreadable:
		elapsed = int((time.monotonic() - start_time) * 1000)
		return ProofreadResponse(
			corrected=req.text,
			was_modified=False,
			korean_ratio=detection.korean_ratio,
			segments_proofread=0,
			segments_skipped=len(skippable),
			provider_used=req.provider.value,
			latency_ms=elapsed,
			diff=None,
		)

	corrections: dict[int, str] = {}
	uncached_segments = []

	for seg in proofreadable:
		cached = cache.get(seg.text, req.tone.value, req.provider.value) if cache else None
		if cached is not None:
			corrections[seg.index] = cached
		else:
			uncached_segments.append(seg)

	if uncached_segments:
		try:
			llm_corrections = await proofread_segments(
				segments=uncached_segments,
				provider=req.provider,
				tone=req.tone,
				api_keys=_get_api_keys(),
				models=_get_models(),
				base_urls=_get_base_urls(),
				context=req.context,
			)
			corrections.update(llm_corrections)

			if cache:
				for seg in uncached_segments:
					if seg.index in corrections:
						cache.put(seg.text, corrections[seg.index], req.tone.value, req.provider.value)
		except Exception:
			logger.exception("Proofreading failed")
			raise HTTPException(status_code=502, detail="Proofreading LLM call failed")

	corrected_text = reassemble(segments, corrections)

	elapsed = int((time.monotonic() - start_time) * 1000)

	diff_items = None
	if req.return_diff:
		original_pairs = [(s.index, s.text) for s in proofreadable]
		raw_diffs = generate_diffs(original_pairs, corrections)
		diff_items = [
			DiffItem(
				original=d.original,
				corrected=d.corrected,
				error_type=d.error_type,
				segment_index=d.segment_index,
			)
			for d in raw_diffs
		]

	was_modified = corrected_text != req.text

	if correction_logger:
		correction_logger.log_request(
			provider=req.provider.value,
			tone=req.tone.value,
			mode=req.mode.value,
			korean_ratio=detection.korean_ratio,
			segments_proofread=len(proofreadable),
			segments_skipped=len(skippable),
			total_latency_ms=elapsed,
			was_modified=was_modified,
		)
		for seg in proofreadable:
			if seg.index in corrections and seg.text.strip() != corrections[seg.index].strip():
				correction_logger.log_correction(
					segment_index=seg.index,
					original=seg.text,
					corrected=corrections[seg.index],
					error_type=classify_error(seg.text, corrections[seg.index]),
					provider=req.provider.value,
					latency_ms=elapsed,
				)

	return ProofreadResponse(
		corrected=corrected_text,
		was_modified=was_modified,
		korean_ratio=detection.korean_ratio,
		segments_proofread=len(proofreadable),
		segments_skipped=len(skippable),
		provider_used=req.provider.value,
		latency_ms=elapsed,
		diff=diff_items,
	)


@app.get("/health")
async def health():
	return {"status": "ok"}


@app.get("/stats")
async def stats():
	if not correction_logger:
		return {"error_counts": {}, "total_corrections": 0}

	return {
		"error_counts": correction_logger.get_error_counts(),
		"total_corrections": correction_logger.get_total_corrections(),
	}


if __name__ == "__main__":
	import uvicorn

	cfg = config.get("server", {}) if config else {}
	host = cfg.get("host", "0.0.0.0")
	port = cfg.get("port", 8787)
	uvicorn.run("main:app", host=host, port=port, reload=True)
