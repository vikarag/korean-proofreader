from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class SegmentType(str, Enum):
	KOREAN_PROSE = "korean_prose"
	CODE_BLOCK = "code_block"
	INLINE_CODE = "inline_code"
	URL = "url"
	ENGLISH_PROSE = "english_prose"
	MARKDOWN_HEADING = "markdown_heading"
	MARKDOWN_LIST_ITEM = "markdown_list_item"
	OTHER = "other"


@dataclass
class Segment:
	index: int
	segment_type: SegmentType
	text: str
	proofread: bool = False


_CODE_BLOCK_RE = re.compile(r"(```[\s\S]*?```)", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"(`[^`\n]+`)")
_URL_RE = re.compile(
	r"(https?://[^\s\)\]\>\"']+|/[a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)"
)
_HEADING_RE = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(r"^(\s*[-*+]\s+.+)$", re.MULTILINE)
_ORDERED_LIST_RE = re.compile(r"^(\s*\d+\.\s+.+)$", re.MULTILINE)

_KOREAN_CHAR_RE = re.compile(
	r"[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F\uA960-\uA97F\uD7B0-\uD7FF]"
)


def _has_korean(text: str) -> bool:
	return bool(_KOREAN_CHAR_RE.search(text))


def _is_mostly_english(text: str) -> bool:
	alpha = sum(1 for c in text if c.isalpha() and ord(c) < 0x0400)
	total = sum(1 for c in text if c.isalpha())
	if total == 0:
		return False
	return (alpha / total) > 0.8


def _split_preserving_delimiters(text: str, pattern: re.Pattern) -> list[str]:
	parts: list[str] = []
	last = 0
	for m in pattern.finditer(text):
		if m.start() > last:
			parts.append(text[last : m.start()])
		parts.append(m.group())
		last = m.end()
	if last < len(text):
		parts.append(text[last:])
	return [p for p in parts if p]


def _classify_chunk(chunk: str) -> SegmentType:
	if _CODE_BLOCK_RE.fullmatch(chunk.strip()):
		return SegmentType.CODE_BLOCK
	if _INLINE_CODE_RE.fullmatch(chunk.strip()):
		return SegmentType.INLINE_CODE
	if _URL_RE.fullmatch(chunk.strip()):
		return SegmentType.URL

	stripped = chunk.strip()
	if re.match(r"^#{1,6}\s+", stripped):
		return SegmentType.MARKDOWN_HEADING
	if re.match(r"^(\s*[-*+]\s+|\s*\d+\.\s+)", stripped, re.MULTILINE):
		return SegmentType.MARKDOWN_LIST_ITEM

	if _has_korean(chunk):
		if _is_mostly_english(chunk):
			return SegmentType.ENGLISH_PROSE
		return SegmentType.KOREAN_PROSE

	if _is_mostly_english(chunk):
		return SegmentType.ENGLISH_PROSE

	return SegmentType.OTHER


def _should_proofread(seg_type: SegmentType) -> bool:
	return seg_type in (
		SegmentType.KOREAN_PROSE,
		SegmentType.MARKDOWN_HEADING,
		SegmentType.MARKDOWN_LIST_ITEM,
	)


def _extract_text_from_heading(line: str) -> str:
	return re.sub(r"^#{1,6}\s+", "", line)


def _extract_text_from_list_item(line: str) -> str:
	return re.sub(r"^\s*[-*+\d.]+\s+", "", line)


def segment(text: str) -> list[Segment]:
	if not text:
		return []

	chunks = _split_preserving_delimiters(text, _CODE_BLOCK_RE)

	further_chunks: list[str] = []
	for chunk in chunks:
		if _CODE_BLOCK_RE.fullmatch(chunk.strip()):
			further_chunks.append(chunk)
		else:
			further_chunks.extend(_split_preserving_delimiters(chunk, _INLINE_CODE_RE))

	url_chunks: list[str] = []
	for chunk in further_chunks:
		if (
			_CODE_BLOCK_RE.fullmatch(chunk.strip())
			or _INLINE_CODE_RE.fullmatch(chunk.strip())
		):
			url_chunks.append(chunk)
		else:
			url_chunks.extend(_split_preserving_delimiters(chunk, _URL_RE))

	segments: list[Segment] = []
	idx = 0

	for chunk in url_chunks:
		chunk_stripped = chunk.strip()
		if not chunk_stripped:
			segments.append(Segment(index=idx, segment_type=SegmentType.OTHER, text=chunk))
			idx += 1
			continue

		if _CODE_BLOCK_RE.fullmatch(chunk_stripped):
			segments.append(Segment(index=idx, segment_type=SegmentType.CODE_BLOCK, text=chunk))
			idx += 1
			continue

		if _INLINE_CODE_RE.fullmatch(chunk_stripped):
			segments.append(Segment(index=idx, segment_type=SegmentType.INLINE_CODE, text=chunk))
			idx += 1
			continue

		if _URL_RE.fullmatch(chunk_stripped):
			segments.append(Segment(index=idx, segment_type=SegmentType.URL, text=chunk))
			idx += 1
			continue

		lines = chunk.split("\n")
		last_line_idx = len(lines) - 1
		current_lines: list[str] = []
		current_type: SegmentType | None = None

		for i, line in enumerate(lines):
			is_last = i == last_line_idx
			line_stripped = line.strip()
			if not line_stripped:
				if current_lines:
					combined = "\n".join(current_lines)
					seg_type = current_type or _classify_chunk(combined)
					segments.append(
						Segment(index=idx, segment_type=seg_type, text=combined)
					)
					idx += 1
					current_lines = []
					current_type = None
				segments.append(
					Segment(index=idx, segment_type=SegmentType.OTHER, text="\n")
				)
				idx += 1
				continue

			if re.match(r"^#{1,6}\s+", line_stripped):
				if current_lines:
					combined = "\n".join(current_lines)
					seg_type = current_type or _classify_chunk(combined)
					segments.append(
						Segment(index=idx, segment_type=seg_type, text=combined)
					)
					idx += 1
					current_lines = []
					segments.append(
						Segment(index=idx, segment_type=SegmentType.OTHER, text="\n")
					)
					idx += 1
				segments.append(
					Segment(
						index=idx,
						segment_type=SegmentType.MARKDOWN_HEADING,
						text=line,
					)
				)
				idx += 1
				current_type = None
				if not is_last:
					segments.append(
						Segment(index=idx, segment_type=SegmentType.OTHER, text="\n")
					)
					idx += 1
				continue

			if re.match(r"^(\s*[-*+]\s+|\s*\d+\.\s+)", line_stripped):
				if current_lines and current_type not in (
					SegmentType.MARKDOWN_LIST_ITEM,
					None,
				):
					combined = "\n".join(current_lines)
					seg_type = current_type or _classify_chunk(combined)
					segments.append(
						Segment(index=idx, segment_type=seg_type, text=combined)
					)
					idx += 1
					current_lines = []
					segments.append(
						Segment(index=idx, segment_type=SegmentType.OTHER, text="\n")
					)
					idx += 1
				current_lines.append(line)
				current_type = SegmentType.MARKDOWN_LIST_ITEM
				continue

			line_type = _classify_chunk(line)
			if line_type in (SegmentType.KOREAN_PROSE, SegmentType.ENGLISH_PROSE):
				if current_type is None:
					current_type = line_type
				elif current_type != line_type and current_lines:
					combined = "\n".join(current_lines)
					segments.append(
						Segment(index=idx, segment_type=current_type, text=combined)
					)
					idx += 1
					current_lines = []
					segments.append(
						Segment(index=idx, segment_type=SegmentType.OTHER, text="\n")
					)
					idx += 1
					current_type = line_type
				current_lines.append(line)
			else:
				if current_lines:
					combined = "\n".join(current_lines)
					seg_type = current_type or _classify_chunk(combined)
					segments.append(
						Segment(index=idx, segment_type=seg_type, text=combined)
					)
					idx += 1
					current_lines = []
					current_type = None
					segments.append(
						Segment(index=idx, segment_type=SegmentType.OTHER, text="\n")
					)
					idx += 1
				segments.append(
					Segment(index=idx, segment_type=line_type, text=line)
				)
				idx += 1
				if not is_last:
					segments.append(
						Segment(index=idx, segment_type=SegmentType.OTHER, text="\n")
					)
					idx += 1

		if current_lines:
			combined = "\n".join(current_lines)
			seg_type = current_type or _classify_chunk(combined)
			segments.append(
				Segment(index=idx, segment_type=seg_type, text=combined)
			)
			idx += 1

	for seg in segments:
		seg.proofread = _should_proofread(seg.segment_type) and _has_korean(seg.text)

	return segments
