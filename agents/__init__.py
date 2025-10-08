# agents/__init__.py
# Agentic RAG v2 - Agent registry (optional imports + safe fallbacks)
#
# [KO] 이 파일은 agents 하위 모듈의 "개발 편의용 레지스트리"입니다.
#      - 팀원이 아직 각 에이전트를 구현하지 않아도 import 에러가 나지 않도록
#        안전한 No-Op(통과) 에이전트를 제공합니다.
#      - graph/graph.py는 각 모듈을 직접 import하고 실패 시 자체 fallback을 사용하므로,
#        이 파일은 주로 "대화형 테스트/IDE 자동완성/로컬 유틸"에 도움을 줍니다.
#
#      권장 구현 파일:
#        - agents/seraph_agent.py          (SeraphAgent, FilterAgent)
#        - agents/augment_agent.py         (AugmentAgent)
#        - agents/rag_retriever_agent.py   (RAGRetrieverAgent)
#        - agents/scoring_agent.py         (ScoringAgent)
#        - agents/report_writer_agent.py   (ReportWriterAgent)
#
#      각 에이전트는 __call__(state: PipelineState) -> PipelineState 형태를 권장합니다.

from __future__ import annotations

from typing import Callable, Dict, Any
import logging

# [KO] 공통 상태 타입 (docstring 및 타입힌트 목적)
try:
    from graph.state import PipelineState  # type: ignore
except Exception:  # pragma: no cover
    PipelineState = Any  # fallback for type checkers when path differs

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# [KO] No-Op(통과) 에이전트
# ─────────────────────────────────────────────────────────────


class _NoOpAgent:
    """A pass-through agent used when actual implementation is missing."""

    # [KO] 실제 에이전트가 없을 때 임시로 사용하는 통과 에이전트입니다.
    def __init__(self, name: str):
        self.name = name

    def __call__(self, state: PipelineState) -> PipelineState:
        logger.info(f"[agents] {_NoOpAgent.__name__}('{self.name}') pass-through")
        return state


# ─────────────────────────────────────────────────────────────
# [KO] 개별 에이전트 임포트 (실패 시 No-Op 대체)
# ─────────────────────────────────────────────────────────────


def _try_import(module_path: str, attr: str, fallback_name: str):
    """Import helper that returns a callable agent or a No-Op fallback."""
    try:
        mod = __import__(module_path, fromlist=[attr])
        obj = getattr(mod, attr)
        agent = obj() if isinstance(obj, type) else obj
        if callable(agent):
            return agent
        raise TypeError(f"{module_path}.{attr} is not callable")
    except Exception as e:  # pragma: no cover
        logger.warning(f"[agents] fallback -> {fallback_name} (reason: {e})")
        return _NoOpAgent(fallback_name)


# [KO] 권장 네이밍: 실제 구현이 있으면 해당 객체, 없으면 No-Op 반환
SeraphAgent = _try_import("agents.seraph_agent", "SeraphAgent", "SeraphAgent")
FilterAgent = _try_import("agents.seraph_agent", "FilterAgent", "FilterAgent")
AugmentAgent = _try_import("agents.augment_agent", "AugmentAgent", "AugmentAgent")
RAGRetrieverAgent = _try_import(
    "agents.rag_retriever_agent", "RAGRetrieverAgent", "RAGRetrieverAgent"
)
ScoringAgent = _try_import("agents.scoring_agent", "ScoringAgent", "ScoringAgent")
ReportWriterAgent = _try_import(
    "agents.report_writer_agent", "ReportWriterAgent", "ReportWriterAgent"
)


# ─────────────────────────────────────────────────────────────
# [KO] 개발 편의용 레지스트리 (선택)
# ─────────────────────────────────────────────────────────────

REGISTRY: Dict[str, Callable[[PipelineState], PipelineState]] = {
    "seraph": SeraphAgent,
    "filter": FilterAgent,
    "augment": AugmentAgent,
    "rag": RAGRetrieverAgent,
    "scoring": ScoringAgent,
    "report": ReportWriterAgent,
}

__all__ = [
    "SeraphAgent",
    "FilterAgent",
    "AugmentAgent",
    "RAGRetrieverAgent",
    "ScoringAgent",
    "ReportWriterAgent",
    "REGISTRY",
]
