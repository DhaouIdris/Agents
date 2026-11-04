# Passerelle — formation assistants IA

Assistant local développé pendant les modules **M1 à M3** : messages, streaming,
mesures d'inférence, conversations persistantes et résumé du contexte.

Le point d'entrée reste **[test.ipynb](test.ipynb)**. Le notebook contient les
expériences ; les fonctions réutilisables sont dans `passerelle/`. Une fonction
possède désormais une seule définition.

## Installation sous Windows

Dans le dossier du dépôt, avec Python 3.10 ou plus récent :

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[notebook]"
.venv\Scripts\python.exe -m ipykernel install --user --name passerelle --display-name "Passerelle (.venv)"
```

Ouvrir `test.ipynb` dans VS Code et choisir **Passerelle (.venv)** comme kernel.
Pour JupyterLab :

```powershell
.venv\Scripts\jupyter-lab.exe test.ipynb
```

Ouvrir le notebook depuis la racine du dépôt. La base sera alors dans
`data/conversations.db`. Le chemin absolu est affiché dans la configuration.
Pour reprendre une base `conversations.db` créée avec l'ancien notebook,
renseigner son chemin dans `Settings(db_path=...)` : le schéma est compatible.
La réorganisation ne copie ni ne remplace automatiquement une ancienne base.

Sous Linux/macOS, les exécutables de l'environnement sont dans `.venv/bin/`.

## Exécution du notebook

1. Exécuter les cellules dans l'ordre. Par défaut, `RUN_LLM = False` : les
   exemples SQLite et de sélection du contexte fonctionnent sans serveur Ollama.
2. Pour les vrais appels, lancer l'application Ollama, puis installer le modèle
   s'il manque :

   ```powershell
   ollama pull qwen2.5:3b
   ```

3. Passer `RUN_LLM = True` et relancer depuis la cellule de configuration.
4. Activer séparément `RUN_BENCHMARK = True` pour les mesures 512/2048 tokens.

La configuration par défaut reprend le PC du TP : CPU, 8 Go de RAM,
`qwen2.5:3b`, contexte 2048, sortie maximale 128 tokens. Ajuster `Settings` dans
le notebook si nécessaire. Un appel de résumé peut générer jusqu'à 192 tokens.
Le premier appel et les changements de contexte peuvent nécessiter un chargement.

Relancer une cellule de conversation ajoute un nouveau tour : ce n'est pas une
opération idempotente. Le notebook crée un identifiant de démonstration à chaque
exécution de la configuration ; conserver cet identifiant pour reprendre une
conversation après redémarrage. Les exemples de stockage hors ligne utilisent
des identifiants distincts et peuvent être rejoués.

## Où modifier le code ?

| Fichier | Responsabilité |
| --- | --- |
| `passerelle/config.py` | Modèle, contexte, limites, prompts et chemin de base |
| `passerelle/client.py` | HTTP Ollama, streaming et métriques structurées |
| `passerelle/storage.py` | Chargement et sauvegarde SQLite par utilisateur/conversation |
| `passerelle/memory.py` | Validation, fenêtre récente et résumé des anciens messages |
| `passerelle/assistant.py` | Orchestration d'un tour et sauvegarde après succès |
| `test.ipynb` | Expériences M1–M3 et inspection des résultats |
| `tests/` | Tests du protocole, de la mémoire, de la persistance et des échecs |
| `archive/test_original.ipynb` | Notebook fourni, conservé sans sorties pour référence |

```python
from passerelle import Assistant, OllamaClient, Settings, SQLiteStore

settings = Settings()
client = OllamaClient(settings)
store = SQLiteStore(settings.db_path)
assistant = Assistant(client, store)

result = assistant.chat("alice", "discussion-1", "Je m'appelle Lina.", stream=False)
print(result.content)
print(result.metrics.as_dict())
```

`client.generate(...)` remplace les anciennes fonctions `ask` et `ask_stream`.
Il renvoie toujours un `ChatResult` : `content`, `metrics` et `done_reason`.
Le streaming affiche du texte seulement si un callback `on_token` est fourni.
Les résumés internes restent silencieux.

## Stratégies de contexte

| Mode de `assistant.chat(..., mode=...)` | Messages transmis |
| --- | --- |
| `full` | Historique complet ; à réserver aux petites conversations |
| `window` | Système, derniers couples user/assistant, question finale |
| `summary` (défaut) | Système, résumé de la partie ancienne, échanges récents, question finale |

Le résumé est fourni comme données de contexte, sans remplacer les instructions
système. SQLite conserve les messages originaux et non les messages synthétiques
de compaction. Une réponse interrompue, vide ou tronquée n'est pas enregistrée
comme un tour réussi. Des fragments peuvent néanmoins avoir été affichés avant
qu'une interruption soit détectée.

Les validations de rôles couvrent le format M3 : un système suivi de messages
user/assistant alternés. Les outils seront ajoutés dans un module ultérieur.

## Tests

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe scripts/check_notebook.py
```

Les tests utilisent des réponses HTTP simulées et des bases temporaires : ils
vérifient le comportement logiciel, pas la fidélité réelle du modèle. Le contrôle
du notebook exécute toutes ses cellules avec les appels LLM désactivés. La CI
effectue ces contrôles sur Windows et Linux, avec Python 3.10 et 3.12.
Dans un environnement interdisant les sockets locales de Jupyter, le contrôle
alternatif `python scripts/check_notebook.py --in-process` valide le format et
exécute les cellules Python dans l'ordre, sans démarrer de kernel.

## Limites et suite de la formation

- Sélection encore fondée sur le nombre d'échanges : **aucune garantie de budget
  en tokens**. Le résumé peut lui-même recevoir trop d'entrée. Utiliser les petits
  exemples du notebook avant d'ajouter un comptage adapté au modèle.
- Résumé recalculé à chaque appel qui en a besoin ; cache persistant et position
  du dernier message couvert restent la prochaine évolution de M3.
- `user_id` est une identité simulée pour les TP. La clé composée SQLite évite les
  collisions ; elle ne remplace pas l'authentification ni les autorisations.
- Usage séquentiel local : pas de protection contre deux écritures simultanées
  sur la même conversation. Pas de retry automatique après une erreur.
- La fidélité des réponses et des résumés doit être évaluée avec Ollama réel.
  Une suite de tests logicielle ne rend pas cet assistant prêt pour la production.

Le moteur Ollama et les poids du modèle ont des licences distinctes. La version
Qwen2.5-3B-Instruct porte une **Qwen Research License**, pas une licence Apache
générique : consulter [sa licence](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE)
pour le périmètre d'utilisation. Le modèle reste configurable.
