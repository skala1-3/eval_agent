# scripts/test_scoring.py
# Test script for ScoringAgent
# Run with: uv run python scripts/test_scoring.py

from graph.state import PipelineState, CompanyMeta, Evidence
from agents.scoring_agent import ScoringAgent
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# ─────────────────────────────────────────────
# 1. 더미 테스트 데이터
# ─────────────────────────────────────────────
company = CompanyMeta(
    id="finchat",
    name="FinChat AI",
    website="https://finchat.ai",
)

evidences = [
    Evidence(
        source="https://finchat.ai/blog/llm-guard",
        text="FinChat AI 공개한 LLM 보안 가드 성능은 업계 평균을 상회한다.",
        category="ai_tech",
        strength="strong",
        published="2025-07-01",
    ),
    Evidence(
        source="https://techcrunch.com/finchat",
        text="FinChat은 Sequoia로부터 Series A를 유치했다.",
        category="traction",
        strength="medium",
        published="2025-05-01",
    ),
    Evidence(
        source="https://finchat.ai/security",
        text="FINRA 규정을 충족하고 ISO/IEC 인증을 완료했다.",
        category="risk",
        strength="strong",
        published="2024-12-15",
    ),
    Evidence(
        source="https://financeai.co/report",
        text="미국 RIA 시장 내 CAGR 18% 성장 전망, 주요 경쟁사 대비 선도.",
        category="market",
        strength="medium",
        published="2025-06-20",
    ),
]

state = PipelineState(
    query="AI financial advisory startup",
    companies=[company],
    chunks=evidences,
)

# ─────────────────────────────────────────────
# 2. ScoringAgent 실행
# ─────────────────────────────────────────────
agent = ScoringAgent()
new_state = agent(state)

scorecard = list(new_state.scorecard.values())[0]

# ─────────────────────────────────────────────
# 3. 결과 출력 (표 + 패널)
# ─────────────────────────────────────────────
table = Table(title=f"F-AI Scorecard for {company.name}", show_lines=True)
table.add_column("Axis", justify="center", style="bold cyan")
table.add_column("Score", justify="right")
table.add_column("Confidence", justify="right")
table.add_column("Notes", justify="left")

for item in scorecard.items:
    table.add_row(item.key, f"{item.value:.2f}", f"{item.confidence:.2f}", item.notes)

console.print(table)

summary = f"""
[bold]Total Score:[/bold] {scorecard.total:.2f}
[bold]Decision:[/bold] [green]{scorecard.decision.upper()}[/green]
"""

console.print(Panel(summary, title="Final Decision", subtitle="ScoringAgent Output"))
