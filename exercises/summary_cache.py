"""M3 — exercice du cache : compléter save/load, puis is_cache_valid.

Aucun modèle ni tokenizer n'est nécessaire pour cet exercice.
"""

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SummaryCacheEntry:
    summary_text: str
    covered_until: int
    source_hash: str
    summarizer_fingerprint: str


def source_hash(history, covered_until):
    """Empreinte du préfixe couvert, système inclus ; fin EXCLUSIVE.

    Pour [S, U1, A1, U2], covered_until=3 couvre [S, U1, A1].
    L'indice doit tomber après un couple complet, jamais après un user isolé.
    """
    if (
        isinstance(covered_until, bool)
        or not isinstance(covered_until, int)
        or covered_until < 1
        or covered_until > len(history)
        or covered_until % 2 == 0
    ):
        raise ValueError("Position de couverture invalide.")
    serialized = json.dumps(
        history[:covered_until], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class SummaryCache:
    def __init__(self, db_path):
        self.path = Path(db_path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    summary_text TEXT NOT NULL,
                    covered_until INTEGER NOT NULL,
                    source_hash TEXT NOT NULL,
                    summarizer_fingerprint TEXT NOT NULL,
                    PRIMARY KEY (user_id, conversation_id)
                )
            """)
            con.commit()

    def save(self, user_id, conversation_id, entry: SummaryCacheEntry):
        """Partie A : écrire les quatre champs de entry pour cette paire d'identifiants.

        Insérer si absent, mettre à jour si présent, utiliser des paramètres SQL,
        valider l'écriture puis fermer la connexion. Remplacer ce corps.
        """
        raise NotImplementedError("À compléter : SummaryCache.save")

    def load(self, user_id, conversation_id):
        """Partie A : filtrer sur les DEUX identifiants.

        Retourner None si absent, sinon un SummaryCacheEntry reconstruit depuis
        la ligne SQLite. Fermer la connexion. Remplacer ce corps.
        """
        raise NotImplementedError("À compléter : SummaryCache.load")


def is_cache_valid(entry, history, summarizer_fingerprint):
    """Partie B : booléen, sans appeler de modèle ni modifier history.

    False si entry est absent, si l'empreinte du résumeur diffère, si la position
    est invalide, ou si source_hash ne correspond plus au préfixe couvert.
    Ajouter des messages APRÈS ce préfixe ne doit pas invalider le cache.
    """
    raise NotImplementedError("À compléter après la partie A : is_cache_valid")
