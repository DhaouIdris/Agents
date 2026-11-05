"""Comparer le compteur HF à Ollama sur des entrées courtes, sans cache de résumé."""

from passerelle import OllamaClient, Settings
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
    for index, messages in enumerate(samples, start=1):
        estimated = count_tokens(messages)
        result = client.generate(messages, max_tokens=8)
        measured = result.metrics.input_tokens
        delta = None if measured is None else measured - estimated
        print(f"Cas {index} : HF={estimated}, Ollama={measured}, écart serveur-HF={delta}")
    print(
        "Une différence demande de comparer les templates. Une égalité sur ces exemples "
        "ne prouve pas un alignement universel. La sortie générée ici n'est pas évaluée."
    )


if __name__ == "__main__":
    main()
