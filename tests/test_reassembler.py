import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.reassembler import reassemble
from core.segmenter import segment, SegmentType


class TestReassemble:
	def test_no_corrections(self):
		text = "이 함수는 데이터를 처리합니다."
		segs = segment(text)
		result = reassemble(segs, {})
		assert result == text

	def test_with_correction(self):
		text = "이 함수를 진행합니다."
		segs = segment(text)
		corrections = {}
		for s in segs:
			if s.proofread:
				corrections[s.index] = s.text.replace("진행합니다", "실행합니다")
		result = reassemble(segs, corrections)
		assert "실행합니다" in result

	def test_preserves_code_blocks(self):
		text = "한글 텍스트.\n```python\nprint('hello')\n```\n더 많은 한글."
		segs = segment(text)
		result = reassemble(segs, {})
		assert "```python" in result
		assert "print('hello')" in result

	def test_heading_prefix_preserved(self):
		text = "# 제목입니다"
		segs = segment(text)
		corrections = {}
		for s in segs:
			if s.proofread:
				corrections[s.index] = "새 제목입니다"
		result = reassemble(segs, corrections)
		assert result.startswith("# ")

	def test_roundtrip(self):
		text = "첫 번째 문장입니다.\n```\ncode\n```\n세 번째 문장입니다."
		segs = segment(text)
		result = reassemble(segs, {})
		assert result == text

	def test_heading_followed_by_paragraph_roundtrip(self):
		text = "# 제목\n본문"
		segs = segment(text)
		assert reassemble(segs, {}) == text

	def test_leading_trailing_whitespace_around_code_block(self):
		text = "\n\n```x```\n\n"
		segs = segment(text)
		assert reassemble(segs, {}) == text

	def test_list_then_paragraph_roundtrip(self):
		text = "- 항목\n본문 단락"
		segs = segment(text)
		assert reassemble(segs, {}) == text
