"""Validation M3 : démonstration hors ligne ou essai explicite avec Ollama local."""

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

from passerelle import Assistant, ChatResult, Metrics, OllamaClient, Settings, SQLiteStore
from passerelle.config import SYSTEM_PROMPT
from passerelle.summary_cache import prepare_cached_context


def run_offline():
    """Exerce le vrai Assistant et SQLite, avec un compteur et un LLM simulés."""
    client = Mock()
    client.settings = Settings(num_ctx=100, max_tokens=20, summary_tokens=20)
    client.generate.return_value = ChatResult(
        "Réponse simulée", Metrics(0, None, None, None, None, None, None), "stop"
    )
    with tempfile.TemporaryDirectory() as directory:
        store = SQLiteStore(Path(directory) / "memory.db")
        history = [{"role": "system", "content": "Assistant factuel."}]
        for i in range(3):
            history.extend(
                [
                    {"role": "user", "content": f"Question initiale {i}"},
                    {"role": "assistant", "content": "Bien reçu."},
                ]
            )
        store.save("alice", "m3", history)
        assistant = Assistant(
            client,
            store,
            max_pairs=1,
            margin=10,
            token_counter=lambda messages: 10 * len(messages),
        )
        counts = []
        coverage = []
        for question in ("Question A", "Question B", "Question C"):
            assistant.chat("alice", "m3", question, stream=False)
            counts.append(client.generate.call_count)
            coverage.append(assistant.summary_cache.load("alice", "m3").covered_until)
        if counts != [2, 3, 5] or coverage != [5, 5, 9]:
            raise AssertionError(f"Parcours inattendu : {counts=}, {coverage=}")
        if len(store.load("alice", "m3")) != 13:
            raise AssertionError("L'historique original doit conserver tous les tours.")
        print("Appels cumulés (résumé + réponse) :", counts, "; attendu [2, 3, 5]")
        print("Couverture exclusive du résumé :", coverage, "; attendu [5, 5, 9]")
        print("OK : création, réutilisation puis actualisation du cache ; 13 messages conservés.")
    print("Simulation uniquement : la fidélité du modèle n'est pas évaluée.")


def run_live():
    """Données synthétiques, DB temporaire, vrai tokenizer et vrais appels Ollama."""
    from passerelle.tokens import count_tokens

    settings = Settings()
    client = OllamaClient(settings)
    original_generate = client.generate
    measurements = []

    def measured_generate(messages, **kwargs):
        estimate = count_tokens(messages)
        result = original_generate(messages, **kwargs)
        measured = result.metrics.input_tokens
        measurements.append(
            {
                "kind": "summary" if "max_tokens" in kwargs else "answer",
                "reference_tokens": estimate,
                "server_prompt_eval_count": measured,
                "delta_server_minus_reference": None if measured is None else measured - estimate,
            }
        )
        return result

    client.generate = Mock(wraps=measured_generate)
    # Charge synthétique : suffisamment d'anciens échanges pour rendre la compaction utile.
    records = "\n".join(
        f"Dossier fictif DEMO-{i:03d} : reçu, service formation, aucun paiement demandé."
        for i in range(25)
    )
    history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "Je m'appelle Lina, je travaille à Lyon et je dispose uniquement d'un CPU.\n"
            + records,
        },
        {"role": "assistant", "content": "Bien reçu pour Lina, Lyon et le CPU."},
        {
            "role": "user",
            "content": "Pour le projet, utilisons uniquement des données synthétiques. " * 12,
        },
        {"role": "assistant", "content": "D'accord, nous utiliserons des données synthétiques."},
    ]
    question = "Quel est mon prénom, ma ville et ma contrainte matérielle ? Reply in English."
    pending = [*history, {"role": "user", "content": question}]
    raw_count = count_tokens(pending)
    # Réserver volontairement plus de marge pour provoquer la compaction sans
    # changer num_ctx ni remplir toute la fenêtre sur le PC de 8 Go.
    margin = settings.num_ctx - settings.max_tokens - (raw_count - 1)
    if margin < 64:
        raise ValueError("Fixture trop longue pour ce tokenizer ; raccourcir records.")
    with tempfile.TemporaryDirectory() as directory:
        store = SQLiteStore(Path(directory) / "live.db")
        store.save("alice", "m3-live", history)
        assistant = Assistant(client, store, max_pairs=1, margin=margin, token_counter=count_tokens)
        result = assistant.chat("alice", "m3-live", question, stream=False)
        entry = assistant.summary_cache.load("alice", "m3-live")
        if entry is None or entry.covered_until != 3:
            raise AssertionError("Le résumé attendu n'a pas été enregistré.")
        before = client.generate.call_count
        context = prepare_cached_context(
            pending,
            assistant.summary_cache,
            "alice",
            "m3-live",
            assistant.summarizer_fingerprint,
            count_tokens,
            client.generate,
            num_ctx=settings.num_ctx,
            reserved_output=settings.max_tokens,
            summary_tokens=settings.summary_tokens,
            margin=margin,
            keep_pairs=1,
        )
        if client.generate.call_count != before:
            raise AssertionError("Le résumé devrait être réutilisé sans génération.")
        report = {
            "model": settings.model,
            "num_ctx": settings.num_ctx,
            "margin_for_this_test": margin,
            "raw_reference_tokens": raw_count,
            "assembled_reference_tokens": count_tokens(context),
            "server_prompt_eval_count": result.metrics.input_tokens,
            "delta_server_minus_reference": (
                None
                if result.metrics.input_tokens is None
                else result.metrics.input_tokens - count_tokens(context)
            ),
            "covered_until": entry.covered_until,
            "summary": entry.summary_text,
            "answer": result.content,
            "metrics": result.metrics.as_dict(),
            "cached_reuse_without_generation": True,
            "original_messages_saved": len(store.load("alice", "m3-live")),
            "calls": measurements,
        }
        # Mesurer aussi l'appel interne : le template JSON du résumeur peut différer.
        for call in client.generate.call_args_list:
            estimate = count_tokens(call.args[0])
            output = call.kwargs.get("max_tokens", settings.max_tokens)
            if estimate + output + margin > settings.num_ctx:
                raise AssertionError("Un appel dépasse le budget de référence.")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    print("À vérifier : Lina, Lyon, CPU, réponse en anglais et absence d'invention.")
    print("Un écart de comptage demande d'examiner les templates ; ce test ne les certifie pas.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Appeler réellement Ollama local.")
    args = parser.parse_args()
    run_live() if args.live else run_offline()


if __name__ == "__main__":
    main()
