# M3 — tester le budget, puis construire le cache

Cette fiche conserve les étapes des exercices. Leur implémentation a été poussée
dans `exercises/` ; pour utiliser et valider le parcours intégré, suivre
[la fin de M3](m3_validation.md). Les mentions « à compléter » ci-dessous décrivent
les consignes initiales, pas l'état actuel du package.

Le dépôt GitHub s'appelle maintenant **DhaouIdris/Agents_Chat**. Le dossier local
peut encore s'appeler `Agents` : ce n'est pas un problème. Exécuter les commandes
depuis le dossier qui contient `pyproject.toml` et `test.ipynb`.

## 1. Repères : quel fichier utiliser ?

| Fichier | Utilisation |
| --- | --- |
| `passerelle/memory.py` | Ta fonction corrigée `fit_recent_context` |
| `tests/test_budget.py` | Neuf tests de sélection, sans Ollama ni tokenizer |
| `passerelle/tokens.py` | Compteur Hugging Face, chargé seulement à la demande |
| `scripts/check_token_count.py` | Comparaison facultative du compteur avec Ollama réel |
| `exercises/summary_cache.py` | Code du prochain exercice, à compléter |
| `exercises/test_summary_cache.py` | Tests qui définissent le comportement attendu du cache |

Les corrections du budget et ton implémentation du cache sont présentes. Le package
utilise désormais `passerelle/summary_cache.py`, indépendant du fichier d'exercices.

## 2. Tester le budget depuis le terminal Windows

Si l'environnement `.venv` n'existe pas, le créer une seule fois avec
`py -m venv .venv`. Ensuite :

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_budget.py" -v
```

Résultat attendu : **9 tests, OK**. Le faux compteur donne dix unités par message,
pour tester les décisions de sélection avec des nombres déterministes. Il ne
représente pas la tokenisation réelle du modèle.

La suite complète de vérification du logiciel se lance avec :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les tests du cache inachevé ne font pas partie de cette commande.

## 3. Même test depuis le notebook

Redémarrer le kernel après une modification des modules importés. Vérifier le
kernel utilisé :

```python
import sys
from pathlib import Path

print(sys.executable)
print(Path.cwd())
print("Racine du projet :", Path("pyproject.toml").exists())
```

Le dernier résultat doit être `True`. Ajouter temporairement une cellule :

```python
import subprocess

subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_budget.py", "-v"],
    check=True,
)
```

Cette commande utilise le même interpréteur que le notebook, dans un processus
neuf. Elle évite les anciens imports restés en mémoire.

Pour une inspection manuelle, importer avec
`from passerelle.memory import fit_recent_context`. Écrire les fonctions dans
les modules `.py` ; utiliser le notebook pour appeler et inspecter les résultats.

## 4. Compteur réel : vérification distincte

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[tokenization]"
.\.venv\Scripts\python.exe scripts/check_token_count.py
```

Ollama doit être lancé avec `qwen2.5:3b` installé. Le premier comptage télécharge
le tokenizer Hugging Face, pas les poids du modèle. Le script compare les tokens
du template HF au `prompt_eval_count` serveur, sur de petites requêtes explicites.
Une différence indique un alignement à examiner. Même une égalité sur trois
exemples n'est pas une garantie universelle pour tous les formats de messages.

`Assistant.chat` applique désormais ces contrôles dans son mode `cached` par défaut,
y compris au prompt JSON de résumé et au contexte final assemblé.

## 5. Exercice du cache — partie A : stockage

Ouvrir `exercises/summary_cache.py`. La structure `SummaryCacheEntry`, le calcul
de l'empreinte et la création de table sont fournis. Compléter uniquement :

- `SummaryCache.save` : insertion ou mise à jour d'une ligne, puis commit ;
- `SummaryCache.load` : lecture par utilisateur ET conversation, retour de
  `None` ou d'un objet `SummaryCacheEntry`.

Il faut enregistrer les quatre champs du résumé et fermer les connexions. Les
requêtes doivent utiliser des paramètres `?`. La clé composée interdit de créer
deux lignes pour la même paire d'identifiants.

```powershell
.\.venv\Scripts\python.exe -m unittest exercises.test_summary_cache.CacheStorageTests -v
```

Avant implémentation, **les 6 tests échouent avec NotImplementedError : c'est
attendu**. Le livrable de la partie A est `save`, `load` et six tests réussis.

## 6. Partie B : savoir si le résumé est encore réutilisable

Compléter ensuite `is_cache_valid`. Un cache est valide si son préfixe source
n'a pas changé et si sa configuration de résumé est toujours la même.

`covered_until` est une position EXCLUSIVE dans l'historique, système inclus :

| Historique | Position | Couverture |
| --- | --- | --- |
| `[S, U1, A1, U2]` | `3` | `[S, U1, A1]` |
| `[S, U1, A1, U2, A2, U3]` | `3` | Le même préfixe ; le cache reste réutilisable |
| `[S, U1, A1, U2, A2, U3]` | `5` | `[S, U1, A1, U2, A2]` |

La fonction `source_hash` calcule l'empreinte de `history[:covered_until]`. Dans
cet exercice, `summarizer_fingerprint` est une chaîne stable représentant modèle
et version du prompt ; on y ajoutera les détails de configuration à l'intégration.

```powershell
.\.venv\Scripts\python.exe -m unittest exercises.test_summary_cache.CacheValidityTests -v
```

Résultat attendu après implémentation : **6 tests, OK**. Ajouter des messages
après le préfixe couvert ne doit pas invalider le cache. Modifier un message
couvert, raccourcir la source ou changer la configuration doit l'invalider.

## 7. Intégration suivante, après correction de l'exercice

Le contrôleur charge le cache par utilisateur/conversation. Tant que le résumé
et les échanges non couverts tiennent dans le budget, aucun nouvel appel de
résumé n'est nécessaire. Sinon, cette version régénère un résumé depuis un préfixe
plus long des originaux, sous un budget propre à cet appel. La mise à jour à partir
du résumé précédent et la compression par morceaux restent des extensions.

Un résumé tronqué ou échoué ne devra pas remplacer le dernier cache valide.
L'écriture du texte et des métadonnées de couverture sera atomique. L'historique
brut restera conservé. C'est cette intégration et ses essais qui termineront M3.

