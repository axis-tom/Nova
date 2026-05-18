"""
Keepa ASIN 级缓存
按 (asin, domain) 粒度缓存 _parse_product 输出，SQLite 持久化。
KeepaConnector.query_products() 内部透明调用，上层无感知。
"""

import json
import logging
import sqlite3
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "backend" / "infrastructure" / "data" / "keepa_cache.sqlite"


class KeepaProductCache:

    def __init__(self, db_path: Path = _DEFAULT_DB_PATH, ttl_seconds: int = 6 * 3600):
        self._db_path = db_path
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path), timeout=5)

    def _ensure_table(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS keepa_products (
                    asin    TEXT NOT NULL,
                    domain  TEXT NOT NULL DEFAULT 'US',
                    data    TEXT NOT NULL,
                    cached_at REAL NOT NULL,
                    PRIMARY KEY (asin, domain)
                )
            """)

    def get_many(self, asins: List[str], domain: str = "US") -> Dict[str, Dict[str, Any]]:
        if not asins:
            return {}
        cutoff = time.time() - self._ttl
        with self._lock, self._conn() as conn:
            placeholders = ",".join("?" * len(asins))
            rows = conn.execute(
                f"SELECT asin, data FROM keepa_products "
                f"WHERE asin IN ({placeholders}) AND domain = ? AND cached_at > ?",
                (*asins, domain, cutoff),
            ).fetchall()
        return {asin: json.loads(data) for asin, data in rows}

    def put_many(self, products: List[Dict[str, Any]], domain: str = "US") -> None:
        if not products:
            return
        now = time.time()
        rows = [
            (p["asin"], domain, json.dumps(p, ensure_ascii=False), now)
            for p in products
            if "asin" in p
        ]
        with self._lock, self._conn() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO keepa_products (asin, domain, data, cached_at) "
                "VALUES (?, ?, ?, ?)",
                rows,
            )

    def evict_expired(self) -> int:
        cutoff = time.time() - self._ttl
        with self._lock, self._conn() as conn:
            cursor = conn.execute("DELETE FROM keepa_products WHERE cached_at < ?", (cutoff,))
            return cursor.rowcount

    def stats(self) -> Dict[str, int]:
        cutoff = time.time() - self._ttl
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM keepa_products").fetchone()[0]
            fresh = conn.execute(
                "SELECT COUNT(*) FROM keepa_products WHERE cached_at > ?", (cutoff,)
            ).fetchone()[0]
        return {"total": total, "fresh": fresh, "stale": total - fresh}


# ── 模块级单例 ──

_cache_instance: Optional[KeepaProductCache] = None
_cache_init_lock = threading.Lock()


def get_cache() -> Optional[KeepaProductCache]:
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    with _cache_init_lock:
        if _cache_instance is not None:
            return _cache_instance

        try:
            from backend.config.config import settings
            ttl_hours = getattr(settings, "KEEPA_CACHE_TTL_HOURS", 6)
        except Exception:
            ttl_hours = 6

        if ttl_hours <= 0:
            logger.info("Keepa 缓存已禁用 (KEEPA_CACHE_TTL_HOURS=0)")
            return None

        try:
            _cache_instance = KeepaProductCache(ttl_seconds=ttl_hours * 3600)
            logger.info(
                f"Keepa 缓存已初始化 (TTL={ttl_hours}h, DB={_cache_instance._db_path})"
            )
        except Exception as e:
            logger.warning(f"Keepa 缓存初始化失败，将直接调 API: {e}")
            return None

    return _cache_instance
