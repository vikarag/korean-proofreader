from __future__ import annotations

from .segmenter import Segment, SegmentType

_MARKDOWN_HEADING_RE = __import__("re").compile(r"^(#{1,6}\s+)")
_MARKDOWN_LIST_RE = __import__("re").compile(r"^(\s*[-*+]\s+|\s*\d+\.\s+)")


def _strip_heading_prefix(text: str) -> tuple[str, str]:
	import re

	m = re.match(r"^(#{1,6}\s+)", text)
	if m:
		return m.group(1), text[m.end() :]
	return "", text


def _strip_list_prefix(text: str) -> tuple[str, str]:
	import re

	m = re.match(r"^(\s*[-*+\d.]+\s+)", text)
	if m:
		return m.group(1), text[m.end() :]
	return "", text


def reassemble(
	segments: list[Segment],
	corrections: dict[int, str],
) -> str:
	parts: list[str] = []

	for seg in segments:
		if seg.index in corrections and seg.proofread:
			corrected = corrections[seg.index]

			if seg.segment_type == SegmentType.MARKDOWN_HEADING:
				prefix, _ = _strip_heading_prefix(seg.text)
				parts.append(f"{prefix}{corrected}")
			elif seg.segment_type == SegmentType.MARKDOWN_LIST_ITEM:
				prefix, _ = _strip_list_prefix(seg.text)
				parts.append(f"{prefix}{corrected}")
			else:
				parts.append(corrected)
		else:
			parts.append(seg.text)

	return "".join(parts)
