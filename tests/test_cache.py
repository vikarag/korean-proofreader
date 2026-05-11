import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.cache import Cache


class TestCacheKeyIsolation:
	def test_round_trip_same_tone_and_provider(self, tmp_path):
		c = Cache(db_path=str(tmp_path / "c.db"))
		c.put("진행합니다", "실행해요", "casual", "gemini")
		assert c.get("진행합니다", "casual", "gemini") == "실행해요"

	def test_tone_collision_misses(self, tmp_path):
		c = Cache(db_path=str(tmp_path / "c.db"))
		c.put("진행합니다", "casual-out", "casual", "gemini")
		assert c.get("진행합니다", "formal", "gemini") is None

	def test_provider_collision_misses(self, tmp_path):
		c = Cache(db_path=str(tmp_path / "c.db"))
		c.put("진행합니다", "gemini-out", "casual", "gemini")
		assert c.get("진행합니다", "casual", "openai") is None

	def test_disabled_cache_returns_none(self, tmp_path):
		c = Cache(db_path=str(tmp_path / "c.db"), enabled=False)
		c.put("진행합니다", "out", "casual", "gemini")
		assert c.get("진행합니다", "casual", "gemini") is None
