from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from pathlib import Path

import httpx

from models.request import ProofreadProvider, ProofreadTone
from .segmenter import Segment

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt_template(name: str) -> str:
	path = PROMPTS_DIR / name
	return path.read_text(encoding="utf-8")


def _load_error_examples() -> str:
	return _load_prompt_template("error_examples.txt")


def _build_system_prompt(tone: ProofreadTone) -> str:
	template_name = (
		"system_casual.txt" if tone == ProofreadTone.CASUAL else "system_formal.txt"
	)
	template = _load_prompt_template(template_name)
	return template.replace("{error_examples}", _load_error_examples())


def _build_user_prompt(segments: list[Segment], context: str = "") -> str:
	parts: list[str] = []
	if context:
		parts.append(f"## Original User Context\n{context}\n")
	parts.append("## Korean Segments to Proofread\n")
	for seg in segments:
		parts.append(f"[SEGMENT {seg.index}]\n{seg.text}\n[/SEGMENT {seg.index}]")
	parts.append(
		"\nReturn each corrected segment wrapped in the same [SEGMENT N] markers."
	)
	return "\n".join(parts)


def _parse_proofread_response(
	response_text: str, original_segments: list[Segment]
) -> dict[int, str]:
	import re

	pattern = re.compile(
		r"\[SEGMENT\s+(\d+)\]\s*\n(.*?)\n\s*\[/SEGMENT\s+\1\]",
		re.DOTALL,
	)
	corrections: dict[int, str] = {}
	for m in pattern.finditer(response_text):
		idx = int(m.group(1))
		text = m.group(2).strip()
		corrections[idx] = text

	if not corrections:
		lines = response_text.strip().split("\n\n")
		for i, seg in enumerate(original_segments):
			if i < len(lines):
				corrections[seg.index] = lines[i].strip()

	return corrections


async def _call_gemini(
	system_prompt: str,
	user_prompt: str,
	api_key: str,
	model: str,
	base_url: str,
) -> str:
	url = f"{base_url}/models/{model}:generateContent?key={api_key}"
	payload = {
		"contents": [{"parts": [{"text": user_prompt}]}],
		"systemInstruction": {"parts": [{"text": system_prompt}]},
		"generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
	}
	async with httpx.AsyncClient(timeout=60.0) as client:
		resp = await client.post(url, json=payload)
		resp.raise_for_status()
		data = resp.json()
		return data["candidates"][0]["content"]["parts"][0]["text"]


async def _call_openai(
	system_prompt: str,
	user_prompt: str,
	api_key: str,
	model: str,
	base_url: str,
) -> str:
	url = f"{base_url}/chat/completions"
	headers = {"Authorization": f"Bearer {api_key}"}
	payload = {
		"model": model,
		"messages": [
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": user_prompt},
		],
		"temperature": 0.2,
		"max_tokens": 8192,
	}
	async with httpx.AsyncClient(timeout=60.0) as client:
		resp = await client.post(url, json=payload, headers=headers)
		resp.raise_for_status()
		data = resp.json()
		return data["choices"][0]["message"]["content"]


async def proofread_segments(
	segments: list[Segment],
	provider: ProofreadProvider,
	tone: ProofreadTone,
	api_keys: dict[str, str],
	models: dict[str, str],
	base_urls: dict[str, str],
	context: str = "",
) -> dict[int, str]:
	proofreadable = [s for s in segments if s.proofread]
	if not proofreadable:
		return {}

	system_prompt = _build_system_prompt(tone)
	user_prompt = _build_user_prompt(proofreadable, context)

	provider_key = provider.value
	api_key = api_keys.get(provider_key, "")
	model = models.get(provider_key, "")
	base_url = base_urls.get(provider_key, "")

	if not api_key:
		raise ValueError(f"API key for provider '{provider_key}' not configured")

	try:
		if provider == ProofreadProvider.GEMINI:
			raw_response = await _call_gemini(
				system_prompt, user_prompt, api_key, model, base_url
			)
		else:
			raw_response = await _call_openai(
				system_prompt, user_prompt, api_key, model, base_url
			)
	except httpx.HTTPStatusError as e:
		logger.error("LLM API error (%s): %s", provider_key, e.response.status_code)
		raise
	except Exception:
		logger.exception("LLM call failed for provider %s", provider_key)
		raise

	corrections = _parse_proofread_response(raw_response, proofreadable)
	return corrections
