"""Verify (Phase 1 stub).

The real claim-audit lands in Phase 2. For now it returns no claims so the graph
shape and finalize logic are exercised end-to-end.
"""

from typing import Any

from app.agent.deps import NodeConfig
from app.agent.state import ResearchState


def verify(state: ResearchState, config: NodeConfig) -> dict[str, Any]:
    return {"claims": []}
