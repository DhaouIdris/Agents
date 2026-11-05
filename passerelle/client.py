"""Un seul client pour les appels complets, le streaming et les métriques."""

import json
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Callable

import requests

from .config import Settings

Message = dict[str, str]
TokenCallback = Callable[[str], None]


class OllamaError(RuntimeError):
    """Erreur HTTP, protocole incomplet ou réponse inexploitable."""


@dataclass(frozen=True)
class Metrics:
    total_s: float
    first_content_s: float | None
    load_s: float | None
    prompt_s: float | None
    generation_s: float | None
    input_tokens: int | None
    output_tokens: int | None

    @property
    def tokens_per_second(self) -> float | None:
        if self.generation_s and self.output_tokens is not None:
            return self.output_tokens / self.generation_s
        return None

    def as_dict(self) -> dict:
        return {**asdict(self), "tokens_per_second": self.tokens_per_second}


@dataclass(frozen=True)
class ChatResult:
    content: str
    metrics: Metrics
    done_reason: str | None = None

    @property
    def truncated(self) -> bool:
        return self.done_reason == "length"


class OllamaClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    def generate(
        self,
        messages: list[Message],
        *,
        stream: bool = False,
        on_token: TokenCallback | None = None,
        num_ctx: int | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Retourne un résultat structuré ; n'affiche rien sans callback.

        first_content_s mesure la réception du premier texte côté client,
        uniquement en streaming. Un fragment n'est pas nécessairement un token.
        Aucun retry automatique : une génération interrompue remonte une erreur.
        """
        if not messages:
            raise ValueError("La liste de messages ne peut pas être vide.")
        context_size = self.settings.num_ctx if num_ctx is None else num_ctx
        output_size = self.settings.max_tokens if max_tokens is None else max_tokens
        if context_size <= 0 or output_size <= 0 or output_size >= context_size:
            raise ValueError("Il faut 0 < max_tokens < num_ctx.")
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.settings.keep_alive,
            "options": {
                "num_ctx": context_size,
                "num_predict": output_size,
                "temperature": self.settings.temperature,
            },
        }
        start = perf_counter()
        first_content_s = None
        parts = []
        final = None
        try:
            with requests.post(
                self.settings.chat_url,
                json=payload,
                stream=stream,
                timeout=self.settings.timeout_s,
            ) as response:
                response.raise_for_status()
                if stream:
                    # Éviter d'attendre le remplissage du buffer par défaut de requests.
                    for line in response.iter_lines(chunk_size=1):
                        if not line:
                            continue
                        event = json.loads(line)
                        content = self._content(event)
                        if content:
                            if first_content_s is None:
                                first_content_s = perf_counter() - start
                            parts.append(content)
                            if on_token is not None:
                                on_token(content)
                        if event.get("done") is True:
                            final = event
                            break
                else:
                    final = response.json()
                    parts.append(self._content(final))
        except requests.RequestException as exc:
            raise OllamaError(
                f"Appel Ollama échoué ({self.settings.chat_url}). "
                "Vérifie qu'Ollama est lancé et que le modèle est installé."
            ) from exc
        except (ValueError, TypeError, AttributeError) as exc:
            raise OllamaError("Réponse Ollama invalide : JSON ou structure inattendue.") from exc

        if final is None or final.get("done") is not True:
            raise OllamaError("Flux interrompu : aucun événement final done=true reçu.")
        content = "".join(parts)
        if not content.strip():
            raise OllamaError("Le modèle n'a renvoyé aucun texte exploitable.")

        def seconds(name):
            value = final.get(name)
            return None if value is None else value / 1e9

        metrics = Metrics(
            total_s=perf_counter() - start,
            first_content_s=first_content_s,
            load_s=seconds("load_duration"),
            prompt_s=seconds("prompt_eval_duration"),
            generation_s=seconds("eval_duration"),
            input_tokens=final.get("prompt_eval_count"),
            output_tokens=final.get("eval_count"),
        )
        return ChatResult(content, metrics, final.get("done_reason"))

    @staticmethod
    def _content(event: dict) -> str:
        if not isinstance(event, dict):
            raise OllamaError("Un événement Ollama doit être un objet JSON.")
        if "error" in event:
            raise OllamaError(str(event["error"]))
        content = event.get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise OllamaError("Le contenu du message doit être du texte.")
        return content
