"""Comparer le compteur HF à Ollama sur des entrées courtes, sans cache de résumé."""

from passerelle import OllamaClient, OllamaError, Settings
from passerelle.tokens import count_tokens


def main():
    client = OllamaClient(Settings())
    samples = [
        [
            {"role": "system", "content": "Réponds brièvement."},
            {"role": "user", "content": "Bonjour."},
        ],
        [
            {"role": "system", "content": "Reply briefly."},
            {"role": "user", "content": "What is a CPU?"},
        ],
        [
            {"role": "system", "content": "Réponds brièvement."},
            {"role": "user", "content": "Je m'appelle Lina."},
            {"role": "assistant", "content": "Bien reçu."},
            {"role": "user", "content": "Comment je m'appelle ?"},
        ],
    ]
    errors = 0
    for index, messages in enumerate(samples, start=1):
        estimated = count_tokens(messages)
        try:
            result = client.generate(messages, max_tokens=8)
        except OllamaError as exc:
            errors += 1
            print(f"Cas {index} : ÉCHEC : {exc}")
            continue
        measured = result.metrics.input_tokens
        delta = None if measured is None else measured - estimated
        print(f"Cas {index} : HF={estimated}, Ollama={measured}, écart serveur-HF={delta}")
    print(
        "Une différence demande de comparer les templates. Une égalité sur ces exemples "
        "ne prouve pas un alignement universel. La sortie générée ici n'est pas évaluée."
    )
    if errors:
        raise SystemExit(f"{errors} appel(s) Ollama en échec ; aucun retry automatique effectué.")


if __name__ == "__main__":
    main()
