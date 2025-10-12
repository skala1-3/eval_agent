# agents/scoring_agent.py (수정 완료)
# Agentic RAG v2 – ScoringAgent (patched)
# - 7축 점수 산출, confidence 계산, total/decision 결정
# - 엄밀 매칭: 회사 공식 도메인 / 텍스트·URL 경로 회사명 / market 축 태그 특례

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from urllib.parse import urlparse
from datetime import datetime, timedelta
import logging

from graph.state import (
    PipelineState,
    Evidence,
    EvidenceCategory,
    ScoreItem,
    ScoreCard,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 설정 상수
# ... (설정 상수 및 유틸 함수는 이전과 동일) ...
# AXIS_WEIGHTS, STRENGTH_BONUS, ... , _score_axis 함수까지는 변경 없습니다.
# _gather_company_axis_evidence 와 _matches_company 함수는 이제 사용되지 않으므로 삭제해도 됩니다.
# ─────────────────────────────────────────────────────────────

AXIS_WEIGHTS: Dict[EvidenceCategory, int] = {
    "ai_tech": 25,
    "market": 20,
    "traction": 15,
    "moat": 10,
    "risk": 10,
    "team": 10,
    "deployability": 10,
}

STRENGTH_BONUS = {"weak": 1, "medium": 2, "strong": 3}
CONF_RECENCY_MONTHS = 18  # recency 계산 윈도우 (개월)

# coverage 스케일 기준(축별 권장 최소 문장 수)
MIN_ITEMS_FOR_AXIS: Dict[EvidenceCategory, int] = {
    "ai_tech": 3,
    "market": 2,
    "traction": 2,
    "moat": 1,
    "risk": 2,
    "team": 1,
    "deployability": 2,
}

# ─────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────


def _domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _slug(s: str) -> str:
    # "FinChat AI" -> "finchatai"
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _contains_any(text: str, keywords: List[str]) -> bool:
    t = (text or "").lower()
    return any((kw or "").lower() in t for kw in keywords if kw)


def _within_recency(iso_date: Optional[str], months: int) -> bool:
    if not iso_date:
        return False
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", ""))
    except Exception:
        return False
    return (datetime.now() - dt) <= timedelta(days=30 * months)

# ─────────────────────────────────────────────────────────────
# confidence 계산
# ─────────────────────────────────────────────────────────────


@dataclass
class ConfidenceParts:
    coverage: float
    diversity: float
    recency: float


def _calc_confidence(axis_evs: List[Evidence], axis: EvidenceCategory) -> ConfidenceParts:
    if not axis_evs:
        return ConfidenceParts(0.0, 0.0, 0.0)

    # coverage: 축별 최소 권장 문장수 대비 충족도 (클립 0~1)
    min_need = max(1, MIN_ITEMS_FOR_AXIS.get(axis, 2))
    coverage = min(1.0, len(axis_evs) / float(min_need))

    # diversity: 출처 도메인 다양성
    domains = {_domain_of(e.source) for e in axis_evs if e.source}
    diversity = min(1.0, len(domains) / max(1.0, float(len(axis_evs))))

    # recency: 최근 자료 비율 (최근 18개월 내)
    recent_cnt = sum(
        1 for e in axis_evs if _within_recency(getattr(e, "published", None), CONF_RECENCY_MONTHS)
    )
    recency = recent_cnt / float(len(axis_evs))

    return ConfidenceParts(coverage, diversity, recency)


def _blend_confidence(parts: ConfidenceParts) -> float:
    # 규약: 0.4*coverage + 0.3*diversity + 0.3*recency
    return round(0.4 * parts.coverage + 0.3 * parts.diversity + 0.3 * parts.recency, 4)


# ─────────────────────────────────────────────────────────────
# 점수 계산 (신호강도 → 가점 누적, 0~10 클립, 중복출처 가점 억제)
# ─────────────────────────────────────────────────────────────


def _score_axis(axis_evs: List[Evidence]) -> Tuple[float, str]:
    """
    - 동일 도메인에서 같은 strength 반복 시 두 번째부터 0.5 가중 (과대 가점 방지)
    - strength 보너스(weak=1, medium=2, strong=3) 합산 후 0~10 클립
    """
    if not axis_evs:
        return 0.0, "No evidence."

    total = 0.0
    memory: Dict[Tuple[str, str], int] = defaultdict(int)  # (domain, strength) -> count
    for e in axis_evs:
        dom = _domain_of(e.source)
        s = getattr(e, "strength", "weak") or "weak"
        base = STRENGTH_BONUS.get(s, 1)

        key = (dom, s)
        memory[key] += 1
        penalty = 1.0 if memory[key] == 1 else 0.5
        total += base * penalty

    value = max(0.0, min(10.0, total))
    notes = f"{len(axis_evs)} evidences, domains={len({ _domain_of(e.source) for e in axis_evs })}"
    return round(value, 2), notes

# ─────────────────────────────────────────────────────────────
# 의사결정
# ─────────────────────────────────────────────────────────────


def _weighted_total(items: List[ScoreItem]) -> float:
    if not items:
        return 0.0
    # Σ(weight * score) / 100  (score는 0~10, 가중 평균을 0~10 스케일로)
    acc = 0.0
    for it in items:
        w = AXIS_WEIGHTS.get(it.key, 10)
        acc += w * it.value
    return round(acc / 100.0, 2)


def _decide(total: float, items: List[ScoreItem]) -> str:
    if not items:
        return "hold"
    mean_conf = sum(it.confidence for it in items) / len(items)
    # 룰: total >= 7.5 AND mean_conf >= 0.55 → invest
    return "invest" if (total >= 7.5 and mean_conf >= 0.55) else "hold"


# ─────────────────────────────────────────────────────────────
# 메인 에이전트 (이 부분이 수정됩니다)
# ─────────────────────────────────────────────────────────────


class ScoringAgent:
    """Compute 7-axis scores, confidence, total, and decision per company."""

    def __call__(self, state: PipelineState) -> PipelineState:
        if not state.companies or not state.retrieved_evidence:
            logger.warning("ScoringAgent: No companies or retrieved_evidence to score.")
            return state

        scorecards: Dict[str, ScoreCard] = {}
        
        # RAGRetrieverAgent의 결과물을 가져옵니다.
        all_retrieved_evidence = state.retrieved_evidence

        for company in state.companies:
            # <<-- 수정된 부분 1: state.chunks 대신 state.retrieved_evidence 사용
            #    이제 _gather_company_axis_evidence 함수는 필요 없습니다.
            axis_map = all_retrieved_evidence.get(company.id, {})

            items: List[ScoreItem] = []
            for axis in AXIS_WEIGHTS.keys():
                evs = axis_map.get(axis, [])
                value, notes = _score_axis(evs)
                conf_parts = _calc_confidence(evs, axis)
                conf = _blend_confidence(conf_parts)

                items.append(
                    ScoreItem(
                        key=axis,
                        value=value,
                        confidence=round(conf, 3),
                        notes=notes,
                        evidence=evs,  # <<-- 수정된 부분 2: 검색된 근거를 그대로 ScoreItem에 포함
                    )
                )

            total = _weighted_total(items)
            decision = _decide(total, items)

            logger.debug(
                "[Scoring] %s → total=%.2f, decision=%s, axis_counts=%s",
                company.name,
                total,
                decision,
                {k: len(v) for k, v in axis_map.items()},
            )

            scorecards[company.id] = ScoreCard(items=items, total=total, decision=decision)

        state.scorecard.update(scorecards)
        logger.info(f"✅ Scoring complete for {len(scorecards)} companies.")
        return state

"""
python graph/run.py --query "AI financial advisory"

이 방식은 run.py를 단독 스크립트로 실행하는 거라,
Python이 “graph는 패키지가 아니라 그냥 폴더잖아?”라고 인식하게 됩니다.
→ 그래서 상대 임포트(from .graph import ...)가 실패합니다.

=============================================================
python -m graph.run --query "AI financial advisory"

-m 옵션은 “모듈로 실행”을 의미합니다.
이렇게 하면 Python이 eval_agent 폴더를 패키지 루트로 인식해서
from .graph import ... 같은 상대 임포트가 정상 작동합니다.
"""