# agents/report_writer_agent.py
# 개선 포인트:
# - evidence 개수 2개 제한
# - LLM 요약 길이 제한 강화
# - PDF scale 0.85
# - 동일 문장 반복 최소화

import os, re, json, asyncio, logging
from datetime import datetime
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import async_playwright
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# ---------- Utils ----------
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|다\.\s+")

def as_float(x: Any, default: float = 0.0) -> float:
    try:
        if isinstance(x, (int, float)): return float(x)
        if isinstance(x, str): return float(x.strip())
    except Exception: pass
    return default

def safe_str(x: Any, default="-") -> str:
    if x is None: return default
    s = str(x).strip()
    return s if s else default

def truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text

def strength_from_score(v: float) -> str:
    if v >= 2.0: return "strong"
    if v >= 1.0: return "medium"
    return "weak"

# ---------- Agent ----------
class ReportWriterAgent:
    def __init__(self,
                 template_dir="docs/templates",
                 template_name="report.html.j2",
                 output_dir="outputs/reports",
                 model="gpt-4o-mini"):
        self.template_dir = template_dir
        self.template_name = template_name
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(["html","xml"])
        )

        self.llm = ChatOpenAI(model=model, temperature=0.3)
        logging.getLogger("httpx").setLevel(logging.WARNING)

        self.notes_len = 120   # 더 짧은 요약
        self.ev_len    = 80    # evidence 요약 1줄 수준
        self.ev_limit  = 2     # 2개로 제한

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
        return {"report_path": pdf_path, "skipped": False, "decision": context["scorecard"]["decision"]}

    async def _build_context(self, company: str, state: Dict[str, Any], total: float, mean_conf: float) -> Dict[str, Any]:
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

        blob = "\n".join([
            state.get("startup_summary",""),
            state.get("tech_summary",""),
            state.get("market_eval",""),
            state.get("competitor_summary",""),
            state.get("decision_rationale",""),
        ])

        items_llm = await self._gen_axis_items_llm(axes, total, mean_conf, blob)

        normalized_items: List[Dict[str, Any]] = []
        for key, label in [
            ("ai_tech","AI Tech"), ("market","Market"), ("traction","Traction"),
            ("moat","Moat"), ("risk","Risk"), ("team","Team"),
            ("deployability","Deployability"), ("total","Total")
        ]:
            raw = next((it for it in items_llm if it["key"] == key), None)
            score = total if key == "total" else axes.get(key, 0.0)
            conf = mean_conf
            notes = truncate((raw or {}).get("summary") or f"{label} 점수 {score:.2f}", self.notes_len)

            ev_list = (raw or {}).get("evidence") or []
            ev_rows = []
            for ev in ev_list[:self.ev_limit]:
                text = truncate(ev if isinstance(ev, str) else ev.get("text", "-"), self.ev_len)
                ev_rows.append({
                    "strength": strength_from_score(score),
                    "text": text, "source": "-", "published": "-"
                })
            if not ev_rows:
                ev_rows = [{"strength":"weak","text":"근거 수집 필요","source":"-","published":"-"}]

            normalized_items.append({
                "key": key,
                "value": score,
                "confidence": conf,
                "notes": notes,
                "evidence": ev_rows
            })

        return {
            "company": company_obj,
            "query": state.get("query",""),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "evidence_limit_per_axis": self.ev_limit,
            "scorecard": {
                "total": total,
                "decision": "invest",
                "items": normalized_items
            }
        }

    async def _gen_axis_items_llm(self, axes: Dict[str,float], total: float, conf: float, blob: str) -> List[Dict[str, Any]]:
        pairs = [
            ("ai_tech","AI Tech", axes.get("ai_tech",0.0)),
            ("market","Market", axes.get("market",0.0)),
            ("traction","Traction", axes.get("traction",0.0)),
            ("moat","Moat", axes.get("moat",0.0)),
            ("risk","Risk", axes.get("risk",0.0)),
            ("team","Team", axes.get("team",0.0)),
            ("deployability","Deployability", axes.get("deployability",0.0)),
            ("total","Total", total),
        ]

        async def _one(k: str, label: str, score: float) -> Dict[str, Any]:
            sys = SystemMessage(content="VC 심사역으로서 핵심 수치만 요약. 한 문장만 생성.")
            user = HumanMessage(content=f"""
[항목] {label}
[점수] {score:.2f}/10, 신뢰도 {conf:.2f}

[컨텍스트 요약]
{blob[:1000]}

JSON 형식으로 출력:
{{
  "summary": "정량근거 포함 1문장 (예: 'AHT 18% 개선, FCR 9%p 상승')",
  "evidence": ["15자 내외 문장 2개"]
}}
""")
            res = await self.llm.ainvoke([sys, user])
            try:
                j = json.loads(res.content)
            except Exception:
                j = {"summary": f"{label} 점수 {score:.2f}", "evidence": [f"{label} 관련 근거 필요."]}
            if not isinstance(j.get("evidence"), list) or not j["evidence"]:
                j["evidence"] = [f"{label} 근거 필요."]
            return {"key": k, "summary": j.get("summary",""), "evidence": j["evidence"]}

        return await asyncio.gather(*[asyncio.create_task(_one(k,l,sc)) for (k,l,sc) in pairs])

    async def _render_pdf(self, company: str, context: Dict[str, Any]):
        html = self.env.get_template(self.template_name).render(**context)
        html_path = os.path.join(self.output_dir, f"{company}.html")
        pdf_path  = os.path.join(self.output_dir, f"{company}.pdf")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(f"file://{os.path.abspath(html_path)}")
            await page.pdf(
                path=pdf_path,
                format="A4",
                print_background=True,
                scale=0.85,  # 👈 더 넉넉한 여백
                margin={"top":"18mm","bottom":"18mm","left":"14mm","right":"14mm"}
            )
            await browser.close()
        return html_path, pdf_path

# ---------------- Run ----------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = ReportWriterAgent()

    dummy_state = {
        "company_name": "FinChat AI",
        "company_meta": {
            "website": "https://finchat.ai",
            "founded_year": "2023",
            "stage": "Seed",
            "headcount": "10-20",
            "region": "KR",
            "tags": ["Financial AI","KYC","Contact Center"]
        },
        "fae_score": {
            "total": 8.1,
            "ai_tech": 2.3, "market": 1.8, "traction": 1.2,
            "moat": 1.0, "risk": 0.8, "team": 0.9, "deployability": 0.9
        },
        "confidence": {"mean": 0.62},
        "startup_summary": "금융 상담 자동화로 고객센터 AHT 18% 감소, FCR 9%p 향상.",
        "tech_summary": "온프렘/VPC/PII 마스킹 보안 설계로 금융기관 대응.",
        "market_eval": "국내 금융 AI 시장 연평균 15% 성장.",
        "competitor_summary": "한국어 인식률·보안 인증에서 경쟁사 대비 우위.",
        "decision_rationale": "시장성, 기술성 모두 우수하여 투자 권장.",
        "query": "AI financial advisory startup"
    }

    result = asyncio.run(agent.run(dummy_state))
    print(result)
