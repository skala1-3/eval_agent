# graph/graph.py
# Agentic RAG v2 - LangGraph flow assembly
# Python 3.11+
#
# [KO] 이 파일은 LangGraph 파이프라인의 "노드/엣지"를 정의합니다.
#      - 팀원이 agents/* 를 아직 구현하지 않아도 최소 실행이 되도록
#        안전한 fallback(더미) 노드를 제공합니다.
#      - 실제 에이전트가 준비되면 자동으로 해당 구현을 사용합니다.
#      - 파이프라인은 다음 순서로 흐릅니다:
#        Seraph → Filter → Augment → RAG → Scoring → Report → END
#
#      ※ 주의: 여기서는 "흐름"만 정의합니다. 각 Agent의 상세 로직은 agents/* 내부에서 구현하세요.

from __future__ import annotations

from typing import Any, Callable, Optional
import logging

# LangGraph
try:
    from langgraph.graph import StateGraph, END
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "[graph/graph.py] LangGraph import failed. Please install langgraph."
    ) from e

# Shared state
from .state import PipelineState

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# [KO] Fallback(더미) 노드 구현
#     - 실제 agents/* 모듈이 없을 때도 파이프라인이 최소한으로 흘러가도록 보장
#     - 각 더미 노드는 입력 state를 그대로 반환하며 로그만 남깁니다.
# ─────────────────────────────────────────────────────────────


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

    Expected agent interface (one of):
      - class SeraphAgent: def __call__(self, state: PipelineState) -> PipelineState
      - def seraph_node(state: PipelineState) -> PipelineState
    """
    try:
        module_path, attr = dotted.rsplit(".", 1)
        mod = __import__(module_path, fromlist=[attr])
        obj = getattr(mod, attr)
        # If it's a class, instantiate; else assume callable
        node = obj() if isinstance(obj, type) else obj
        # Probe callability
        if not callable(node):
            raise TypeError(f"{dotted} is not callable")
        logger.info(f"[graph] resolved agent: {dotted}")
        return node
    except Exception as e:  # pragma: no cover
        logger.warning(f"[graph] use fallback for {name} (reason: {e})")
        return _fallback_node_factory(name)


# ─────────────────────────────────────────────────────────────
# [KO] 에이전트 노드 로딩
#     - 실제 구현이 있으면 사용, 없으면 fallback을 사용
#     - 기본 경로는 agents.{file}.{callable} 형태로 가정
# ─────────────────────────────────────────────────────────────


def load_nodes() -> dict[str, Callable[[PipelineState], PipelineState]]:
    """Resolve all pipeline nodes (real agent or fallback)."""
    return {
        "seraph": _resolve_agent("seraph", "agents.seraph_agent.SeraphAgent"),
        "filter": _resolve_agent("filter", "agents.seraph_agent.FilterAgent"),
        "augment": _resolve_agent("augment", "agents.augment_agent.AugmentAgent"),
        "rag": _resolve_agent("rag", "agents.rag_retriever_agent.RAGRetrieverAgent"),
        "scoring": _resolve_agent("scoring", "agents.scoring_agent.ScoringAgent"),
        "report": _resolve_agent(
            "report", "agents.report_writer_agent.ReportWriterAgent"
        ),
    }


# ─────────────────────────────────────────────────────────────
# [KO] 그래프 구성
#     - StateGraph(PipelineState) 기반으로 노드/엣지/엔트리를 설정
#     - compile() 결과(ExecutableGraph)를 반환
# ─────────────────────────────────────────────────────────────


def build_graph() -> Any:
    """Build and compile the LangGraph pipeline."""
    nodes = load_nodes()

    g = StateGraph(PipelineState)

    # Register nodes (각 노드 이름은 아래 edges에서 참조됩니다)
    g.add_node("seraph", nodes["seraph"])
    g.add_node("filter", nodes["filter"])
    g.add_node("augment", nodes["augment"])
    g.add_node("rag", nodes["rag"])
    g.add_node("scoring", nodes["scoring"])
    g.add_node("report", nodes["report"])

    # Entry point
    g.set_entry_point("seraph")

    # Edges: Seraph → Filter → Augment → RAG → Scoring → Report → END
    g.add_edge("seraph", "filter")
    g.add_edge("filter", "augment")
    g.add_edge("augment", "rag")
    g.add_edge("rag", "scoring")
    g.add_edge("scoring", "report")
    g.add_edge("report", END)

    compiled = g.compile()
    return compiled


# ─────────────────────────────────────────────────────────────
# [KO] 외부에서 import 시 편의 함수
#     - run_step_by_step: 디버그용 단일 호출 유틸
# ─────────────────────────────────────────────────────────────


def run_step_by_step(state: PipelineState) -> PipelineState:
    """
    Debug helper: invoke nodes one by one in linear order.
    Use build_graph() for production runs.
    """
    nodes = load_nodes()
    for key in ("seraph", "filter", "augment", "rag", "scoring", "report"):
        state = nodes[key](state)
    return state
