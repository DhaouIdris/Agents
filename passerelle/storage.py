"""Historique complet dans SQLite ; pas de base globale créée à l'import."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .client import Message


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    messages_json TEXT NOT NULL,
                    PRIMARY KEY (user_id, conversation_id)
                )
            """)
            con.commit()

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    @staticmethod
    def _validate_key(user_id: str, conversation_id: str):
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id doit être un identifiant non vide.")
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ValueError("conversation_id doit être un identifiant non vide.")

    def load(self, user_id: str, conversation_id: str) -> list[Message] | None:
        self._validate_key(user_id, conversation_id)
        with closing(self._connect()) as con:
            row = con.execute(
                "SELECT messages_json FROM conversations WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def save(self, user_id: str, conversation_id: str, messages: list[Message]):
        self._validate_key(user_id, conversation_id)
        serialized = json.dumps(messages, ensure_ascii=False)
        with closing(self._connect()) as con:
            con.execute(
                """
                INSERT INTO conversations (user_id, conversation_id, messages_json)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, conversation_id)
                DO UPDATE SET messages_json = excluded.messages_json
                """,
                (user_id, conversation_id, serialized),
            )
            con.commit()
