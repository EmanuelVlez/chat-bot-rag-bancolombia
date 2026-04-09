"""
Memoria largo plazo: perfil de usuario en SQLite.

Registra los temas que más consulta cada usuario para personalizar
futuras respuestas y entender patrones de uso.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(os.getenv("PROFILES_DB_PATH", Path(__file__).parent.parent / "data" / "user_profiles.db"))


class UserProfileStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id      TEXT PRIMARY KEY,
                    name         TEXT,
                    interests    TEXT DEFAULT '[]',
                    query_count  INTEGER DEFAULT 0,
                    last_seen    TEXT
                )
            """)

    def get(self, user_id: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
            ).fetchone()

        if not row:
            return {"user_id": user_id, "interests": [], "query_count": 0}

        return {
            "user_id": row["user_id"],
            "name": row["name"],
            "interests": json.loads(row["interests"]),
            "query_count": row["query_count"],
            "last_seen": row["last_seen"],
        }

    def record_query(self, user_id: str, category: str | None = None):
        """Registra una consulta y actualiza intereses del usuario."""
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO profiles (user_id, interests, query_count, last_seen)
                VALUES (?, '[]', 1, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    query_count = query_count + 1,
                    last_seen   = excluded.last_seen
            """, (user_id, now))

            if category:
                row = conn.execute(
                    "SELECT interests FROM profiles WHERE user_id = ?", (user_id,)
                ).fetchone()
                interests: list = json.loads(row[0])

                if category not in interests:
                    interests.append(category)
                    conn.execute(
                        "UPDATE profiles SET interests = ? WHERE user_id = ?",
                        (json.dumps(interests), user_id),
                    )

    def context_for_prompt(self, user_id: str) -> str:
        """Retorna texto para incluir en el system prompt con contexto del usuario."""
        profile = self.get(user_id)
        if not profile.get("query_count"):
            return ""

        interests = profile.get("interests", [])
        count = profile.get("query_count", 0)

        parts = [f"Este usuario ha realizado {count} consultas previas."]
        if interests:
            parts.append(f"Sus temas de interés: {', '.join(interests)}.")

        return " ".join(parts)
