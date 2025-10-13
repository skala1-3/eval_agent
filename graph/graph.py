# Agentic RAG v2 - LangGraph flow assembly
# Python 3.11+
#
# [KO] 이 파일은 LangGraph 파이프라인의 "노드/엣지"를 정의합니다.

from __future__ import annotations

from typing import Any, Callable, Optional
import logging

# LangGraph
try:
    from langgraph.graph import StateGraph, END
except Exception as e:  # pragma: no cover
    raise RuntimeError("[graph/graph.py] LangGraph import failed. Please install langgraph.") from e

# Shared state
from .state import PipelineState

logger = logging.getLogger(__name__)


def _fallback_node_factory(name: str) -> Callable[[PipelineState], PipelineState]:
    """Create a no-op node that only logs and returns the state."""

    def _node(state: PipelineState) -> PipelineState:
        logger.info(f"[fallback:{name}] pass-through (no-op)")
        return state

    _node.__name__ = f"fallback_{name}"
    return _node


def _resolve_agent(name: str, dotted: str) -> Callable[[PipelineState], PipelineState]:
    """
    Try to import a callable {Agent}.{__call__ or run}; otherwise return a no-op.
    """
    try:
        module_path, attr = dotted.rsplit(".", 1)
        mod = __import__(module_path, fromlist=[attr])
        obj = getattr(mod, attr)
        node = obj() if isinstance(obj, type) else obj
        if not callable(node):
            raise TypeError(f"{dotted} is not callable")
        logger.info(f"[graph] resolved agent: {dotted}")
        return node
    except Exception as e:  # pragma: no cover
        # ↓ 경고를 정보로 낮춰 노이즈 감소
        logger.info(f"[graph] use fallback for {name} (reason: {e})")
        return _fallback_node_factory(name)


def load_nodes() -> dict[str, Callable[[PipelineState], PipelineState]]:
    """Resolve all pipeline nodes (real agent or fallback)."""
    return {
        "seraph": _resolve_agent("seraph", "agents.seraph_agent.SeraphAgent"),
        "filter": _resolve_agent("filter", "agents.filter_agent.FilterAgent"),
        "augment": _resolve_agent("augment", "agents.augment_agent.AugmentAgent"),
        "rag": _resolve_agent("rag", "agents.rag_retriever_agent.RAGRetrieverAgent"),
        "scoring": _resolve_agent("scoring", "agents.scoring_agent.ScoringAgent"),
        "report": _resolve_agent("report", "agents.report_writer_agent.ReportWriterAgent"),
    }


def build_graph() -> Any:
    """Build and compile the LangGraph pipeline."""
    nodes = load_nodes()

    g = StateGraph(PipelineState)

    g.add_node("seraph", nodes["seraph"])
    g.add_node("filter", nodes["filter"])
    g.add_node("augment", nodes["augment"])
    g.add_node("rag", nodes["rag"])
    g.add_node("scoring", nodes["scoring"])
    g.add_node("report", nodes["report"])

    g.set_entry_point("seraph")

    g.add_edge("seraph", "filter")
    g.add_edge("filter", "augment")
    g.add_edge("augment", "rag")
    g.add_edge("rag", "scoring")
    g.add_edge("scoring", "report")
    g.add_edge("report", END)

    compiled = g.compile()
    return compiled


def run_step_by_step(state: PipelineState) -> PipelineState:
    """
    Debug helper: invoke nodes one by one in linear order.
    Use build_graph() for production runs.
    """
    nodes = load_nodes()
    for key in ("seraph", "filter", "augment", "rag", "scoring", "report"):
        state = nodes[key](state)
    return state
