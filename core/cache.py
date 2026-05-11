from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class Cache:
	def __init__(self, db_path: str = "cache.db", ttl_hours: int = 24, enabled: bool = True):
		self.enabled = enabled
		self.ttl_seconds = ttl_hours * 3600
		self.db_path = db_path

		if self.enabled:
			self._init_db()

	def _init_db(self) -> None:
		conn = sqlite3.connect(self.db_path)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS proofread_cache (
				cache_key TEXT PRIMARY KEY,
				corrected TEXT NOT NULL,
				provider TEXT NOT NULL,
				created_at REAL NOT NULL
			)
			"""
		)
		conn.execute(
			"CREATE INDEX IF NOT EXISTS idx_created_at ON proofread_cache(created_at)"
		)
		conn.commit()
		conn.close()

	@staticmethod
	def _make_key(text: str, tone: str, provider: str) -> str:
		normalized = text.strip()
		raw = f"{normalized}|{tone}|{provider}"
		return hashlib.sha256(raw.encode("utf-8")).hexdigest()

	def get(self, text: str, tone: str, provider: str) -> str | None:
		if not self.enabled:
			return None

		key = self._make_key(text, tone, provider)
		conn = sqlite3.connect(self.db_path)
		try:
			row = conn.execute(
				"SELECT corrected, created_at FROM proofread_cache WHERE cache_key = ?",
				(key,),
			).fetchone()
			if row is None:
				return None

			corrected, created_at = row
			if time.time() - created_at > self.ttl_seconds:
				conn.execute("DELETE FROM proofread_cache WHERE cache_key = ?", (key,))
				conn.commit()
				return None

			return corrected
		finally:
			conn.close()

	def put(self, text: str, corrected: str, tone: str, provider: str) -> None:
		if not self.enabled:
			return

		key = self._make_key(text, tone, provider)
		conn = sqlite3.connect(self.db_path)
		try:
			conn.execute(
				"""
				INSERT OR REPLACE INTO proofread_cache
				(cache_key, corrected, provider, created_at)
				VALUES (?, ?, ?, ?)
				""",
				(key, corrected, provider, time.time()),
			)
			conn.commit()
		finally:
			conn.close()

	def cleanup(self) -> int:
		if not self.enabled:
			return 0

		conn = sqlite3.connect(self.db_path)
		try:
			cutoff = time.time() - self.ttl_seconds
			cursor = conn.execute(
				"DELETE FROM proofread_cache WHERE created_at < ?", (cutoff,)
			)
			conn.commit()
			return cursor.rowcount
		finally:
			conn.close()

	def clear(self) -> None:
		if not self.enabled:
			return

		conn = sqlite3.connect(self.db_path)
		try:
			conn.execute("DELETE FROM proofread_cache")
			conn.commit()
		finally:
			conn.close()
