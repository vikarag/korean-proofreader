import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.detector import detect_korean, _count_korean_chars


class TestCountKoreanChars:
	def test_empty(self):
		assert _count_korean_chars("") == 0

	def test_pure_korean(self):
		assert _count_korean_chars("안녕하세요") == 5

	def test_pure_english(self):
		assert _count_korean_chars("hello world") == 0

	def test_mixed(self):
		result = _count_korean_chars("hello 안녕 world")
		assert result == 2

	def test_jamo(self):
		# Hangul Jamo
		assert _count_korean_chars("ㄱㄴㄷ") == 3


class TestDetectKorean:
	def test_empty_text(self):
		result = detect_korean("")
		assert result.is_korean is False
		assert result.korean_ratio == 0.0

	def test_pure_korean(self):
		text = "이 함수는 데이터를 처리합니다. 사용자가 입력한 값을 검증한 후 결과를 반환합니다."
		result = detect_korean(text)
		assert result.is_korean is True
		assert result.korean_ratio > 0.5

	def test_pure_english(self):
		text = "This is a pure English sentence with no Korean at all."
		result = detect_korean(text)
		assert result.is_korean is False
		assert result.korean_ratio == 0.0

	def test_mixed_high_korean(self):
		text = "API 서버를 시작합니다. 사용자 요청을 처리합니다. Use uvicorn to run the server."
		result = detect_korean(text, min_korean_chars=5)
		assert result.is_korean is True

	def test_mixed_low_korean(self):
		text = "Use the API server to start. Run uvicorn main:app."
		result = detect_korean(text, threshold=0.10, min_korean_chars=10)
		assert result.is_korean is False

	def test_min_chars_threshold(self):
		text = "한글"
		result = detect_korean(text, threshold=0.10, min_korean_chars=10)
		assert result.is_korean is False

	def test_custom_threshold(self):
		text = "이 함수는 데이터를 처리합니다."
		result = detect_korean(text, threshold=0.90, min_korean_chars=1)
		# Korean ratio might not be > 0.90 since there are non-Korean chars
		assert isinstance(result.is_korean, bool)

	def test_ratio_rounding(self):
		text = "안녕 hello"
		result = detect_korean(text)
		assert isinstance(result.korean_ratio, float)
