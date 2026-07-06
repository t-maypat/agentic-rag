"""Process-wide agent runtime: compiled graph, deps, and the SQLite checkpointer.

Lazily initialized (needs a Gemini key and touches Pinecone), so unit tests that
build their own graph with fake deps never trigger it.
"""

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from app.adapters.llm import GeminiLLM
from app.agent.deps import AgentDeps
from app.agent.graph import compile_graph
from app.agent.tools import search_corpus
from app.core.config import settings

_REPO_ROOT = Path(__file__).resolve().parents[3]

_graph: Any = None
_deps: AgentDeps | None = None


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else _REPO_ROOT / path


def init_runtime() -> None:
    global _graph, _deps
    if _graph is not None:
        return
    db_path = _resolve(settings.threads_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    _graph = compile_graph(checkpointer=checkpointer)
    _deps = AgentDeps(llm=GeminiLLM(settings.gemini_api_key), search_corpus=search_corpus)


def get_graph() -> Any:
    if _graph is None:
        init_runtime()
    return _graph


def get_deps() -> AgentDeps:
    if _deps is None:
        init_runtime()
    assert _deps is not None
    return _deps
