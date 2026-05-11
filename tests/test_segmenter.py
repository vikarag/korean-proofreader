import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.segmenter import segment, SegmentType


class TestSegment:
	def test_empty_text(self):
		segs = segment("")
		assert segs == []

	def test_pure_korean(self):
		text = "이 함수는 데이터를 처리합니다."
		segs = segment(text)
		assert len(segs) >= 1
		korean_segs = [s for s in segs if s.segment_type == SegmentType.KOREAN_PROSE]
		assert len(korean_segs) >= 1
		assert any(s.proofread for s in segs)

	def test_code_block_passthrough(self):
		text = "다음 코드를 실행하세요:\n```python\ndef hello():\n    print('world')\n```\n결과가 출력됩니다."
		segs = segment(text)
		code_segs = [s for s in segs if s.segment_type == SegmentType.CODE_BLOCK]
		assert len(code_segs) == 1
		assert code_segs[0].proofread is False
		assert "def hello" in code_segs[0].text

	def test_inline_code_passthrough(self):
		text = "명령어는 `uvicorn main:app` 입니다."
		segs = segment(text)
		inline_segs = [s for s in segs if s.segment_type == SegmentType.INLINE_CODE]
		assert len(inline_segs) == 1
		assert inline_segs[0].proofread is False

	def test_url_passthrough(self):
		text = "자세한 내용은 https://example.com/docs 를 확인하세요."
		segs = segment(text)
		url_segs = [s for s in segs if s.segment_type == SegmentType.URL]
		assert len(url_segs) >= 1
		assert all(not s.proofread for s in url_segs)

	def test_heading_preserved(self):
		text = "# 제목입니다\n이것은 본문입니다."
		segs = segment(text)
		heading_segs = [s for s in segs if s.segment_type == SegmentType.MARKDOWN_HEADING]
		assert len(heading_segs) >= 1

	def test_list_items(self):
		text = "- 첫 번째 항목\n- 두 번째 항목"
		segs = segment(text)
		list_segs = [s for s in segs if s.segment_type == SegmentType.MARKDOWN_LIST_ITEM]
		assert len(list_segs) >= 1

	def test_english_passthrough(self):
		text = "This is English text."
		segs = segment(text)
		english_segs = [s for s in segs if s.segment_type == SegmentType.ENGLISH_PROSE]
		assert len(english_segs) >= 1
		assert all(not s.proofread for s in english_segs)

	def test_segment_indices_unique(self):
		text = "한글 텍스트입니다.\n```code\n```\n더 많은 한글."
		segs = segment(text)
		indices = [s.index for s in segs]
		assert len(indices) == len(set(indices))

	def test_mixed_content_preserves_order(self):
		text = "첫 번째.\n```\ncode\n```\n세 번째."
		segs = segment(text)
		reassembled = "".join(s.text for s in segs)
		assert reassembled == text
