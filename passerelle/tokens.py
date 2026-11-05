"""Comptage de référence : tokenizer chargé uniquement lors du premier appel.

Le template Hugging Face doit être comparé au rendu effectif d'Ollama avant
d'utiliser ce compteur comme une mesure exacte de l'entrée du serveur.
"""

from functools import lru_cache

DEFAULT_TOKENIZER = "Qwen/Qwen2.5-3B-Instruct"


@lru_cache(maxsize=1)
def _get_tokenizer(tokenizer_id):
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise ImportError(
            'Comptage réel : installer python -m pip install -e ".[tokenization]" '
            "dans l'environnement du notebook."
        ) from exc
    return AutoTokenizer.from_pretrained(tokenizer_id)


def count_tokens(messages, tokenizer_id=DEFAULT_TOKENIZER):
    tokenizer = _get_tokenizer(tokenizer_id)
    token_ids = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=False,
    )
    return len(token_ids)
