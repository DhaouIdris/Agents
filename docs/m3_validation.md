# Fin de M3 — mémoire persistante, budget et cache intégrés

Le parcours par défaut de `Assistant.chat` est maintenant `mode="cached"`.
Les fonctions travaillées sont intégrées dans `passerelle/summary_cache.py` ;
le fichier d'exercices est conservé. On termine la partie logicielle avec les tests
ci-dessous, puis la validation locale du modèle avec Ollama.

## 1. Préparer l'environnement

Depuis la racine du dépôt, après avoir récupéré cette branche :

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,notebook,tokenization]"
```

Dans VS Code, sélectionner le kernel de cet environnement. Si tu gardes ton kernel
Python actuel, installer avec `%pip install -e ".[dev,tokenization]"` dans une cellule,
puis redémarrer ce kernel. L'installation ne fait pas partie des cellules de test.

## 2. Validation logicielle sans Ollama

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest exercises.test_summary_cache -v
.\.venv\Scripts\python.exe scripts/validate_m3.py
```

La suite principale comporte 50 tests ; les deux parties historiques de l'exercice
en comportent 12. La démonstration appelle le vrai `Assistant.chat` et SQLite avec
un générateur et un compteur simulés. Elle doit afficher :

```text
Appels cumulés (résumé + réponse) : [2, 3, 5]
Couverture exclusive du résumé : [5, 5, 9]
```

Le premier tour produit un résumé et une réponse, le deuxième réutilise le résumé,
le troisième actualise sa couverture. Les 13 messages originaux sont conservés.
Les tests couvrent aussi les erreurs, les dépassements, la réouverture et la
séparation utilisateur/conversation. Cela ne mesure pas la fidélité du modèle.

Depuis le notebook, une seule cellule permet de voir les sorties même en cas d'échec :

```python
import subprocess
import sys

commands = [
    ["-m", "unittest", "discover", "-s", "tests", "-v"],
    ["-m", "unittest", "exercises.test_summary_cache", "-v"],
    ["scripts/validate_m3.py"],
]
for arguments in commands:
    check = subprocess.run(
        [sys.executable, *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    print(check.stdout)
    print(check.stderr)
    if check.returncode:
        raise RuntimeError(f"Échec de la vérification : {arguments}")
```

Le notebook `test.ipynb` contient cette validation. Les processus ne réutilisent pas
les anciens imports du kernel.

## 3. Essais réels sur ton CPU — dernière validation à fournir

Ollama doit être lancé et `qwen2.5:3b` installé. Le premier comptage télécharge le
tokenizer Hugging Face, pas les poids du modèle.

```powershell
.\.venv\Scripts\python.exe scripts/check_token_count.py
.\.venv\Scripts\python.exe scripts/validate_m3.py --live
```

Dans le notebook, remplacer les arguments de la cellule précédente par
`["scripts/check_token_count.py"]`, puis `["scripts/validate_m3.py", "--live"]`.

L'essai live utilise des données synthétiques et une base temporaire. Il réserve
volontairement une grande marge pour provoquer la compaction d'une conversation
courte avec `num_ctx=2048`, sans remplir toute la fenêtre. Cette marge de test ne
remplace pas la marge normale de 64. Il vérifie la réutilisation du cache pour le
même contexte et affiche résumé, réponse, comptages et métriques.

Contrôler manuellement :

- Le résumé conserve Lina, Lyon et la contrainte CPU, sans faits inventés.
- La réponse restitue ces faits en anglais, conformément à la dernière demande.
- `cached_reuse_without_generation` vaut `true`.
- Le compteur de référence et `prompt_eval_count` sont comparés sur le contexte
  assemblé, en plus des cas simples de `check_token_count.py`.

Un écart demande d'examiner les templates et le tokenizer avant d'utiliser ce
comptage comme limite stricte. Une égalité sur ces exemples ne prouve pas un
alignement universel. Envoyer les sorties pour corriger les écarts ou les erreurs
de fidélité. Un résumé tronqué peut demander une consigne plus concise ou une
réserve de sortie plus grande, en recalculant les budgets ; ce n'est pas un succès.

## 4. Ce que fait exactement le contrôleur

1. Charger l'historique original et ajouter la nouvelle question en mémoire.
2. Vérifier le budget d'entrée : `num_ctx - max_tokens - margin`.
3. Utiliser l'historique complet s'il tient ; sinon, essayer le cache valide.
4. Si nécessaire, résumer un préfixe de couples complets en gardant `max_pairs`
   couples récents et la dernière question. Le prompt de résumé complet est compté
   avec sa propre réserve `summary_tokens`.
5. Vérifier le contexte reconstruit avant d'enregistrer le nouveau cache.
6. Générer la réponse, puis sauvegarder le tour complet seulement après succès.

Le résumé est une donnée dérivée et approximative. Il conserve le système original
et ne remplace jamais les messages bruts dans SQLite. L'enveloppe « données de
contexte » n'est pas une protection suffisante contre les injections de prompt.

Si le résumeur échoue, est vide, est tronqué ou produit un contexte trop long,
l'ancien cache est conservé. Si le résumé réussit puis la réponse échoue, le résumé
valide peut rester enregistré : son préfixe existe déjà dans l'historique sauvegardé.
L'historique et le cache n'ont pas de transaction commune ; on ne prétend pas ici
garantir une écriture atomique entre ces deux tables.

Les clés comprennent utilisateur ET conversation. L'empreinte source porte sur le
préfixe original, système inclus, avec une fin exclusive après un couple complet.
L'empreinte du résumeur comprend modèle, prompt, paramètres et version. Changer
`summary_version` si les poids derrière un tag changent : le digest n'est pas résolu
automatiquement.

## 5. Limites acceptées pour clôturer ce module

La sélection conserve un nombre fixe de couples récents. La mise à jour repart des
originaux : elle n'utilise pas un résumé précédent pour résumer des blocs nouveaux.
Si le préfixe du résumeur ou le contexte final dépasse, le code refuse explicitement.
La compression par morceaux reste une extension. Les modes historiques `full`,
`window` et `summary` servent aux comparaisons, sans les contrôles du mode `cached`.

Usage local séquentiel, identités simulées, aucun contrôle d'authentification ou de
concurrence. La réussite des tests ne rend pas le système prêt pour la production.

## 6. À retenir

- **Historique** : messages originaux persistants ; **contexte** : messages réellement
  transmis à un appel ; **résumé** : représentation dérivée, avec perte possible.
- Le modèle ne lit pas SQLite : l'application charge et sélectionne les informations.
- Une fenêtre conserve une capacité ; elle ne signifie pas que tous ses tokens
  sont consommés. Compter le template, les rôles et les enveloppes, pas les caractères.
- Réserver la sortie et une marge pour chaque appel, y compris celui du résumeur.
- La validité du cache et sa taille sont deux contrôles distincts. Des messages
  ajoutés après son préfixe ne l'invalident pas, mais peuvent imposer une actualisation.
- Une erreur ne constitue pas un tour réussi ; aucun texte partiel ne doit être
  sauvegardé comme réponse complète.

Après les tests logiciels et l'essai live relu ensemble, M3 est validé. M4 portera
sur le corpus documentaire : ingestion, métadonnées, découpage et provenance, avant
de construire et mesurer la recherche.
