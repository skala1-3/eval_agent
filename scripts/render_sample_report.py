# scripts/render_sample_report.py
# [KO] report.html.j2 템플릿 단독 스모크 렌더링 (에이전트 없이)
#     - 더미 scorecard/회사정보/레이더차트 생성 → WeasyPrint로 PDF 출력

from __future__ import annotations
from pathlib import Path
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape
import matplotlib.pyplot as plt

# [KO] 출력 디렉터리 준비
ROOT = Path.cwd()
OUT = ROOT / "outputs" / "reports"
OUT.mkdir(parents=True, exist_ok=True)


# [KO] 레이더차트 샘플 생성 (옵션)
def make_radar_png(path: Path) -> Path:
    labels = ["AI", "Market", "Traction", "Moat", "Risk", "Team", "Deploy"]
    values = [8.5, 7.8, 7.2, 6.5, 6.2, 7.0, 7.6]
    # 레이더 설정
    import numpy as np

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig = plt.figure()
    ax = plt.subplot(111, polar=True)
    ax.plot(angles, values)
    ax.fill(angles, values, alpha=0.1)
    ax.set_thetagrids(np.degrees(angles[:-1]), labels)
    ax.set_ylim(0, 10)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


radar_path = make_radar_png(OUT / "sample_radar.png")

# [KO] 템플릿 로드
tmpl_dir = ROOT / "docs" / "templates"
env = Environment(
    loader=FileSystemLoader(tmpl_dir),
    autoescape=select_autoescape(disabled_extensions=("j2",)),
)
tmpl = env.get_template("report.html.j2")

# [KO] 더미 컨텍스트 (템플릿 키와 일치)
context = {
    "company": {
        "id": "finchat-ai",
        "name": "FinChat AI",
        "website": "https://finchat.example.com",
        "founded_year": 2023,
        "stage": "Seed",
        "headcount": 18,
        "region": "US",
        "tags": ["LLM", "Advisor", "Finance"],
    },
    "query": "AI financial advisory startup",
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "radar_chart_path": str(radar_path),
    "evidence_limit_per_axis": 3,
    "scorecard": {
        "total": 7.9,
        "decision": "invest",
        "items": [
            {
                "key": "ai_tech",
                "value": 8.5,
                "confidence": 0.70,
                "notes": "LLM guardrails & benchmark 공개",
                "evidence": [
                    {
                        "source": "https://example.com/tech",
                        "text": "Benchmark X on dataset Y",
                        "category": "ai_tech",
                        "strength": "strong",
                        "published": "2025-05-01",
                    },
                    {
                        "source": "https://example.com/tech2",
                        "text": "Safety guardrails doc",
                        "category": "ai_tech",
                        "strength": "medium",
                        "published": "2025-07-14",
                    },
                ],
            },
            {
                "key": "market",
                "value": 7.8,
                "confidence": 0.62,
                "notes": "RIA 세그먼트·CAGR xx%",
                "evidence": [
                    {
                        "source": "https://example.com/market",
                        "text": "TAM/SAM 수치",
                        "category": "market",
                        "strength": "medium",
                        "published": "2025-04-02",
                    }
                ],
            },
            {
                "key": "traction",
                "value": 7.2,
                "confidence": 0.58,
                "notes": "ARR 공개, 유료 고객 로고",
                "evidence": [],
            },
            {
                "key": "moat",
                "value": 6.5,
                "confidence": 0.55,
                "notes": "전환비용·규제 적격성",
                "evidence": [],
            },
            {
                "key": "risk",
                "value": 6.2,
                "confidence": 0.60,
                "notes": "FINRA 관련 문서",
                "evidence": [],
            },
            {
                "key": "team",
                "value": 7.0,
                "confidence": 0.50,
                "notes": "금융/AI 경력 혼합",
                "evidence": [],
            },
            {
                "key": "deployability",
                "value": 7.6,
                "confidence": 0.57,
                "notes": "API/관제/데이터 경계",
                "evidence": [],
            },
        ],
    },
}

# [KO] HTML 렌더 → PDF 변환
html = tmpl.render(**context)

from playwright.sync_api import sync_playwright

pdf_path = OUT / "sample_report.pdf"
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    # base_url 이 필요한 자원(CSS/이미지)이 있으면 data URL 또는 file URL 사용
    page.set_content(html, wait_until="load")
    page.pdf(
        path=str(pdf_path),
        format="A4",
        print_background=True,
        margin={"top": "18mm", "right": "16mm", "bottom": "18mm", "left": "16mm"},
    )
    browser.close()
print(f"[OK] PDF generated (Playwright) -> {pdf_path}")
