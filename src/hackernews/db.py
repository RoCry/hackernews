import json
import aiosqlite
from typing import Optional, Dict, Any
from pathlib import Path


class HNCache:
    ITEM_TABLE_NAME = "hn_cache_item"

    CREATE_TABLE_SQL = f"""
    CREATE TABLE IF NOT EXISTS {ITEM_TABLE_NAME} (
        id INTEGER PRIMARY KEY,
        data TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    def __init__(self, db_path: str = "hn_cache.sqlite3"):
        self.db_path = Path(db_path)
        self._db: Optional[aiosqlite.Connection] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self):
        """Connect to the database and initialize tables"""
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute(self.CREATE_TABLE_SQL)
        await self._db.commit()

    async def close(self):
        """Close the database connection"""
        if self._db:
            await self._db.close()
            self._db = None

    async def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get item from cache by id"""
        if not self._db:
            raise RuntimeError("Database not connected")

        async with self._db.execute(
            f"SELECT data FROM {self.ITEM_TABLE_NAME} WHERE id = ?", (item_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    async def save_item(self, item_id: int, data: Dict[str, Any]):
        """Save item to cache"""
        if not self._db:
            raise RuntimeError("Database not connected")

        await self._db.execute(
            f"INSERT OR REPLACE INTO {self.ITEM_TABLE_NAME} (id, data) VALUES (?, ?)",
            (item_id, json.dumps(data)),
        )
        await self._db.commit() 