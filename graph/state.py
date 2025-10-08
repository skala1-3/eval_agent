# graph/state.py
# Agentic RAG v2 - Pipeline shared data models (Pydantic)
# Python 3.11+, pydantic >= 2.x
#
# [KO] 이 파일은 모든 에이전트가 공유하는 "공통 상태 스키마"를 정의합니다.
#      한국인 팀원 6명이 짧은 기간 내 협업하는 상황을 고려하여,
#      바깥 주석은 한국어로, 내부 docstring은 영어로 작성했습니다.
#      각 에이전트는 자신의 책임 범위 필드만 읽고/추가/수정하세요.

from __future__ import annotations

from typing import Literal, List, Dict, Optional
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────
# [KO] 회사/증거/점수 관련 기본 스키마
#     - CompanyMeta: 발견된 회사의 메타데이터
#     - Evidence: 평가에 사용되는 근거(출처/문장/카테고리/강도)
#     - ScoreItem/ScoreCard: 축별/회사별 점수와 신뢰도, 총점, 의사결정
# ─────────────────────────────────────────────────────────────


class CompanyMeta(BaseModel):
    """Foundational company metadata discovered by Seraph/Filter."""

    # [KO] Seraph/Filter 단계에서 발견된 회사의 기본 정보
    id: str = Field(..., description="Stable identifier (slug or uuid)")
    name: str = Field(..., description="Company display name")
    website: Optional[str] = Field(None, description="Official website url")
    founded_year: Optional[int] = Field(None, ge=1800, le=2100)
    stage: Optional[str] = Field(None, description="Funding stage or lifecycle")
    headcount: Optional[int] = Field(None, ge=0)
    region: Optional[str] = Field(None, description="HQ region or primary market")
    tags: List[str] = Field(default_factory=list, description="Keywords/labels")


# [KO] 증거 카테고리/강도는 고정된 리터럴로 선언하여 실수를 줄입니다.
EvidenceCategory = Literal[
    "ai_tech", "market", "traction", "moat", "risk", "team", "deployability"
]
EvidenceStrength = Literal["weak", "medium", "strong"]


class Evidence(BaseModel):
    """Normalized snippet used for scoring with traceable source."""

    # [KO] 평가에 사용되는 근거(문장) 단위. 출처(URL/파일 경로)와 카테고리, 강도를 반드시 포함.
    source: str = Field(..., description="URL or file path")
    text: str = Field(..., description="Quoted or summarized evidence text")
    category: EvidenceCategory
    strength: EvidenceStrength = "weak"
    published: Optional[str] = Field(
        None, description="ISO date string if known (e.g., '2025-07-14')"
    )


class ScoreItem(BaseModel):
    """Axis-level score with confidence and attached evidences."""

    # [KO] 개별 축(ai_tech 등)의 점수/신뢰도와 근거 목록
    key: EvidenceCategory
    value: float = Field(0.0, ge=0.0, le=10.0, description="Axis score on 0–10")
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    notes: str = Field("", description="1–2 line summary note")
    evidence: List[Evidence] = Field(default_factory=list)


# [KO] 회사별 의사결정: 투자/보류/조건부
DecisionType = Literal["invest", "hold", "conditional"]


class ScoreCard(BaseModel):
    """Per-company score aggregation."""

    # [KO] 회사 단위로 축별 점수를 합친 결과. 총점과 최종 의사결정을 포함.
    items: List[ScoreItem] = Field(default_factory=list)
    total: float = Field(0.0, ge=0.0, le=10.0)
    decision: DecisionType = "hold"


# ─────────────────────────────────────────────────────────────
# [KO] 파이프라인 상태(PipelineState)
#     - LangGraph 노드 간에 전달되는 공통 상태
#     - 각 에이전트는 자신 책임 영역의 필드만 수정
# ─────────────────────────────────────────────────────────────


class PipelineState(BaseModel):
    """
    Shared state flowing through LangGraph nodes.
    Each agent SHOULD read/append/update only its responsibility.
    """

    # [KO] 입력 질의(예: "AI financial advisory startup")
    query: str = Field(
        ..., description="Discovery query (e.g., 'AI financial advisory startup')"
    )

    # [KO] Discovery/Filter 단계 결과: 후보 회사 목록
    companies: List[CompanyMeta] = Field(default_factory=list)

    # [KO] Augment 단계 결과: 크롤링/정제/라벨링 후 적재된 근거(청크) 풀
    chunks: List[Evidence] = Field(default_factory=list)

    # [KO] Scoring 단계 결과: 회사별 ScoreCard (key: company_id)
    scorecard: Dict[str, ScoreCard] = Field(default_factory=dict)

    # [KO] Report 단계 결과: 회사별 출력물 경로 (예: PDF 파일 경로)
    reports: Dict[str, str] = Field(default_factory=dict)


__all__ = [
    "CompanyMeta",
    "Evidence",
    "EvidenceCategory",
    "EvidenceStrength",
    "ScoreItem",
    "ScoreCard",
    "DecisionType",
    "PipelineState",
]
