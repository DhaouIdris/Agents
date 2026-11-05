"""Valider et exécuter le notebook canonique sans Ollama ni modification du fichier."""

import argparse
import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="Exécuter les cellules Python sans kernel Jupyter.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    notebook = nbformat.read(root / "test.ipynb", as_version=4)
    nbformat.validate(notebook)
    if args.in_process:
        # Alternative explicite pour les environnements sans sockets locales.
        # Le notebook canonique ne contient ni magics ni commandes shell.
        namespace = {"__name__": "__main__"}
        previous = Path.cwd()
        try:
            os.chdir(root)
            for index, cell in enumerate(notebook.cells):
                if cell.cell_type == "code":
                    exec(compile(cell.source, f"test.ipynb:cell-{index}", "exec"), namespace)
        finally:
            os.chdir(previous)
        print("Notebook validé ; cellules Python exécutées dans l'ordre, sans kernel Jupyter.")
    else:
        NotebookClient(
            notebook,
            timeout=120,
            kernel_name="python3",
            resources={"metadata": {"path": str(root)}},
        ).execute()
        print("Notebook validé et exécuté dans un kernel Jupyter, sans Ollama.")


if __name__ == "__main__":
    main()
