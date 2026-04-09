import aiosqlite
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# Siempre resuelve a scraper/data/raw.db sin importar el CWD
DEFAULT_DB = Path(__file__).parent.parent / "data" / "raw.db"


class RawStore:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB

    async def init(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = await aiosqlite.connect(self.db_path)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                url          TEXT PRIMARY KEY,
                title        TEXT,
                content      TEXT,
                content_hash TEXT,
                category     TEXT,
                extracted_at TEXT
            )
        """)
        await self.conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_content_hash ON pages(content_hash)"
        )
        await self.conn.commit()

    async def exists(self, url):
        cursor = await self.conn.execute(
            "SELECT 1 FROM pages WHERE url = ?",
            (url,)
        )
        result = await cursor.fetchone()
        return result is not None

    async def save(self, url, content, title=None, category=None) -> bool:
        """
        Inserta la página solo si su content_hash no existe ya en la tabla.
        Retorna True si se insertó, False si era contenido duplicado.
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        cursor = await self.conn.execute(
            "SELECT 1 FROM pages WHERE content_hash = ?", (content_hash,)
        )
        if await cursor.fetchone():
            return False

        extracted_at = datetime.now(timezone.utc).isoformat()
        await self.conn.execute("""
            INSERT OR IGNORE INTO pages
            (url, title, content, content_hash, category, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (url, title, content, content_hash, category, extracted_at))
        await self.conn.commit()
        return True

    async def close(self):
        await self.conn.close()