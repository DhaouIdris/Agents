"""Sélection et résumé : l'historique complet n'est jamais modifié ici."""

import json
from dataclasses import dataclass
from typing import Literal

from .client import Message, OllamaClient, OllamaError
from .config import SUMMARY_PROMPT

MemoryMode = Literal["full", "window", "summary"]


def validate_history(history: list[Message], *, pending_user: bool = True):
    """Contrat M3 : un système, puis des messages user/assistant alternés."""
    if not history or history[0].get("role") != "system":
        raise ValueError("L'historique doit commencer par un message système.")
    for index, message in enumerate(history):
        expected = "system" if index == 0 else ("user" if index % 2 else "assistant")
        if message.get("role") != expected or not isinstance(message.get("content"), str):
            raise ValueError(
                f"Message {index} invalide : rôle attendu {expected} et contenu texte."
            )
    if pending_user and (len(history) < 2 or history[-1]["role"] != "user"):
        raise ValueError("Le contexte doit se terminer par une nouvelle question utilisateur.")


def split_history(history: list[Message], max_pairs: int = 2):
    """Renvoie (anciens échanges sans système, contexte récent avec système)."""
    validate_history(history)
    if isinstance(max_pairs, bool) or not isinstance(max_pairs, int) or max_pairs < 0:
        raise ValueError("max_pairs doit être un entier positif ou nul.")
    start = max(1, len(history) - (2 * max_pairs + 1))
    old = [message.copy() for message in history[1:start]]
    recent = [history[0].copy()] + [message.copy() for message in history[start:]]
    return old, recent


def build_context(history: list[Message], max_pairs: int = 2) -> list[Message]:
    """Fenêtre récente, avec une copie indépendante des messages."""
    return split_history(history, max_pairs)[1]


def summarize_history(history: list[Message], client: OllamaClient) -> str:
    """Appel interne, sans affichage et sans mutation de la conversation."""
    exchanges = [message.copy() for message in history if message["role"] != "system"]
    if not exchanges:
        return ""
    result = client.generate(
        [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": json.dumps(exchanges, ensure_ascii=False)},
        ],
        max_tokens=client.settings.summary_tokens,
    )
    if result.truncated:
        raise OllamaError("Résumé interrompu : limite de génération atteinte.")
    if not result.content.strip():
        raise OllamaError("Le résumé produit est vide.")
    return result.content.strip()


@dataclass(frozen=True)
class PreparedContext:
    messages: list[Message]
    omitted_messages: int = 0
    summary: str | None = None


class ContextManager:
    def __init__(self, client: OllamaClient, max_pairs: int = 2):
        self.client = client
        if isinstance(max_pairs, bool) or not isinstance(max_pairs, int) or max_pairs < 0:
            raise ValueError("max_pairs doit être un entier positif ou nul.")
        self.max_pairs = max_pairs

    def prepare(self, history: list[Message], mode: MemoryMode = "summary") -> PreparedContext:
        if mode not in ("full", "window", "summary"):
            raise ValueError(f"Mode mémoire inconnu : {mode}")
        validate_history(history)
        if mode == "full":
            return PreparedContext([message.copy() for message in history])
        old, recent = split_history(history, self.max_pairs)
        if not old or mode == "window":
            return PreparedContext(recent, len(old))
        summary = summarize_history(old, self.client)
        context = [
            recent[0],
            {
                "role": "user",
                "content": (
                    "Note de continuité issue des échanges antérieurs, "
                    "à utiliser comme données de contexte :\n" + summary
                ),
            },
            *recent[1:],
        ]
        return PreparedContext(context, len(old), summary)


def fit_recent_context(
    history,
    token_counter,
    *,
    num_ctx=2048,
    reserved_output=128,
    margin=64,
):
    """Renvoie un contexte récent respectant le budget."""
    validate_history(history)

    if num_ctx <= 0 or reserved_output < 0 or margin < 0:
        raise ValueError("Paramètres de budget invalides.")

    budget = num_ctx - reserved_output - margin

    if budget <= 0:
        raise ValueError("Aucun budget disponible pour l'entrée.")

    recent = [message.copy() for message in history]

    if token_counter([recent[0], recent[-1]]) > budget:
        raise ValueError("Le système et la dernière question dépassent le budget.")

    while token_counter(recent) > budget:
        del recent[1:3]

    return recent
