# agents/report_writer_agent.py
# Consulting-style ReportWriterAgent
# - Executive Summary / Competitive Position / Risk & Considerations / Investment Outlook
# - Evidence/Notes 길이 제한, PDF scale, OpenAI 호출 안전화(실패시 대체문구)
# - 축별 카드에 ScoringAgent의 실제 Evidence(강도/텍스트/출처/날짜) 반영

import os, re, json, asyncio, logging
from datetime import datetime
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import async_playwright
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import PipelineState


def as_float(x: Any, default: float = 0.0) -> float:
    try:
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            return float(x.strip())
    except Exception:
        pass
    return default


def safe_str(x: Any, default="-") -> str:
    if x is None:
        return default
    s = str(x).strip()
    return s if s else default


def truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def strength_from_score(v: float) -> str:
    if v >= 2.0:
        return "strong"
    if v >= 1.0:
        return "medium"
    return "weak"


SYSTEM_PROMPT = """
당신은 VC/전략 컨설턴트입니다. 기업 데이터를 분석해 **투자·컨설팅용 보고서**를 작성합니다.

[작성 목적]
- 투자자/고객이 기업의 기술력, 성장성, 시장성, 리스크를 한눈에 파악하도록 돕는다.
- 단순 요약이 아닌 **전략적 통찰(Strategic Insight)**과 **투자 판단 근거**를 제공한다.

[톤 & 스타일]
- 전문 컨설턴트의 자신감 있는 어조(확언형), 과장 금지, 정량 수치 우선.
- 각 섹션 3~6문장 내외(불릿 섹션 제외). 중복 표현/군더더기 금지.

[섹션 구성]
1) Executive Summary: 기업 개요 + 핵심 수치 + 투자 요약(3~4문장)
2) Competitive Position: 주요 강점/차별성 불릿 4~6개 (각 1문장)
3) Risk & Considerations: 핵심 리스크 3~5개 + 완화/대응 포인트 (각 1문장)
4) Investment Outlook: 종합평가 + 권고 + 3~6개월 액션아이템(3~5문장)

[출력 형식(JSON)]
{
  "exec_summary": "문단",
  "position_points": ["불릿", "..."],
  "risks": ["불릿", "..."],
  "outlook": "문단"
}
"""


class ReportWriterAgent:
    def __init__(
        self,
        template_dir="docs/templates",
        template_name="report.html.j2",
        output_dir="outputs/reports",
        model="gpt-4o-mini",
    ):
        self.template_dir = template_dir
        self.template_name = template_name
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

        self.llm = ChatOpenAI(model=model, temperature=0.4)
        logging.getLogger("httpx").setLevel(logging.WARNING)

        self.notes_len = 140
        self.ev_len = 90
        self.ev_limit = 3

        # 파이프라인 state 참조 (evidence 접근용)
        self._pipeline_state_ref: PipelineState | None = None

    def __call__(self, state: PipelineState) -> PipelineState:
        # 전체 state 보관
        self._pipeline_state_ref = state

        for company in state.companies:
            sc = state.scorecard.get(company.id)
            if not sc or sc.decision != "invest":
                continue

            fae_items = {it.key: it.value for it in sc.items}
            fae_items["total"] = sc.total
            conf_mean = 0.0
            if sc.items:
                conf_mean = sum(it.confidence for it in sc.items) / len(sc.items)

            payload = {
                "company_id": company.id,  # ← id 전달
                "company_name": company.name,
                "company_meta": company.model_dump(),
                "fae_score": fae_items,
                "confidence": {"mean": conf_mean},
                "startup_summary": "",
                "tech_summary": "",
                "market_eval": "",
                "competitor_summary": "",
                "decision_rationale": "",
                "query": state.query,
            }
            res = asyncio.run(self.run(payload))
            if res and res.get("report_path"):
                state.reports[company.id] = res["report_path"]
        return state

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        company = state.get("company_name", "Unknown")
        total = as_float((state.get("fae_score") or {}).get("total"), 0.0)
        mean_conf = as_float((state.get("confidence") or {}).get("mean"), 0.5)
        if total < 7.5 or mean_conf < 0.55:
            logging.info(f"[SKIP] Gate fail total={total}, conf={mean_conf}")
            return {"report_path": None, "skipped": True, "decision": "hold"}

        context = await self._build_context(company, state, total, mean_conf)
        _, pdf_path = await self._render_pdf(company, context)
        logging.info(f"[REPORT] created: {pdf_path}")
        return {
            "report_path": pdf_path,
            "skipped": False,
            "decision": context["scorecard"]["decision"],
        }

    async def _build_context(
        self, company: str, state: Dict[str, Any], total: float, mean_conf: float
    ) -> Dict[str, Any]:
        meta = state.get("company_meta") or {}
        company_obj = {
            "name": company,
            "website": safe_str(meta.get("website")),
            "founded_year": safe_str(meta.get("founded_year") or meta.get("founded")),
            "stage": safe_str(meta.get("stage")),
            "headcount": safe_str(meta.get("headcount")),
            "region": safe_str(meta.get("region", "KR")),
            "tags": meta.get("tags") or [],
        }

        fae = state.get("fae_score") or {}
        axes = {
            "ai_tech": as_float(fae.get("ai_tech"), 0.0),
            "market": as_float(fae.get("market"), 0.0),
            "traction": as_float(fae.get("traction"), 0.0),
            "moat": as_float(fae.get("moat"), 0.0),
            "risk": as_float(fae.get("risk"), 0.0),
            "team": as_float(fae.get("team"), 0.0),
            "deployability": as_float(fae.get("deployability"), 0.0),
        }

        blob = "\n".join(
            [
                state.get("startup_summary", ""),
                state.get("tech_summary", ""),
                state.get("market_eval", ""),
                state.get("competitor_summary", ""),
                state.get("decision_rationale", ""),
            ]
        )

        consulting = await self._gen_consulting_sections(company_obj, axes, total, mean_conf, blob)

        # 실제 Evidence 반영
        normalized_items: List[Dict[str, Any]] = []
        company_id = state.get("company_id")
        sc_obj = None
        if self._pipeline_state_ref and company_id:
            sc_obj = self._pipeline_state_ref.scorecard.get(company_id)

        for key, label in [
            ("ai_tech", "AI Tech"),
            ("market", "Market"),
            ("traction", "Traction"),
            ("moat", "Moat"),
            ("risk", "Risk"),
            ("team", "Team"),
            ("deployability", "Deployability"),
            ("total", "Total"),
        ]:
            score = total if key == "total" else axes.get(key, 0.0)
            notes = f"{label} 지표는 {score:.2f} 수준."
            ev_rows = []

            if sc_obj and key != "total":
                try:
                    item = next((i for i in sc_obj.items if i.key == key), None)
                    if item and item.evidence:
                        for e in item.evidence[: self.ev_limit]:
                            ev_rows.append(
                                {
                                    "strength": getattr(e, "strength", strength_from_score(score)),
                                    "text": truncate(getattr(e, "text", ""), self.ev_len),
                                    "source": getattr(e, "source", "-") or "-",
                                    "published": getattr(e, "published", "-") or "-",
                                }
                            )
                except Exception:
                    pass

            if not ev_rows:
                ev_rows = [
                    {
                        "strength": strength_from_score(score),
                        "text": "핵심 근거 보강 필요",
                        "source": "-",
                        "published": "-",
                    }
                ]

            normalized_items.append(
                {
                    "key": key,
                    "value": score,
                    "confidence": mean_conf,
                    "notes": truncate(notes, self.notes_len),
                    "evidence": ev_rows,
                }
            )

        context = {
            "company": company_obj,
            "query": state.get("query", ""),
            "generated_at": state.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
            "evidence_limit_per_axis": self.ev_limit,
            "scorecard": {"total": total, "decision": "invest", "items": normalized_items},
            "exec_summary": consulting["exec_summary"],
            "position_points": consulting["position_points"],
            "risks": consulting["risks"],
            "outlook": consulting["outlook"],
        }
        return context

    async def _gen_consulting_sections(
        self, company: Dict[str, Any], axes: Dict[str, float], total: float, conf: float, blob: str
    ) -> Dict[str, Any]:
        sys = SystemMessage(content=SYSTEM_PROMPT)
        user = HumanMessage(
            content=f"""
[기업 정보]
{json.dumps(company, ensure_ascii=False)}

[점수표 요약]
total={total:.2f}, confidence={conf:.2f}
{json.dumps(axes, ensure_ascii=False)}

[텍스트 컨텍스트(요약)]
{blob[:1500]}

지침에 맞는 JSON만 반환.
"""
        )
        try:
            res = await self.llm.ainvoke([sys, user])
            j = json.loads(res.content)
        except Exception:
            j = {
                "exec_summary": f"{company.get('name','기업')}은(는) 총점 {total:.2f}로 투자 권장 수준입니다. "
                f"핵심 지표의 신뢰도는 {conf:.2f}입니다.",
                "position_points": [
                    "도메인 특화 AI 역량 보유",
                    "엔터프라이즈 보안/온프렘 대응",
                    "금융기관 PoC 진행 및 상용화 가능성",
                ],
                "risks": ["규제 및 데이터 접근 권한 리스크", "대형 경쟁사 진입시 차별화 유지 필요"],
                "outlook": "단기적으로는 레퍼런스 확보 및 ARR 가시화, 중기적으로는 파트너십/리전 확장 권장.",
            }

        j["exec_summary"] = truncate(j.get("exec_summary", ""), 900)
        j["outlook"] = truncate(j.get("outlook", ""), 900)
        j["position_points"] = [truncate(s, 160) for s in (j.get("position_points") or [])][:6] or [
            "강점 정리 필요"
        ]
        j["risks"] = [truncate(s, 160) for s in (j.get("risks") or [])][:5] or ["리스크 정리 필요"]
        return j

    async def _render_pdf(self, company: str, context: Dict[str, Any]):
        html = self.env.get_template(self.template_name).render(**context)
        html_path = os.path.join(self.output_dir, f"{company}.html")
        pdf_path = os.path.join(self.output_dir, f"{company}.pdf")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page()
            await page.goto(f"file://{os.path.abspath(html_path)}")
            await page.pdf(
                path=pdf_path,
                format="A4",
                print_background=True,
                scale=0.9,
                margin={"top": "16mm", "bottom": "18mm", "left": "14mm", "right": "14mm"},
            )
            await browser.close()
        return html_path, pdf_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = ReportWriterAgent()

    dummy_state = {
        "company_id": "demo_1",
        "company_name": "FinChat AI",
        "company_meta": {
            "website": "https://finchat.ai",
            "founded_year": "2023",
            "stage": "Seed",
            "headcount": "10-20",
            "region": "KR",
            "tags": ["Financial AI", "KYC", "Contact Center"],
        },
        "fae_score": {
            "total": 8.2,
            "ai_tech": 2.4,
            "market": 1.8,
            "traction": 1.3,
            "moat": 1.0,
            "risk": 0.8,
            "team": 0.9,
            "deployability": 1.0,
        },
        "confidence": {"mean": 0.62},
        "startup_summary": "금융 상담 자동화로 AHT 18% 감소, FCR 9%p 향상.",
        "tech_summary": "온프렘/VPC/PII 마스킹, 감사추적 등 엔터프라이즈 보안 설계.",
        "market_eval": "국내 금융 AI 연 15% 성장, 규제 친화·감사추적 기능이 채택 핵심.",
        "competitor_summary": "한국어 성능·온프렘 대응·보안 인증에서 경쟁력.",
        "decision_rationale": "시장성/기술성 모두 우수 → 투자 권장.",
        "query": "AI financial advisory startup",
    }

    result = asyncio.run(agent.run(dummy_state))
    print(result)
