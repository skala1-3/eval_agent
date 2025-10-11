# tests/test_scoring_agent_full.py
# Run:
#   PYTHONPATH=. uv run pytest -s -q
#      └─ -s 로 캡처 해제: 성공해도 테이블 출력됨
#   PYTHONPATH=. uv run pytest -s -k full_7_axes_invest
#      └─ 7개 축을 사용한 테스트만


from graph.state import PipelineState, CompanyMeta, Evidence
from agents.scoring_agent import ScoringAgent

# ── pretty print (성공/실패 상관없이 점수표 보여주기용)
from rich.console import Console
from rich.table import Table

console = Console()


def _print_scorecard(title: str, sc):
    table = Table(title=f"{title} — total={sc.total:.2f}, decision={sc.decision}", show_lines=True)
    table.add_column("Axis", justify="left", style="bold cyan")
    table.add_column("Score", justify="right")
    table.add_column("Conf", justify="right")
    table.add_column("#Ev", justify="right")
    table.add_column("Notes", justify="left")

    for it in sc.items:
        table.add_row(
            it.key,
            f"{it.value:.2f}",
            f"{it.confidence:.2f}",
            str(len(it.evidence)),
            it.notes,
        )
    console.print(table)


# ── 테스트 고정값/헬퍼들 ─────────────────────────────────────────


def make_company():
    # market 특례(tags)는 ScoringAgent의 엄밀 매칭에서 사용됨
    return CompanyMeta(
        id="finchat",
        name="FinChat AI",
        website="https://finchat.ai",
        tags=["RIA", "Wealth", "US"],
    )


def E(src, txt, cat, strength="strong", pub="2025-06-01"):
    # 텍스트에 "FinChat AI" 전체 이름을 명시해 텍스트 매칭 확실히 통과
    return Evidence(
        source=src,
        text=f"FinChat AI — {txt}",
        category=cat,
        strength=strength,
        published=pub,
    )


# ── 테스트 1: 7축 모두 채워서 invest 조건 충족 ───────────────────


def test_scoring_full_7_axes_invest():
    evidences = [
        # ai_tech (3 strong, 서로 다른 도메인) → 축점수 ≈ 9
        E("https://finchat.ai/tech", "Model card with evals and guardrails.", "ai_tech"),
        E("https://arxiv.org/abs/2505.00001", "Benchmark SOTA vs peers.", "ai_tech"),
        E("https://github.com/finchat-ai/guard", "Safety guard OSS.", "ai_tech"),
        # market (3 strong, 서로 다른 도메인) → 축점수 ≈ 9
        E("https://financeai.co/report", "US RIA CAGR 18% (TAM/SAM).", "market"),
        E("https://www.mckinsey.com/insights/ai/fin-advisory", "Segment growth.", "market"),
        E("https://www.gartner.com/research/fintech-ai", "Leaders & category outlook.", "market"),
        # traction (3 strong) → 축점수 ≈ 9
        E("https://techcrunch.com/finchat", "Series A; ACV disclosed.", "traction"),
        E("https://sequoia.com/portfolio/finchat", "Ref customers & growth.", "traction"),
        E("https://customers.finchat.ai/case", "Paid logos; MAU/retention.", "traction"),
        # moat (2 strong) → 축점수 ≈ 6
        E("https://patents.google.com/patent/US1234567", "Patent granted.", "moat"),
        E("https://regulator.gov/eligibility/finchat", "Regulatory eligibility.", "moat"),
        # risk (3 strong) → 축점수 ≈ 9
        E("https://finchat.ai/security", "FINRA/SEC compliant; DLP.", "risk"),
        E("https://www.iso.org/cert/finchat", "ISO/IEC certification.", "risk"),
        E("https://dpa.finchat.ai", "DPA & privacy docs.", "risk"),
        # team (2 strong) → 축점수 ≈ 6
        E("https://www.linkedin.com/in/ceo", "Ex-FAANG; fintech exit.", "team"),
        E("https://finchat.ai/team", "AI+Finance track record.", "team"),
        # deployability (3 strong) → 축점수 ≈ 9
        E("https://finchat.ai/docs", "API/SLA/observability.", "deployability"),
        E("https://status.finchat.ai", "SLOs & ops maturity.", "deployability"),
        E("https://finops.dev/guides/finchat", "Multi-region, data boundaries.", "deployability"),
    ]

    state = PipelineState(
        query="AI financial advisory startup", companies=[make_company()], chunks=evidences
    )
    sc = ScoringAgent()(state).scorecard["finchat"]

    # 성공해도 항상 표를 출력
    _print_scorecard("Scoring — Full 7 Axes", sc)

    # 총점/신뢰도/결정 검증 (도메인/강도·페널티에 따른 약간의 오차 허용)
    assert 8.3 <= sc.total <= 8.6, f"unexpected total={sc.total}"
    mean_conf = sum(i.confidence for i in sc.items) / len(sc.items or [1])
    assert mean_conf >= 0.9, f"mean_conf too low: {mean_conf}"
    assert sc.decision == "invest"


# ── 테스트 2: 일부 축만 채워져 있으면 hold ──────────────────────


def test_scoring_partial_axes_hold():
    evidences = [
        E("https://finchat.ai/tech", "Model card.", "ai_tech"),
        E("https://financeai.co/report", "Segment outlook.", "market"),
        # 나머지 축은 비워둠
    ]
    state = PipelineState(
        query="AI financial advisory startup", companies=[make_company()], chunks=evidences
    )
    sc = ScoringAgent()(state).scorecard["finchat"]

    _print_scorecard("Scoring — Partial Axes", sc)

    assert sc.total < 7.5
    mean_conf = sum(i.confidence for i in sc.items) / len(sc.items or [1])
    assert mean_conf < 0.55
    assert sc.decision == "hold"
