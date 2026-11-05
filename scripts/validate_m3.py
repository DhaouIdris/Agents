"""Validation M3 : démonstration hors ligne ou essai explicite avec Ollama local."""

import argparse
import json
import re
import tempfile
from pathlib import Path
from unittest.mock import Mock

from passerelle import Assistant, ChatResult, Metrics, OllamaClient, Settings, SQLiteStore
from passerelle.config import SYSTEM_PROMPT
from passerelle.summary_cache import (
    SummaryCacheEntry,
    context_from_cache,
    prepare_cached_context,
    source_hash,
)


def check_fixture_facts(text):
    """Smoke lexical propre à cette fixture ; ni juge sémantique ni contrôle de production."""
    lowered = text.casefold()
    counts = re.findall(r"\b(\d+)\s+(?:dossiers?|files?|records?)\b", lowered)
    return {
        "name_present": bool(re.search(r"\blina\b", lowered)),
        "city_present": bool(re.search(r"\blyon\b", lowered)),
        "hardware_present": bool(re.search(r"\b(cpu|processor|processeur)\b", lowered)),
        "record_count_claim_consistent": all(int(n) == 25 for n in counts),
    }


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


def run_live(*, diagnose=False):
    """Données synthétiques, DB temporaire, vrai tokenizer et vrais appels Ollama."""
    from passerelle.tokens import count_tokens

    settings = Settings()
    client = OllamaClient(settings)
    original_generate = client.generate
    measurements = []
    active_margin = 64
    phase = None

    def measured_generate(messages, **kwargs):
        estimate = count_tokens(messages)
        result = original_generate(messages, **kwargs)
        measured = result.metrics.input_tokens
        measurements.append(
            {
                "kind": phase or ("summary" if "max_tokens" in kwargs else "answer"),
                "reference_tokens": estimate,
                "server_prompt_eval_count": measured,
                "delta_server_minus_reference": None if measured is None else measured - estimate,
                "reserved_output": kwargs.get("max_tokens", settings.max_tokens),
                "margin": active_margin,
                "truncated": result.truncated,
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
    diagnostics = {}
    if diagnose:
        # Deux contrôles : les originaux, puis une note correcte écrite pour la fixture.
        # Cette note n'est jamais utilisée comme résumé produit par le système.
        phase = "full_history_baseline"
        baseline = client.generate(pending, stream=False)
        diagnostics[phase] = {
            "answer": baseline.content,
            "facts": check_fixture_facts(baseline.content),
            "truncated": baseline.truncated,
        }
        reference = SummaryCacheEntry(
            "Utilisateur : Lina. Lieu de travail : Lyon. Matériel : CPU uniquement.",
            3,
            source_hash(pending, 3),
            "fixture-reference-only",
        )
        phase = "reference_summary_baseline"
        baseline = client.generate(context_from_cache(pending, reference), stream=False)
        diagnostics[phase] = {
            "answer": baseline.content,
            "facts": check_fixture_facts(baseline.content),
            "truncated": baseline.truncated,
        }
    phase = None
    active_margin = margin
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
            "summary_fact_checks": check_fixture_facts(entry.summary_text),
            "answer_fact_checks": check_fixture_facts(result.content),
            "diagnostics": diagnostics,
            "manual_review_required": True,
        }
        # Mesurer aussi l'appel interne : le template JSON du résumeur peut différer.
        for call in measurements:
            if (
                call["reference_tokens"] + call["reserved_output"] + call["margin"]
                > settings.num_ctx
            ):
                raise AssertionError("Un appel dépasse le budget de référence.")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    print("À vérifier : Lina, Lyon, CPU, réponse en anglais et absence d'invention.")
    print("Un écart de comptage demande d'examiner les templates ; ce test ne les certifie pas.")
    facts_ok = all(report["summary_fact_checks"].values()) and all(
        report["answer_fact_checks"].values()
    )
    counts_ok = all(call["delta_server_minus_reference"] == 0 for call in measurements)
    complete = not any(call["truncated"] for call in measurements)
    if not (facts_ok and counts_ok and complete):
        raise SystemExit(
            "Échec du smoke test : examiner les faits, les comptages ou la troncature."
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Appeler réellement Ollama local.")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Avec --live : ajouter deux réponses témoins (originaux et résumé de référence).",
    )
    args = parser.parse_args()
    if args.diagnose and not args.live:
        parser.error("--diagnose nécessite --live")
    run_live(diagnose=args.diagnose) if args.live else run_offline()


if __name__ == "__main__":
    main()
