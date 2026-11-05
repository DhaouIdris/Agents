"""M4.1 — charger une source sans perdre son texte ni sa provenance.

Seule load_document est à compléter. Aucun LLM ni dépendance externe nécessaire.
"""

import hashlib  # noqa: F401 -- À utiliser dans le TODO 3.
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    language: str
    version: str
    status: str
    published_on: str
    access_groups: tuple[str, ...]
    source_path: str
    text: str
    content_hash: str


def read_manifest(root):
    """Lire l'inventaire fourni ; son ordre est conservé."""
    path = Path(root) / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_source(root, source_path):
    """Limiter les chemins à un corpus local de confiance ; pas une sandbox complète."""
    base = Path(root).resolve()
    relative = Path(source_path)
    if relative.is_absolute():
        raise ValueError("Le chemin de source doit être relatif au corpus.")
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError("La source doit rester à l'intérieur du corpus.")
    if path.suffix.lower() != ".md":
        raise ValueError("Cette séance accepte uniquement des sources Markdown.")
    return path


def load_document(root, metadata):
    """Renvoie un Document pour une entrée du manifeste, sans modifier metadata.

    Contrat :
    - source_path est résolu par le helper fourni ;
    - lire les octets une seule fois avec path.read_bytes() ;
    - décoder ces octets en UTF-8, sans strip ni remplacement des sauts de ligne ;
    - content_hash est le SHA-256 HEXADÉCIMAL de ces mêmes octets ;
    - recopier les huit champs du manifeste dans Document ;
    - convertir access_groups en tuple ; ajouter text et content_hash.

    Les versions archivées et les groupes sont préservés : charger n'autorise pas
    l'accès et ne signifie pas qu'un document doit être utilisé pour répondre.
    """
    path = resolve_source(root, metadata["source_path"])

    # TODO 1 : lire les octets dans une variable raw.

    # TODO 2 : décoder raw en UTF-8 dans une variable text.

    # TODO 3 : calculer content_hash avec hashlib.sha256(raw).hexdigest().

    # TODO 4 : retourner Document(...) avec ses dix champs nommés.
    # Exemple de correspondance : doc_id=metadata["doc_id"].
    # Le chemin à conserver est metadata["source_path"], pas le chemin absolu path.
    raise NotImplementedError(f"M4.1 : compléter load_document pour {path.name}.")
