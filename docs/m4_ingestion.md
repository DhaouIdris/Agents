# M4 — construire un corpus traçable avant la recherche

Objectif : transformer des sources en documents puis en passages que l'on pourra
retrouver, contrôler et citer. Pour cette étape, Python standard suffit ; aucun
appel à Ollama, embedding ou serveur vectoriel n'est nécessaire sur ton PC de 8 Go.

Les documents décrivent l'Agence Passerelle, une organisation fictive. Les règles,
dates, groupes et codes sont entièrement synthétiques : aucune politique réelle
ni donnée personnelle n'est reproduite.

## Parcours et critères

| Séance | Objectif et prérequis | Livrable et critère de passage | Temps estimé |
| --- | --- | --- | --- |
| M4.1 — ingestion | Path, octets/UTF-8, métadonnées, SHA-256 ; Python et dataclass vus en M3 | load_document et 8 tests réussis ; source préservée à l'identique | 30–60 min |
| M4.2 — découpage | Documents validés ; paragraphes, titres, taille et recouvrement | Passages avec provenance et positions ; chaque extrait correspond exactement à une tranche de source | 60–90 min |
| M4.3 — préparation de l'index | Passages validés ; versions, statuts et mise à jour | Export inspectable, sans doublons ; une source modifiée est détectée et la version archivée identifiée | 60–90 min |

Ces durées sont des estimations de travail, pas des durées de vidéos. Le choix de
taille des passages sera mesuré avec les questions et le contexte disponible ; il
n'existe pas une taille universelle à appliquer sans évaluation. La recherche et
ses métriques commenceront ensuite en M5.

## Le corpus fourni

L'inventaire est `corpus/passerelle/manifest.json`. Les six fichiers Markdown sont
listés explicitement : un fichier présent dans un dossier n'est pas automatiquement
une source à indexer.

| Source | Langue | Particularité pour les futurs tests |
| --- | --- | --- |
| teletravail-fr-v2 | FR | Politique actuelle : jusqu'à deux jours, avec approbation |
| teletravail-en-v2 | EN | Même règle dans une autre langue |
| teletravail-fr-v1 | FR | Ancienne règle d'un jour, version archivée |
| demandes-fr-v1 | FR | Confirmation avant soumission ; le statut individuel vient d'un outil |
| demandes-en-v1 | EN | Guide équivalent en anglais |
| note-rh-fr-v1 | FR | Métadonnée de diffusion limitée au groupe RH |

Le manifeste distingue l'identifiant documentaire, le titre, la langue, la version,
le statut, la date de publication, les groupes autorisés et le chemin relatif.
`doc_id` est un identifiant fourni pour cette version, pas un hash ni un nom généré
par le modèle. `content_hash` sera calculé depuis le fichier effectivement lu.
Un changement de contenu ne doit pas changer silencieusement les métadonnées ;
il doit être détectable pour décider ensuite d'une mise à jour de l'index.

Les groupes sont des annotations pédagogiques, pas une autorisation implémentée.
Le chargeur doit les conserver, y compris pour un document RH ou archivé. Plus tard,
le serveur authentifié filtrera les résultats avant leur transmission au modèle.
Un prompt demandant de respecter les droits ne remplace pas ce filtrage.

## Exercice M4.1 : une seule fonction à compléter

Ouvrir `exercises/ingestion.py` et compléter **uniquement `load_document`**.
Les helpers `read_manifest` et `resolve_source`, ainsi que la dataclass `Document`,
sont fournis. Les métadonnées de ce TP proviennent du manifeste de confiance.

1. Lire les octets du fichier résolu avec `path.read_bytes()` dans `raw`.
2. Décoder ces mêmes octets avec UTF-8 dans `text`.
3. Calculer le SHA-256 hexadécimal de `raw` dans `content_hash`.
4. Construire et retourner un `Document` avec les huit champs du manifeste,
   puis `text` et `content_hash`. Convertir `access_groups` en tuple.

Ne pas appliquer `.strip()`, remplacer les retours à la ligne ni résumer le contenu.
Préserver d'abord la source rendra les positions et citations vérifiables. Si un
texte nettoyé devient nécessaire, il sera une représentation dérivée distincte.

Le chemin conservé dans `Document.source_path` est celui du manifeste, relatif au
corpus. Le chemin absolu résolu sert à lire, sans rendre l'index dépendant du chemin
Windows de ton ordinateur. Le helper refuse les sorties de corpus et les formats
non pris en charge ; ce contrôle local n'est pas une sandbox pour des uploads hostiles.

Le SHA-256 détecte un changement d'octets. Il ne prouve ni la vérité du document ni
l'identité de son auteur. Des fins de ligne différentes donnent des octets différents :
les tests vérifient le hash de la source lue, pas un hash supposé identique à chaque checkout.

Le squelette ne contient volontairement pas la solution. Remplacer le
`raise NotImplementedError(...)` final par le retour du document une fois les TODO complétés.

## Tester dans le notebook

Ouvrir **m4.ipynb depuis la racine du dépôt**, avec le kernel Python habituel. Les
premières cellules affichent le manifeste sans utiliser le chargeur inachevé.
Après avoir écrit et enregistré ta fonction, passer `RUN_EXERCISE = True` puis
relancer les cellules. Le notebook utilise `importlib.reload` pour l'inspection et
un processus neuf pour les tests, avec les sorties d'erreur complètes.

La commande équivalente dans le terminal est :

```powershell
python -m unittest exercises.test_ingestion.LoadDocumentTests -v
```

Avant l'implémentation, plusieurs tests échouent avec `NotImplementedError` : c'est
attendu. Après implémentation, les **8 tests** doivent passer. Ils vérifient les
métadonnées, accents et fins de ligne, le hash des octets, l'absence de mutation,
les statuts/groupes, les fichiers absents, l'UTF-8 invalide et les chemins sortants.
La suite CI générale ne lance pas le chargeur à compléter. Elle vérifie seulement
que les documents et le manifeste fournis sont cohérents, et que le notebook
s'exécute avec `RUN_EXERCISE = False`.

Puis charger le corpus dans une cellule :

```python
documents = [ingestion.load_document(root, meta) for meta in manifest]
print(len(documents))
print(documents[0].doc_id, documents[0].language)
print(documents[0].content_hash)
```

Le livrable à envoyer : ta fonction et la sortie des 8 tests. Nous examinerons
ensuite la différence entre identifier une source, détecter sa modification et
retrouver un passage précis avant de commencer le découpage.

## Ressources vérifiées pour cette séance

Ressource principale : [documentation Python 3.12 — pathlib](https://docs.python.org/fr/3.12/library/pathlib.html#pathlib.Path.read_bytes).
Organisme : projet CPython / Python Software Foundation. Français avec des passages
anglais ; niveau débutant/intermédiaire en entrées-sorties. Lire seulement `Path`,
`read_bytes`, `read_text` et `resolve`. Après lecture : lire une source locale et
expliquer la différence entre octets, texte décodé et chemin résolu.

Complément facultatif : [documentation Python 3.12 — hashlib](https://docs.python.org/fr/3.12/library/hashlib.html#hashlib.sha256).
Même organisme, français partiel/anglais ; niveau intermédiaire. Lire « Utilisation »,
`sha256` et `hexdigest`. Après lecture : calculer une empreinte sur les octets et
expliquer ce qu'elle détecte, sans la confondre avec une preuve de qualité documentaire.

Liens ouverts et vérifiés le 5 novembre 2026. La référence 3.12 correspond à ton
environnement ; les API utilisées sont également disponibles dans le minimum 3.10
du projet. Aucun framework supplémentaire ni vidéo non vérifiée n'est requis.
