"""La connexion de contrôle du test doit être fermée avant le nettoyage Windows."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from exercises import test_summary_cache as cache_tests
from exercises.summary_cache import SummaryCacheEntry


class ExerciseCleanupTests(unittest.TestCase):
    def test_update_check_closes_its_sqlite_connection(self):
        # Le cache est simulé : ce test reste utilisable avant la fin de l'exercice.
        case = cache_tests.CacheStorageTests(
            "test_update_replaces_existing_entry_without_duplicate"
        )
        case.path = Path("unused.db")
        case.cache = Mock()
        case.cache.load.return_value = SummaryCacheEntry(
            "Résumé corrigé.", 3, "new-hash", "prompt-v2"
        )
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = (1,)

        with patch("exercises.test_summary_cache.sqlite3.connect", return_value=connection):
            case.test_update_replaces_existing_entry_without_duplicate()

        connection.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
