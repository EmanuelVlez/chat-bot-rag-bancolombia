import os
import sqlite3
from pathlib import Path
from datetime import datetime

DEFAULT_DB = Path(os.getenv("CHUNKS_DB_PATH", Path(__file__).parent.parent / "data" / "chunks.db"))


class ChunkStore:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB

    def init(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT NOT NULL,
                title       TEXT,
                category    TEXT,
                chunk_index INTEGER NOT NULL,
                content     TEXT NOT NULL,
                token_count INTEGER,
                created_at  TEXT
            )
        """)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_category ON chunks(category)"
        )
        self.conn.commit()

    def clear_url(self, url: str):
        """Elimina chunks anteriores de una URL (permite reprocesar)."""
        self.conn.execute("DELETE FROM chunks WHERE url = ?", (url,))
        self.conn.commit()

    def save_chunks(self, url: str, title: str, category: str, chunks: list[dict]):
        now = datetime.utcnow().isoformat()
        self.conn.executemany(
            """
            INSERT INTO chunks (url, title, category, chunk_index, content, token_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (url, title, category, i, c["content"], c["token_count"], now)
                for i, c in enumerate(chunks)
            ],
        )
        self.conn.commit()

    def stats(self) -> dict:
        cur = self.conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT url), SUM(token_count) FROM chunks"
        )
        total_chunks, total_urls, total_tokens = cur.fetchone()
        return {
            "total_chunks": total_chunks,
            "total_urls": total_urls,
            "total_tokens": total_tokens,
        }

    def close(self):
        self.conn.close()
