"""Orchestration d'un tour : charger, préparer, générer, sauvegarder."""

from typing import Literal

from .client import ChatResult, OllamaClient, OllamaError, TokenCallback
from .config import SYSTEM_PROMPT
from .memory import ContextManager, validate_history
from .storage import SQLiteStore
from .summary_cache import SummaryCache, make_summarizer_fingerprint, prepare_cached_context
from .tokens import count_tokens


class Assistant:
    def __init__(
        self,
        client: OllamaClient,
        store: SQLiteStore,
        *,
        max_pairs: int = 2,
        system_prompt: str = SYSTEM_PROMPT,
        summary_cache: SummaryCache | None = None,
        token_counter=None,
        margin: int = 64,
        summary_version: str = "m3-v1",
    ):
        self.client = client
        self.store = store
        self.system_prompt = system_prompt
        self.memory = ContextManager(client, max_pairs)
        if token_counter is None and client.settings.model != "qwen2.5:3b":
            raise ValueError("Fournir un token_counter adapté au modèle et à son template.")
        self.summary_cache = (
            summary_cache if summary_cache is not None else SummaryCache(store.path)
        )
        self.token_counter = count_tokens if token_counter is None else token_counter
        self.margin = margin
        self.summarizer_fingerprint = make_summarizer_fingerprint(client.settings, summary_version)

    def chat(
        self,
        user_id: str,
        conversation_id: str,
        text: str,
        *,
        mode: Literal["cached", "full", "window", "summary"] = "cached",
        stream: bool = True,
        on_token: TokenCallback | None = None,
    ) -> ChatResult:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Le message utilisateur doit contenir du texte.")
        history = self.store.load(user_id, conversation_id)
        if history is None:
            history = [{"role": "system", "content": self.system_prompt}]
        validate_history(history, pending_user=False)
        if len(history) > 1 and history[-1]["role"] != "assistant":
            raise ValueError("La conversation sauvegardée contient un tour inachevé.")
        history.append({"role": "user", "content": text})
        if mode == "cached":
            settings = self.client.settings
            messages = prepare_cached_context(
                history=history,
                cache=self.summary_cache,
                user_id=user_id,
                conversation_id=conversation_id,
                summarizer_fingerprint=self.summarizer_fingerprint,
                token_counter=self.token_counter,
                generate=self.client.generate,
                num_ctx=settings.num_ctx,
                reserved_output=settings.max_tokens,
                summary_tokens=settings.summary_tokens,
                margin=self.margin,
                keep_pairs=self.memory.max_pairs,
            )
        else:
            # Modes historiques du TP : comparaison, sans garantie de budget.
            messages = self.memory.prepare(history, mode).messages
        result = self.client.generate(messages, stream=stream, on_token=on_token)
        if result.truncated:
            raise OllamaError(
                "Réponse interrompue par la limite de génération ; tour non sauvegardé. "
                "Augmente max_tokens ou demande une réponse plus courte."
            )
        history.append({"role": "assistant", "content": result.content})
        # Un échec avant ce point laisse l'historique sauvegardé inchangé.
        self.store.save(user_id, conversation_id, history)
        return result
