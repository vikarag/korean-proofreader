from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path


class CorrectionLogger:
	def __init__(self, log_path: str = "logs/corrections.jsonl"):
		self.log_path = Path(log_path)
		self.log_path.parent.mkdir(parents=True, exist_ok=True)
		self._logger = logging.getLogger("corrections")

	def log_correction(
		self,
		segment_index: int,
		original: str,
		corrected: str,
		error_type: str,
		provider: str,
		latency_ms: int,
	) -> None:
		entry = {
			"timestamp": datetime.now(timezone.utc).isoformat(),
			"segment_index": segment_index,
			"original": original,
			"corrected": corrected,
			"error_type": error_type,
			"provider": provider,
			"latency_ms": latency_ms,
		}
		with open(self.log_path, "a", encoding="utf-8") as f:
			f.write(json.dumps(entry, ensure_ascii=False) + "\n")

	def log_request(
		self,
		provider: str,
		tone: str,
		mode: str,
		korean_ratio: float,
		segments_proofread: int,
		segments_skipped: int,
		total_latency_ms: int,
		was_modified: bool,
	) -> None:
		entry = {
			"timestamp": datetime.now(timezone.utc).isoformat(),
			"event": "request",
			"provider": provider,
			"tone": tone,
			"mode": mode,
			"korean_ratio": korean_ratio,
			"segments_proofread": segments_proofread,
			"segments_skipped": segments_skipped,
			"total_latency_ms": total_latency_ms,
			"was_modified": was_modified,
		}
		with open(self.log_path, "a", encoding="utf-8") as f:
			f.write(json.dumps(entry, ensure_ascii=False) + "\n")

	def get_error_counts(self) -> dict[str, int]:
		counts: dict[str, int] = {}
		if not self.log_path.exists():
			return counts
		with open(self.log_path, "r", encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if not line:
					continue
				try:
					entry = json.loads(line)
					error_type = entry.get("error_type")
					if error_type and error_type != "none":
						counts[error_type] = counts.get(error_type, 0) + 1
				except json.JSONDecodeError:
					continue
		return counts

	def get_total_corrections(self) -> int:
		if not self.log_path.exists():
			return 0
		count = 0
		with open(self.log_path, "r", encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if not line:
					continue
				try:
					entry = json.loads(line)
					if entry.get("error_type") and entry.get("error_type") != "none":
						count += 1
				except json.JSONDecodeError:
					continue
		return count
