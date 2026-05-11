from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DiffItem:
	original: str
	corrected: str
	error_type: str
	segment_index: int


_ERROR_KEYWORDS: dict[str, list[str]] = {
	"조사 오류": ["은 ", "는 ", "이 ", "가 ", "을 ", "를 "],
	"직역체": ["진행합니다", "실시합니다", "해당합니다", "입수합니다"],
	"어순 간섭": [],
	"띄어쓰기": [],
	"어미 부자연스러움": ["것입니다"],
	"한자어 과다 사용": ["확인을 실시", "조사를 실시"],
	"존댓말 혼용": [],
}


def classify_error(original: str, corrected: str) -> str:
	if original == corrected:
		return "none"

	for error_type, keywords in _ERROR_KEYWORDS.items():
		for kw in keywords:
			if kw in original and kw not in corrected:
				return error_type

	if original.replace(" ", "") == corrected.replace(" ", ""):
		return "띄어쓰기"

	return "general"


def generate_diffs(
	original_segments: list[tuple[int, str]],
	corrections: dict[int, str],
) -> list[DiffItem]:
	items: list[DiffItem] = []
	for idx, original in original_segments:
		if idx not in corrections:
			continue
		corrected = corrections[idx]
		if original.strip() == corrected.strip():
			continue
		error_type = classify_error(original, corrected)
		items.append(
			DiffItem(
				original=original,
				corrected=corrected,
				error_type=error_type,
				segment_index=idx,
			)
		)
	return items
