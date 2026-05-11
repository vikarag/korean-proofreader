from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DetectionResult:
	is_korean: bool
	korean_ratio: float
	total_chars: int
	korean_chars: int


def _count_korean_chars(text: str) -> int:
	count = 0
	for ch in text:
		cp = ord(ch)
		if (
			(0xAC00 <= cp <= 0xD7AF)
			or (0x1100 <= cp <= 0x11FF)
			or (0x3130 <= cp <= 0x318F)
			or (0xA960 <= cp <= 0xA97F)
			or (0xD7B0 <= cp <= 0xD7FF)
		):
			count += 1
	return count


def detect_korean(
	text: str,
	threshold: float = 0.10,
	min_korean_chars: int = 10,
) -> DetectionResult:
	total = len(text)
	if total == 0:
		return DetectionResult(
			is_korean=False,
			korean_ratio=0.0,
			total_chars=0,
			korean_chars=0,
		)

	korean_chars = _count_korean_chars(text)
	ratio = korean_chars / total

	is_korean = korean_chars >= min_korean_chars and ratio >= threshold

	return DetectionResult(
		is_korean=is_korean,
		korean_ratio=round(ratio, 4),
		total_chars=total,
		korean_chars=korean_chars,
	)
