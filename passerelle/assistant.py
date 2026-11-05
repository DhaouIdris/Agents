"""Orchestration d'un tour : charger, préparer, générer, sauvegarder."""

from .client import ChatResult, OllamaClient, OllamaError, TokenCallback
from .config import SYSTEM_PROMPT
from .memory import ContextManager, MemoryMode, validate_history
from .storage import SQLiteStore


class Assistant:
    def __init__(
        self,
        client: OllamaClient,
        store: SQLiteStore,
        *,
        max_pairs: int = 2,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self.client = client
        self.store = store
        self.system_prompt = system_prompt
        self.memory = ContextManager(client, max_pairs)

    def chat(
        self,
        user_id: str,
        conversation_id: str,
        text: str,
        *,
        mode: MemoryMode = "summary",
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
        prepared = self.memory.prepare(history, mode)
        result = self.client.generate(prepared.messages, stream=stream, on_token=on_token)
        if result.truncated:
            raise OllamaError(
                "Réponse interrompue par la limite de génération ; tour non sauvegardé. "
                "Augmente max_tokens ou demande une réponse plus courte."
            )
        history.append({"role": "assistant", "content": result.content})
        # Un échec avant ce point laisse l'historique sauvegardé inchangé.
        self.store.save(user_id, conversation_id, history)
        return result
