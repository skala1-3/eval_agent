# agents/report_writer_agent.py
# Consulting Report (v4.0 – KPI tiles / Competition Matrix / Risk Heat / Scenario Table)
# - 기존 섹션 유지 + 신규 4개 섹션 추가
# - KPI 타일: 값 없으면 N/A + "수집 필요" 뱃지
# - 경쟁 매트릭스: 고정 행(기능/보안/배포/로컬/가격/레퍼런스), 열=competitors; 값 없으면 '—'
# - 리스크 Heat: Risk / Likelihood / Impact / Mitigation (없으면 LLM로 정성 생성)
# - 시나리오 표: Upside / Base / Downside (없으면 LLM로 정성 생성)
# - LLM 사용: 새로운 정성 표/문구 생성에 활용 (필수 수치 추정은 하지 않음)
# - 강점/취약 점 불릿, Evidence 표시(도메인/제목), total evidence 숨김 유지

import os, re, json, asyncio, logging
from datetime import datetime
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import async_playwright
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from difflib import SequenceMatcher
from dotenv import load_dotenv

# ---------------- Utils ----------------
def as_float(x: Any, default: float = 0.0) -> float:
    try:
        if isinstance(x, (int, float)): return float(x)
        if isinstance(x, str): return float(x.strip())
    except Exception: pass
    return default

def safe_str(x: Any, default: str = "-") -> str:
    if x is None: return default
    s = str(x).strip()
    return s if s else default

def truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text

def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").strip(), (b or "").strip()).ratio()

def strength_from_score(v: float) -> str:
    if v >= 2.0: return "strong"
    if v >= 1.0: return "medium"
    return "weak"

def _fmt_domain(url: str) -> str:
    try:
        d = urlparse(url).netloc
        return d.replace("www.","")
    except:
        return "-"

def _strip_inline_urls(text: str) -> str:
    return re.sub(r'https?://\S+', '', text or '').strip()

def _dedupe_list(items: List[str], thresh: float = 0.88) -> List[str]:
    out: List[str] = []
    for s in items:
        s = (s or "").strip()
        if not s: continue
        if all(similar(s, t) < thresh for t in out):
            out.append(s)
    return out

def _norm_bullet(s: str) -> str:
    s = (s or "").strip()
    if not s: return s
    s = _strip_inline_urls(s)
    s = re.sub(r'[.]+$', '', s)          # 끝 마침표 제거
    s = re.sub(r'(다|요)$', '', s).strip()
    return s

# ---------------- Data classes ----------------
@dataclass
class EvidenceItem:
    text: str
    source_url: str
    published_at: str
    strength: str
    title: str = "-"
    domain: str = "-"

# ---------------- i18n ----------------
def _i18n(lang: str) -> Dict[str, Any]:
    if str(lang).lower().startswith("en"):
        return {"lang":"en","labels":{
            "invest":"INVEST","hold":"HOLD","total":"Total","confidence":"Confidence",
            "evidence":"Evidence by Axis","strength":"Strength","text":"Text","source":"Source","date":"Date",
            "narrative":"Strengths & Weaknesses",
            "kpis":"Key KPIs","matrix":"Competitive Matrix","risk_heat":"Risk Heat","scenarios":"Scenarios"
        }}
    return {"lang":"ko","labels":{
        "invest":"투자 권장","hold":"보류","total":"총점","confidence":"신뢰도",
        "evidence":"근거(축별)","strength":"강도","text":"텍스트","source":"출처","date":"날짜",
        "narrative":"강점/취약 내러티브",
        "kpis":"핵심 KPI","matrix":"경쟁 매트릭스","risk_heat":"리스크 Heat","scenarios":"시나리오"
    }}

# ---------------- Prompts ----------------
SYSTEM_PROMPT = """
당신은 시니어 VC/전략 컨설턴트입니다. 간결하고 자신감 있는 컨설팅 문체로 작성하세요.
정확한 수치·날짜·고객사 실명은 입력에 있을 때만 사용하고, 없으면 정성적 서술로 대체.
각 섹션 3~6문장, 중복/군더더기 금지.

반환(JSON만):
{
  "exec_summary": "문단",
  "position_points": ["불릿", "..."],
  "risks": ["불릿", "..."],
  "outlook": "문단"
}
"""

NARRATIVE_BULLET_PROMPT = """
아래 정보를 참고하되, 공개 지식과 업계 일반론을 활용해 **음슴체 불릿**을 생성.
요구 사항:
- strengths_bullets 5~8개, weaknesses_bullets 5~8개.
- 각 불릿은 한 줄, 12~28단어 권장. 문장 끝 마침표 금지, 종결어 금지.
- **하이픈(-)을 붙이지 말고 내용만** 반환 (템플릿에서 점 불릿 렌더링).
- 앞 섹션에서 이미 언급된 수치/키워드 반복 금지.

금지 키워드: {banlist}

입력 힌트:
AXES = {axes_json}
FACTS = {facts_json}
DOCS_PREVIEW = {docs_json}

반환(JSON만):
{{"strengths_bullets":["..."], "weaknesses_bullets":["..."]}}
"""

CONCLUSION_FREE_PROMPT = """
투자 판단 관점의 **심층 결론**을 1~2개 문단으로 작성.
요구 사항:
- 각 문단 4~7문장.
- 투자 논지(Thesis), 촉매(Catalysts), 차단 위험(Blockers), 집행 조건(Conditions) 포함.
- 공개 지식/업계 일반론 자유 활용.
- 앞에서 반복된 수치/키워드 재서술 금지.

금지 키워드: {banlist}

입력 힌트:
AXES = {axes_json}
BODY = {body_json}
FACTS = {facts_json}

반환(JSON만):
{{"conclusion":"문단1\\n\\n문단2(선택)"}}
"""

RISK_HEAT_PROMPT = """
아래 정보를 참고해 리스크 테이블을 생성.
열: Risk (짧은 제목), Likelihood(저/중/고), Impact(저/중/고), Mitigation(완화책, 한 줄).
5~7행 권장. 숫자 추정은 금지.

입력:
COMPANY = {company}
AXES = {axes}
CONTEXT = {context}

반환(JSON만):
{{"rows":[{{"risk":"...", "likelihood":"중", "impact":"고", "mitigation":"..."}}, ...]}}
"""

SCENARIO_PROMPT = """
아래 정보를 참고해 시나리오 표를 생성.
행: Upside / Base / Downside
열: Drivers, Catalysts, Blockers, Conditions (각 1~2문장, 정성)
숫자 추정 금지.

입력:
COMPANY = {company}
AXES = {axes}
CONTEXT = {context}

반환(JSON만):
{{"upside": {{"drivers":"...", "catalysts":"...", "blockers":"...", "conditions":"..."}},
  "base":   {{"drivers":"...", "catalysts":"...", "blockers":"...", "conditions":"..."}},
  "downside":{{"drivers":"...", "catalysts":"...", "blockers":"...", "conditions":"..."}}}}
"""

# ---------------- Agent ----------------
class ReportWriterAgent:
    def __init__(self,
                 template_dir="docs/templates",
                 template_name="report.html.j2",
                 output_dir="outputs/reports",
                 model="gpt-4o-mini"):
        load_dotenv()
        self.template_dir = template_dir
        self.template_name = template_name
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(["html","xml"])
        )

        self.llm = ChatOpenAI(model=model, temperature=0.25)
        self.llm_free = ChatOpenAI(model=model, temperature=0.7)
        logging.getLogger("httpx").setLevel(logging.WARNING)

        self.notes_len   = int(os.getenv("NOTES_LEN", "140"))
        self.ev_text_len = int(os.getenv("EVIDENCE_TEXT_LEN", "120"))
        self.ev_limit    = int(os.getenv("EVIDENCE_LIMIT_PER_AXIS", "3"))
        self.min_total   = as_float(os.getenv("REPORT_MIN_TOTAL", "7.5"), 7.5)
        self.min_conf    = as_float(os.getenv("REPORT_MIN_CONF", "0.55"), 0.55)
        self.pdf_scale   = as_float(os.getenv("PDF_SCALE", "0.9"), 0.9)

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        company = state.get("company_name", "Unknown")
        total = as_float((state.get("fae_score") or {}).get("total"), 0.0)
        mean_conf = as_float((state.get("confidence") or {}).get("mean"), 0.5)

        if total < self.min_total or mean_conf < self.min_conf:
            logging.info(f"[SKIP] Gate fail total={total}, conf={mean_conf}")
            return {"report_path": None, "skipped": True, "decision": "hold"}

        context = await self._build_context(company, state, total, mean_conf)
        _, pdf_path = await self._render_pdf(company, context)
        logging.info(f"[REPORT] created: {pdf_path}")
        return {"report_path": pdf_path, "skipped": False, "decision": context["scorecard"]["decision"]}

    async def _build_context(self, company: str, state: Dict[str, Any],
                             total: float, mean_conf: float) -> Dict[str, Any]:
        lang = state.get("lang", "ko")
        i18n = _i18n(lang)

        meta = state.get("company_meta") or {}
        company_obj = {
            "name": company,
            "website": safe_str(meta.get("website")),
            "founded_year": safe_str(meta.get("founded_year") or meta.get("founded")),
            "stage": safe_str(meta.get("stage")),
            "headcount": safe_str(meta.get("headcount")),
            "region": safe_str(meta.get("region", "KR")),
            "tags": meta.get("tags") or [],
            "logos": meta.get("logos") or []
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

        # Blobs for LLM context
        blob = "\n".join([
            state.get("startup_summary",""),
            state.get("tech_summary",""),
            state.get("market_eval",""),
            state.get("competitor_summary",""),
            state.get("decision_rationale",""),
        ])

        product_docs  = state.get("product_docs")  or []
        market_docs   = state.get("market_docs") or []
        customers     = state.get("customers") or []
        partners      = state.get("partners")  or []
        security_certs= state.get("security") or {}
        pricing_plans = state.get("pricing") or []
        competitors   = state.get("competitors") or []   # [{name, product, security, deployment, localization, pricing, references}]
        metrics       = self._normalize_metrics(state.get("metrics") or {})  # KPI tiles
        risk_table    = state.get("risk_table") or await self._gen_risk_heat(company_obj, axes, blob)
        scenarios     = state.get("scenarios") or await self._gen_scenarios(company_obj, axes, blob)

        evidence_by_axis = self._collect_evidence(state, axes, blob)
        grounded = await self._gen_open_sections(company_obj, axes, product_docs, market_docs, evidence_by_axis)

        # 점수표 + evidence
        normalized_items: List[Dict[str, Any]] = []
        for key, label in [
            ("ai_tech","AI Tech"), ("market","Market"), ("traction","Traction"),
            ("moat","Moat"), ("risk","Risk"), ("team","Team"),
            ("deployability","Deployability"), ("total","Total")
        ]:
            score = total if key == "total" else axes.get(key, 0.0)
            ev_rows = evidence_by_axis.get(key, [])
            ev_rows = [
                {
                    "strength": e.strength or strength_from_score(score),
                    "text": truncate(e.text, self.ev_text_len),
                    "source_url": e.source_url or "-",
                    "published_at": e.published_at or "-",
                    "title": e.title or "-",
                    "domain": e.domain or "-"
                } for e in ev_rows[: self.ev_limit]
            ] or [{
                "strength": strength_from_score(score),
                "text": "정보 부족",
                "source_url": "-",
                "published_at": "-",
                "title": "-",
                "domain": "-"
            }]
            normalized_items.append({
                "key": key, "value": score, "confidence": mean_conf,
                "notes": truncate(f"{label} 지표는 {score:.2f} 수준.", self.notes_len),
                "evidence": ev_rows
            })

        # 금지어(중복 억제)
        banlist = self._harvest_said_facts({
            "exec_summary": grounded["exec_summary"],
            "position_points": grounded["position_points"],
            "risks": grounded["risks"]
        })

        # 강점/취약 불릿
        strengths_bullets, weaknesses_bullets = await self._gen_narrative_bullets(
            company_obj, axes, product_docs, market_docs, banlist
        )
        strengths_bullets = self._normalize_bullets(strengths_bullets) or self._fallback_strength_bullets(axes)
        weaknesses_bullets = self._normalize_bullets(weaknesses_bullets) or self._fallback_weakness_bullets(axes)

        # 결론
        gpt_conclusion = await self._gen_conclusion_free(axes, company_obj, grounded, banlist)
        gpt_conclusion = _strip_inline_urls(gpt_conclusion) or (
            "핵심 논지는 기술 우위 기반 문제-해결 적합성. "
            "3~6개월 내 대표 레퍼런스 확보와 파트너 채널이 촉매로 작동. "
            "팀·리스크 축의 실행 불확실성이 차단 요인. "
            "집행 조건: 온보딩 지표·보안/규제 체크리스트·전환율 가시화."
        )

        decision = "invest"
        decision_label = i18n["labels"]["invest"]
        items_for_evidence = [it for it in normalized_items if it["key"] != "total"]

        # 경쟁 매트릭스 표 데이터 정규화
        comp_matrix = self._normalize_comp_matrix(competitors)

        context = {
            "i18n": i18n,
            "company": company_obj,
            "query": state.get("query",""),
            "generated_at": state.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
            "scorecard": {
                "total": total,
                "decision": decision,
                "decision_label": decision_label,
                "items": normalized_items
            },
            "items_for_evidence": items_for_evidence,
            "evidence_limit_per_axis": self.ev_limit,
            "exec_summary": grounded["exec_summary"],
            "position_points": grounded["position_points"],
            "risks": grounded["risks"],
            "outlook": grounded["outlook"],
            "strength_bullets": strengths_bullets,
            "weakness_bullets": weaknesses_bullets,
            "gpt_conclusion": gpt_conclusion,
            "confidence_mean": mean_conf,
            "radar_chart_path": state.get("radar_chart_path") or None,

            # 신규 섹션들
            "metrics": metrics,
            "comp_matrix": comp_matrix,
            "risk_heat": risk_table,
            "scenarios": scenarios,
        }
        return context

    # ----- KPI tiles -----
    def _normalize_metrics(self, m: Dict[str, Any]) -> Dict[str, Any]:
        # 키: nrr, grr, payback_months, gross_margin, win_rate, pipeline_x, customers_count, arr_proxy
        def norm_pct(v): 
            s = safe_str(v,"").replace("%","").strip()
            try:
                f = float(s)
                return f"{f:.0f}%"
            except: 
                return "N/A"
        def norm_num(v):
            try:
                if v is None or v == "": return "N/A"
                return str(v)
            except: return "N/A"
        out = {
            "nrr": norm_pct(m.get("nrr")),
            "grr": norm_pct(m.get("grr")),
            "payback_months": norm_num(m.get("payback_months")),
            "gross_margin": norm_pct(m.get("gross_margin")),
            "win_rate": norm_pct(m.get("win_rate")),
            "pipeline_x": norm_num(m.get("pipeline_x")),
            "customers_count": norm_num(m.get("customers_count")),
            "arr_proxy": norm_num(m.get("arr_proxy")),
        }
        return out

    # ----- Competition matrix -----
    def _normalize_comp_matrix(self, competitors: List[Dict[str,Any]]) -> Dict[str, Any]:
        # rows: product, security, deployment, localization, pricing, references
        cols = []
        for c in (competitors or []):
            cols.append({
                "name": safe_str(c.get("name"), "-"),
                "product": safe_str(c.get("product"), "—"),
                "security": safe_str(c.get("security"), "—"),
                "deployment": safe_str(c.get("deployment"), "—"),
                "localization": safe_str(c.get("localization"), "—"),
                "pricing": safe_str(c.get("pricing"), "—"),
                "references": safe_str(c.get("references"), "—"),
            })
        if not cols:
            # 최소 컬럼 2개 보장 (Generic)
            cols = [
                {"name":"Generic A","product":"—","security":"—","deployment":"—","localization":"—","pricing":"—","references":"—"},
                {"name":"Generic B","product":"—","security":"—","deployment":"—","localization":"—","pricing":"—","references":"—"},
            ]
        return {"cols": cols, "rows": [
            {"key":"product","label":"제품 기능"},
            {"key":"security","label":"보안/컴플라이언스"},
            {"key":"deployment","label":"배포 옵션"},
            {"key":"localization","label":"로컬라이즈"},
            {"key":"pricing","label":"가격/조달"},
            {"key":"references","label":"레퍼런스"},
        ]}

    # ----- Evidence -----
    def _collect_evidence(self, state: Dict[str, Any], axes: Dict[str, float], blob: str) -> Dict[str, List[EvidenceItem]]:
        out: Dict[str, List[EvidenceItem]] = {k: [] for k in list(axes.keys()) + ["total"]}
        def add(axis: str, it: Dict[str, Any]):
            url = safe_str(it.get("source_url") or it.get("source"), "-")
            out[axis].append(EvidenceItem(
                text=safe_str(it.get("text"), "-"),
                source_url=url,
                published_at=safe_str(it.get("published_at") or it.get("published"), "-"),
                strength=safe_str(it.get("strength"), strength_from_score(axes.get(axis,0.0))),
                title=safe_str(it.get("title"), "-"),
                domain=_fmt_domain(url) if url and url != "-" else "-"
            ))
        ev = state.get("evidence") or {}
        if isinstance(ev, dict):
            for axis, items in ev.items():
                if axis not in out: continue
                for it in items or []: add(axis, it)
        pool = state.get("evidence_pool") or []
        for it in pool:
            axis = safe_str(it.get("axis")).lower()
            if axis in out: add(axis, it)

        # truncate & dedupe
        for k, items in out.items():
            items2, seen = [], []
            for e in items:
                if not e.text or e.text == "-": continue
                t = truncate(e.text, self.ev_text_len)
                if all(similar(t, s[0]) < 0.88 for s in seen):
                    items2.append(EvidenceItem(t, e.source_url, e.published_at, e.strength, e.title, e.domain))
                    seen.append((t, e.source_url, e.published_at))
            out[k] = items2
        return out

    # ----- LLM standard sections -----
    async def _gen_open_sections(self, company: Dict[str,Any], axes: Dict[str,float],
                                 product_docs: List[Dict[str,Any]],
                                 market_docs: List[Dict[str,Any]],
                                 ev_by_axis: Dict[str,List[EvidenceItem]]) -> Dict[str, Any]:
        facts = {"company": company}
        docs = {"product": product_docs[:8], "market": market_docs[:8]}
        evidence_preview = {k:[e.text for e in v][:2] for k,v in ev_by_axis.items()}

        sys = SystemMessage(content=SYSTEM_PROMPT)
        user = HumanMessage(content=json.dumps({
            "FACTS": facts, "AXES": axes, "DOCS": docs, "EVIDENCE": evidence_preview
        }, ensure_ascii=False))

        for _ in range(2):
            try:
                res = await self.llm.ainvoke([sys, user])
                txt = (res.content or "").strip()
                m = re.search(r"\{.*\}", txt, flags=re.DOTALL)
                if m: txt = m.group(0)
                j = json.loads(txt)
                return self._normalize_open_sections(j, axes)
            except Exception as e:
                logging.warning(f"[OPEN SECTIONS] LLM error: {e}")

        return self._fallback_from_axes(axes)

    def _normalize_open_sections(self, j: Dict[str,Any], axes: Dict[str,float]) -> Dict[str,Any]:
        exec_summary = truncate(safe_str(j.get("exec_summary"), ""), 900)
        position = [truncate(safe_str(x,""), 200) for x in (j.get("position_points") or []) if safe_str(x,"")]
        risks     = [truncate(safe_str(x,""), 200) for x in (j.get("risks") or []) if safe_str(x,"")]
        outlook   = truncate(safe_str(j.get("outlook"), ""), 900)

        if not exec_summary:
            hi = max(axes, key=lambda k: axes[k]) if axes else "ai_tech"
            lo = min(axes, key=lambda k: axes[k]) if axes else "risk"
            exec_summary = f"축 점수 기준으로 {hi}는 상대적으로 강점, {lo}는 취약 영역입니다. 중기적으로는 취약 축 보강과 강점의 상용화 가속이 권장됩니다."
        if not position:
            position = ["제품/기술 고도화 진행", "엔터프라이즈 요구 대응", "시장 채택 촉진 필요"]
        if not risks:
            risks = ["취약 축 점수가 낮아 초기 장애 요인이 될 수 있음", "경쟁 심화 및 대체재 대비 차별화 유지 필요"]
        if not outlook:
            outlook = "3–6개월 내 취약 축 보강과 대표 레퍼런스 확보가 투자 집행의 핵심 조건입니다."

        return {
            "exec_summary": exec_summary,
            "position_points": position[:6],
            "risks": risks[:5],
            "outlook": outlook
        }

    def _fallback_from_axes(self, axes: Dict[str,float]) -> Dict[str,Any]:
        hi = max(axes, key=lambda k: axes[k]) if axes else "ai_tech"
        lo = min(axes, key=lambda k: axes[k]) if axes else "risk"
        return {
            "exec_summary": f"{hi}가 상대적으로 강점이며 {lo}는 보완이 필요한 취약 영역입니다. 강점 상용화와 취약 축 보강이 병행되어야 합니다.",
            "position_points": ["기술 역량 우위", "엔터프라이즈 요구 충족", "시장 접근 가속 필요"],
            "risks": ["취약 축 관련 실행 리스크", "대형사 진입·대체재 경쟁"],
            "outlook": "조건부 레퍼런스 확보와 파이프라인 전환율 개선이 단기 우선 과제입니다."
        }

    # ----- Bullets & Conclusion -----
    async def _gen_narrative_bullets(self, company: Dict[str,Any], axes: Dict[str,float],
                                     product_docs: List[Dict[str,Any]],
                                     market_docs: List[Dict[str,Any]],
                                     banlist: List[str]) -> Tuple[List[str], List[str]]:
        facts = {"company": company}
        docs_preview = {"product": product_docs[:6], "market": market_docs[:6]}
        sys = SystemMessage(content="컨설팅 톤, JSON only.")
        prompt = NARRATIVE_BULLET_PROMPT.format(
            axes_json=json.dumps(axes, ensure_ascii=False),
            facts_json=json.dumps(facts, ensure_ascii=False),
            docs_json=json.dumps(docs_preview, ensure_ascii=False),
            banlist=", ".join(banlist) or "-"
        )
        user = HumanMessage(content=prompt)

        s_bullets: List[str] = []
        w_bullets: List[str] = []
        for _ in range(2):
            try:
                res = await self.llm_free.ainvoke([sys, user])
                txt = (res.content or "").strip()
                m = re.search(r"\{.*\}", txt, flags=re.DOTALL)
                if m: txt = m.group(0)
                j = json.loads(txt)
                s_bullets = [safe_str(x,"") for x in (j.get("strengths_bullets") or [])]
                w_bullets = [safe_str(x,"") for x in (j.get("weaknesses_bullets") or [])]
                break
            except Exception as e:
                logging.warning(f"[NARRATIVE BULLETS] LLM error: {e}")

        return s_bullets, w_bullets

    async def _gen_conclusion_free(self, axes: Dict[str,float], company: Dict[str,Any],
                                   body: Dict[str,Any], banlist: List[str]) -> str:
        sys = SystemMessage(content="컨설팅 톤, JSON only.")
        prompt = CONCLUSION_FREE_PROMPT.format(
            axes_json=json.dumps(axes, ensure_ascii=False),
            body_json=json.dumps(body, ensure_ascii=False),
            facts_json=json.dumps({"company":company}, ensure_ascii=False),
            banlist=", ".join(banlist) or "-"
        )
        user = HumanMessage(content=prompt)

        text = ""
        for _ in range(2):
            try:
                res = await self.llm_free.ainvoke([sys, user])
                txt = (res.content or "").strip()
                m = re.search(r"\{.*\}", txt, flags=re.DOTALL)
                if m: txt = m.group(0)
                j = json.loads(txt)
                text = truncate(safe_str(j.get("conclusion"), ""), 3000)
                break
            except Exception as e:
                logging.warning(f"[CONCLUSION] LLM error: {e}")
        return text

    async def _gen_risk_heat(self, company: Dict[str,Any], axes: Dict[str,float], context_blob: str) -> Dict[str,Any]:
        sys = SystemMessage(content="컨설팅 톤, JSON only.")
        prompt = RISK_HEAT_PROMPT.format(company=json.dumps(company,ensure_ascii=False),
                                         axes=json.dumps(axes,ensure_ascii=False),
                                         context=json.dumps({"blob":context_blob[:1200]},ensure_ascii=False))
        user = HumanMessage(content=prompt)
        rows = []
        for _ in range(2):
            try:
                res = await self.llm_free.ainvoke([sys,user])
                txt = (res.content or "").strip()
                m = re.search(r"\{.*\}", txt, flags=re.DOTALL)
                if m: txt = m.group(0)
                j = json.loads(txt)
                rows = j.get("rows") or []
                break
            except Exception as e:
                logging.warning(f"[RISK HEAT] LLM error: {e}")
        # 폴백
        if not rows:
            rows = [
                {"risk":"규제/거버넌스", "likelihood":"중", "impact":"고", "mitigation":"감사·레지던시 체크리스트 및 재인증 계획"},
                {"risk":"영업 파이프라인", "likelihood":"중", "impact":"중", "mitigation":"레퍼런스/채널 확보와 전환율 관리"},
                {"risk":"경쟁/대체재", "likelihood":"중", "impact":"중", "mitigation":"차별 기능·TCO·보안 패키지 강조"},
            ]
        # 정규화
        norm = []
        for r in rows:
            norm.append({
                "risk": truncate(safe_str(r.get("risk"), "—"), 60),
                "likelihood": safe_str(r.get("likelihood"), "중"),
                "impact": safe_str(r.get("impact"), "중"),
                "mitigation": truncate(safe_str(r.get("mitigation"), "—"), 140),
            })
        return {"rows": norm[:7]}

    async def _gen_scenarios(self, company: Dict[str,Any], axes: Dict[str,float], context_blob: str) -> Dict[str,Any]:
        sys = SystemMessage(content="컨설팅 톤, JSON only.")
        prompt = SCENARIO_PROMPT.format(company=json.dumps(company,ensure_ascii=False),
                                        axes=json.dumps(axes,ensure_ascii=False),
                                        context=json.dumps({"blob":context_blob[:1200]},ensure_ascii=False))
        user = HumanMessage(content=prompt)
        data = {}
        for _ in range(2):
            try:
                res = await self.llm_free.ainvoke([sys,user])
                txt = (res.content or "").strip()
                m = re.search(r"\{.*\}", txt, flags=re.DOTALL)
                if m: txt = m.group(0)
                data = json.loads(txt)
                break
            except Exception as e:
                logging.warning(f"[SCENARIOS] LLM error: {e}")
        # 폴백
        def nz(x): return truncate(safe_str(x,"—"), 160)
        if not data:
            data = {
                "upside":  {"drivers":"강한 기술 적합성","catalysts":"대형 레퍼런스 확보","blockers":"규모화 지연","conditions":"채널·파트너 인센티브"},
                "base":    {"drivers":"시장 CAGR 수준","catalysts":"보안인증 통과","blockers":"경쟁 번들링","conditions":"온보딩 KPI 달성"},
                "downside":{"drivers":"채택 지연","catalysts":"—","blockers":"규제 리드타임","conditions":"비용 절감/제품 슬림화"}
            }
        for k in ["upside","base","downside"]:
            if k not in data: data[k] = {}
            data[k] = { "drivers": nz(data[k].get("drivers")),
                        "catalysts": nz(data[k].get("catalysts")),
                        "blockers": nz(data[k].get("blockers")),
                        "conditions": nz(data[k].get("conditions")) }
        return data

    # ----- shared helpers -----
    def _harvest_said_facts(self, context: Dict[str, Any]) -> List[str]:
        said = []
        said.append(context.get("exec_summary",""))
        said.extend(context.get("position_points",[]))
        said.extend(context.get("risks",[]))
        blob = " ".join([s for s in said if s])
        keys = re.findall(r'\b(?:\d+(?:\.\d+)?%?|AHT|CAGR|VPC|PII|온프렘|감사 ?추적|ISO|SOC2|레지던시|on-?prem)\b', blob, flags=re.I)
        uniq = sorted(set([k.strip() for k in keys if k.strip()]))
        return uniq[:20]

    def _normalize_bullets(self, bullets: List[str]) -> List[str]:
        if not bullets: return []
        norm = []
        for b in bullets:
            b = _norm_bullet(b)
            if not b: continue
            b = truncate(b, 140)
            norm.append(b)
        norm = _dedupe_list(norm)
        if len(norm) < 5: return []
        return norm[:8]

    def _fallback_strength_bullets(self, axes: Dict[str,float]) -> List[str]:
        top = [k for k,_ in sorted(axes.items(), key=lambda kv: kv[1], reverse=True)[:3]]
        hi = ", ".join(top) if top else "ai_tech"
        return [
            f"{hi} 축 강점 뚜렷, 제품 방향성 명확",
            "엔터프라이즈 요구 충족, 보안·거버넌스 준비",
            "한국어 처리·도메인 적합성 우수, 초기 고객 설득 용이",
            "온프렘·레지던시 대응, 금융권 채택 장벽 낮춤",
            "강점을 레퍼런스·파트너십으로 전환 필요"
        ]

    def _fallback_weakness_bullets(self, axes: Dict[str,float]) -> List[str]:
        low = [k for k,_ in sorted(axes.items(), key=lambda kv: kv[1])[:3]]
        lo = ", ".join(low) if low else "risk"
        return [
            f"{lo} 축 취약, 단기 실행 리스크 상존",
            "팀·프로세스 스케일업 검증 부족",
            "경쟁사 번들링·대체재 압박 가능",
            "규제 변경 시 재인증·거버넌스 리드타임 부담",
            "파이프라인 전환율·온보딩 KPI 가시화 필요"
        ]

    # ----- PDF -----
    async def _render_pdf(self, company: str, context: Dict[str, Any]) -> Tuple[str, str]:
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
                scale=self.pdf_scale,
                margin={"top":"16mm","bottom":"18mm","left":"14mm","right":"14mm"}
            )
            await browser.close()
        return html_path, pdf_path


# ---------------- Quick Run (dummy) ----------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = ReportWriterAgent()

    dummy_state = {
        "company_name": "FinChat AI",
        "company_meta": {
            "website":"https://finchat.ai",
            "founded_year":"2023",
            "stage":"Seed",
            "headcount":"10-20",
            "region":"KR",
            "tags":["Financial AI","KYC","Contact Center"]
        },
        "fae_score": {
            "total": 8.2,
            "ai_tech": 2.4, "market": 1.8, "traction": 1.3,
            "moat": 1.0, "risk": 0.8, "team": 0.9, "deployability": 1.0
        },
        "confidence": {"mean": 0.62},
        "startup_summary": "금융 상담 자동화로 AHT 18% 감소, FCR 9%p 향상.",
        "tech_summary": "온프렘/VPC/PII 마스킹, 감사추적 등 엔터프라이즈 보안 설계.",
        "market_eval": "국내 금융 AI 연 15% 성장, 규제 친화·감사추적 기능이 채택 핵심.",
        "competitor_summary": "한국어 성능·온프렘 대응·보안 인증에서 경쟁력.",
        "decision_rationale": "시장성/기술성 우수 → 투자 권장.",
        "query": "AI financial advisory startup",

        # 신규: KPI tiles (없으면 자동 N/A)
        "metrics": {
            "nrr":"112%", "grr":"96%", "payback_months": "10",
            "gross_margin":"68%", "win_rate":"29%", "pipeline_x":"3.4x",
            "customers_count":"12", "arr_proxy":"-"
        },

        # 경쟁 매트릭스 (없으면 Generic A/B)
        "competitors": [
            {"name":"CompAlpha","product":"LLM routing, agent assist","security":"SOC2","deployment":"Cloud/On-prem","localization":"EN/KO","pricing":"per seat","references":"Tier-1 bank"},
            {"name":"CompBeta","product":"Voice+Chat suite","security":"ISO27001","deployment":"Cloud","localization":"EN/JP","pricing":"usage","references":"Telecom, BFSI"}
        ],

        # Evidence 예시
        "evidence": {
            "ai_tech": [
                {"text":"온프렘/VPC 지원 및 PII 마스킹 제공", "source_url":"https://finchat.ai/security", "published_at":"2025-09-21", "strength":"strong", "title":"Security Features"}
            ],
            "market": [
                {"text":"국내 금융 AI CAGR 약 15%", "source_url":"https://example.com/kr-fin-ai-2025", "published_at":"2025-05-10", "strength":"medium", "title":"KR Financial AI Report 2025"}
            ],
            "traction": [
                {"text":"상위 금융기관 2곳 PoC 진행(AHT 18%↓)", "source_url":"https://news.example/poc", "published_at":"2025-08-20", "strength":"medium", "title":"PoC Press"}
            ],
            "risk": [
                {"text":"규제 변경 시 데이터 거버넌스 조정 필요", "source_url":"https://gov.example/reg-update", "published_at":"2025-09-01", "strength":"weak", "title":"Regulatory Update"}
            ]
        },

        "lang": "ko"
    }

    result = asyncio.run(agent.run(dummy_state))
    print(result)
    assert result.get("report_path") and os.path.exists(result["report_path"])
    assert os.path.getsize(result["report_path"]) > 0
    print("Smoke test passed:", result["report_path"])
