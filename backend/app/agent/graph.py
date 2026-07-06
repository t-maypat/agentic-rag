"""LangGraph assembly for the research agent.

Routing is expressed two ways: static edges for the linear spine, and dynamic
``Command(goto=...)`` returned by intake (route/mode) and grade (loop/budget).
Compiled once with a SqliteSaver so Deep-mode follow-ups share thread state.

LangGraph imports are deliberately confined to this module + the checkpointer
setup, so an API churn blast radius stays small (REVAMP_PLAN §16).
"""

from langgraph.graph import END, START, StateGraph

from app.agent import nodes
from app.agent.state import ResearchState


def build_graph() -> StateGraph:
    builder = StateGraph(ResearchState)

    builder.add_node("intake", nodes.intake)
    builder.add_node("plan", nodes.plan)
    builder.add_node("retrieve", nodes.retrieve)
    builder.add_node("grade", nodes.grade)
    builder.add_node("rewrite", nodes.rewrite)
    builder.add_node("synthesize", nodes.synthesize)
    builder.add_node("verify", nodes.verify)
    builder.add_node("finalize", nodes.finalize)

    builder.add_edge(START, "intake")
    # intake → {plan, retrieve, finalize} via Command
    builder.add_edge("plan", "retrieve")
    builder.add_edge("retrieve", "grade")
    # grade → {rewrite, synthesize, finalize} via Command
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("synthesize", "verify")
    builder.add_edge("verify", "finalize")
    builder.add_edge("finalize", END)

    return builder


def compile_graph(checkpointer=None):
    return build_graph().compile(checkpointer=checkpointer)
