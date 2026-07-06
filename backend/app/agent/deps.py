"""Per-invocation dependencies injected via the LangGraph ``config``.

Nodes read their LLM client and retrieval tool from ``config["configurable"]
["deps"]`` rather than importing singletons, so tests inject fakes (and never touch
Pinecone/Gemini) simply by passing a different :class:`AgentDeps`.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from langchain_core.runnables import RunnableConfig

from app.adapters.llm import LLMClient
from app.adapters.websearch import NullSearch, WebSearch
from app.agent.state import EvidenceChunk

# Re-exported so nodes get the config type without each importing langchain_core
# directly (langgraph's add_node recognizes this annotation for injection).
NodeConfig = RunnableConfig

SearchCorpus = Callable[[str, int], list[EvidenceChunk]]


@dataclass(frozen=True)
class AgentDeps:
    llm: LLMClient
    search_corpus: SearchCorpus
    # Deep-mode web tool; defaults to the disabled null adapter so quick-mode
    # tests and corpus-only deployments need not construct one.
    search_web: WebSearch = field(default_factory=NullSearch)


def get_deps(config: RunnableConfig | None) -> AgentDeps:
    if not config or "configurable" not in config or "deps" not in config["configurable"]:
        raise RuntimeError("AgentDeps missing from graph config['configurable']['deps'].")
    deps = config["configurable"]["deps"]
    if not isinstance(deps, AgentDeps):
        raise RuntimeError("config['configurable']['deps'] is not an AgentDeps.")
    return deps
