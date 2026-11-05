"""API publique des TP M1–M3. Aucun appel réseau à l'import."""

from .assistant import Assistant
from .client import ChatResult, Metrics, OllamaClient, OllamaError
from .config import SYSTEM_PROMPT, Settings
from .memory import ContextManager, build_context, summarize_history
from .storage import SQLiteStore
from .summary_cache import SummaryCache, SummaryCacheEntry

__all__ = [
    "Assistant",
    "ChatResult",
    "ContextManager",
    "Metrics",
    "OllamaClient",
    "OllamaError",
    "SYSTEM_PROMPT",
    "SQLiteStore",
    "Settings",
    "SummaryCache",
    "SummaryCacheEntry",
    "build_context",
    "summarize_history",
]
