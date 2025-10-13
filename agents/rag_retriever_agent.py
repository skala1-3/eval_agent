# agents/rag_retriever_agent.py
import os, logging, requests
from typing import List, Dict, Tuple
from urllib.parse import urlparse
from openai import OpenAI
import chromadb
from bs4 import BeautifulSoup  # HTML 본문 추출용

from graph.state import PipelineState, Evidence, EvidenceCategory

TAVILY_ENDPOINT = "https://api.tavily.com/search"
TAVILY_TIMEOUT = 18

# 한/영 혼용 축 키워드
AXIS_KEYWORDS = {
    "ai_tech": [
        "model",
        "모델",
        "agent",
        "에이전트",
        "benchmark",
        "벤치마크",
        "RAG",
        "retrieval",
        "검색증강",
        "latency",
        "지연",
        "inference",
        "추론",
    ],
    "market": [
        "market",
        "시장",
        "TAM",
        "성장",
        "growth",
        "advisors",
        "운용사",
        "AUM",
        "segment",
        "세그먼트",
    ],
    "traction": [
        "ARR",
        "MRR",
        "매출",
        "users",
        "사용자",
        "clients",
        "고객사",
        "deployed",
        "상용화",
        "case study",
        "레퍼런스",
    ],
    "moat": [
        "proprietary",
        "독점",
        "patent",
        "특허",
        "defensible",
        "unique",
        "차별화",
        "advantage",
        "우위",
    ],
    "risk": [
        "SEC",
        "FCA",
        "규제",
        "regulation",
        "privacy",
        "개인정보",
        "licen",
        "인허가",
        "risk",
        "리스크",
    ],
    "team": ["CEO", "CTO", "founder", "창업자", "리더십", "leadership", "hiring", "채용"],
    "deployability": [
        "on-prem",
        "온프렘",
        "SAML",
        "SSO",
        "SOC2",
        "보안인증",
        "SLA",
        "integration",
        "연동",
        "API",
        "VPC",
    ],
}

# 기본 도메인 가중치 (deployability 축에서 first_party 상향 보정 적용)
BASE_DOMAIN_WEIGHT = {
    "regulator": 1.2,
    "media": 0.8,
    "first_party": 0.25,
    "other": 0.15,
}

ALLOWED_MEDIA = {
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "cnbc.com",
    "techcrunch.com",
    "wired.com",
    "theverge.com",
    "forbes.com",
}
ALLOWED_REGULATORS = {"sec.gov", "fca.org.uk", "mas.gov.sg", "fsb.org"}
DENY_DOMAINS = {
    "reddit.com",
    "medium.com",
    "pdfcoffee.com",
    "pinterest.com",
    "tistory.com",
    "lypydzgy.com",
    "bobhutchins.medium.com",
    "investopedia.com",
}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _domain_type(url: str, base_site: str | None) -> str:
    d = _domain(url)
    if not d:
        return "other"
    if base_site:
        base = _domain(base_site)
        if d == base or d.endswith("." + base):
            return "first_party"
    if any(d == x or d.endswith("." + x) for x in ALLOWED_REGULATORS):
        return "regulator"
    if any(d == x or d.endswith("." + x) for x in ALLOWED_MEDIA):
        return "media"
    return "other"


def _axis_keyword_score(text: str, axis: str) -> float:
    t = (text or "").lower()
    kws = AXIS_KEYWORDS.get(axis, [])
    hits = sum(1 for k in kws if k.lower() in t)
    return min(1.0, hits / max(3, len(kws)))  # 0~1


def _cosine_to_sim(dists: List[float]) -> List[float]:
    # chroma returns distances (cosine). Convert to similarity 1 - d
    return [max(0.0, 1.0 - float(x)) for x in dists]


class RAGRetrieverAgent:
    """
    - Chroma 하이브리드: (A) company_id=ON 결과 + (B) 글로벌 결과 (필터 OFF)
    - Tavily로 외부 기사/문서 보강 → 간이 Evidence 생성
    - 재랭크: sim(임베딩) + axis keyword + domain weight + recency(없으면 0)
    - 도메인 다양성 보장(최종 TopN에서 서로 다른 도메인 최소 min_domain_diversity개)
    """

    def __init__(
        self,
        db_path: str | None = None,
        collection_name: str = "financial_companies_evidence",
        topn_per_axis: int = 5,  # ← 축당 최종 채택 개수
        min_domain_diversity: int = 2,  # ← 서로 다른 도메인 최소 개수
        chroma_topk_each: int = 16,  # ← Chroma에서 가져오는 후보 폭 (company/global 각각)
        tavily_max_results: int = 12,  # ← Tavily에서 가져오는 후보 폭
    ):
        print("🤖 RAGRetrieverAgent 초기화 중...")
        self.openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.tavily_key = os.getenv("TAVILY_API_KEY")
        db_path = db_path or os.path.join(os.getcwd(), "db", "chroma_db")
        self.db = chromadb.PersistentClient(path=db_path)
        self.col = self.db.get_collection(name=collection_name)
        print(f"✅ ChromaDB 컬렉션 '{collection_name}'에 성공적으로 연결했습니다.")

        # 검색/선정 노브
        self.topn_per_axis = max(1, int(topn_per_axis))
        self.min_domain_diversity = max(1, int(min_domain_diversity))
        self.chroma_topk_each = max(4, int(chroma_topk_each))
        self.tavily_max_results = max(4, int(tavily_max_results))

    def __call__(self, state: PipelineState) -> PipelineState:
        return self.invoke(state)

    # -------------------- Tavily --------------------
    def _tavily_search(self, q: str, max_results: int | None = None) -> List[dict]:
        if not self.tavily_key:
            return []
        if max_results is None:
            max_results = self.tavily_max_results
        try:
            payload = {
                "api_key": self.tavily_key,
                "query": q,
                "search_depth": "basic",
                "include_answer": False,
                "include_images": False,
                "max_results": max_results,
                "include_domains": list(ALLOWED_MEDIA | ALLOWED_REGULATORS),
                "exclude_domains": list(DENY_DOMAINS),
            }
            r = requests.post(TAVILY_ENDPOINT, json=payload, timeout=TAVILY_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            cleaned = []
            for h in results:
                u = h.get("url", "")
                if not u:
                    continue
                d = _domain(u)
                if any(d == x or d.endswith("." + x) for x in DENY_DOMAINS):
                    continue
                title = (h.get("title") or "").strip()
                snippet = (h.get("content") or "").strip()
                text = " ".join([title, snippet])
                if len(text) < 220:
                    continue
                # 한국어 컨텐츠 허용(한/영 혼용 시 과도 필터 방지)
                ascii_ratio = sum(1 for ch in text if ord(ch) < 128) / max(1, len(text))
                if ascii_ratio < 0.5:
                    continue
                cleaned.append({"url": u, "title": title, "content": snippet})
            return cleaned
        except Exception as e:
            logging.warning(f"[Tavily] search error: {e}")
            return []

    def _fetch_text(self, url: str) -> str:
        try:
            r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return ""
            if "pdf" in r.headers.get("content-type", "").lower():
                return ""  # PDF는 augment 단계에서 처리
            soup = BeautifulSoup(r.content, "html.parser")
            main = soup.find("main") or soup.find("article") or soup.find("body")
            if main:
                for t in main(["script", "style", "noscript", "nav", "footer", "header"]):
                    t.decompose()
                return main.get_text("\n", strip=True)
        except Exception:
            pass
        return ""

    # -------------------- Main --------------------
    def _embedding(self, texts: List[str]) -> List[List[float]]:
        res = self.openai.embeddings.create(input=texts, model="text-embedding-3-small")
        return [d.embedding for d in res.data]

    def _query_chroma(self, q_embed: List[float], where: dict | None, topk: int | None = None):
        if topk is None:
            topk = self.chroma_topk_each
        kwargs = {"query_embeddings": [q_embed], "n_results": int(topk)}
        if where is not None:
            kwargs["where"] = where
        return self.col.query(**kwargs)

    def _rerank(
        self,
        axis: str,
        base_site: str | None,
        query_embed: List[float],
        pool: List[Tuple[str, str, dict, float]],
        top_n: int,
    ) -> List[Tuple[str, str, dict, float]]:
        """
        pool: (text, source, meta, sim_hint)
        최종점수 = 0.50*sim + 0.25*domain_w + 0.20*axis_kw + 0.05*recency
        """
        # URL 디듀프
        seen_url = set()
        uniq_pool = []
        for t, s, m, sim in pool:
            if s in seen_url:
                continue
            seen_url.add(s)
            uniq_pool.append((t, s, m, sim))

        ranked = []
        for text, source, meta, sim_hint in uniq_pool:
            sim = sim_hint
            axis_kw = _axis_keyword_score(text, axis)

            # 도메인 가중치(축별 보정)
            dtype = _domain_type(source, base_site)
            dw_base = BASE_DOMAIN_WEIGHT[dtype]
            if axis == "deployability" and dtype == "first_party":
                dw = max(dw_base, 0.7)  # 배포/보안 문서는 1차 자료 가중 ↑
            else:
                dw = dw_base

            # 최근성(메타에 있으면 보소 가점)
            rec = 0.3 if (meta and meta.get("published")) else 0.0

            score = 0.50 * sim + 0.25 * dw + 0.20 * axis_kw + 0.05 * rec
            ranked.append((score, text, source, meta))
        ranked.sort(key=lambda x: x[0], reverse=True)

        # 도메인 다양성 우선 선별
        picked: List[Tuple[str, str, dict, float]] = []
        used_domains = set()
        for s, t, u, m in ranked:
            d = _domain(u)
            if d not in used_domains or len(used_domains) < self.min_domain_diversity:
                picked.append((t, u, m, s))
                used_domains.add(d)
            if len(picked) >= top_n:
                break

        # 부족하면 상위에서 채움
        i = 0
        while len(picked) < top_n and i < len(ranked):
            _, t, u, m = ranked[i]
            if (t, u, m, 0.0) not in picked:
                picked.append((t, u, m, 0.0))
            i += 1
        return picked

    def _to_evidence(
        self, axis_key: str, items: List[Tuple[str, str, dict, float]], _company_name: str
    ) -> List[Evidence]:
        evs: List[Evidence] = []
        for text, src, meta, _score in items:
            evs.append(
                Evidence(
                    source=src,
                    text=text,
                    category=meta.get("category", axis_key),
                    strength=meta.get("strength", "weak"),
                    published=meta.get("published"),
                )
            )
        return evs

    def invoke(self, state: PipelineState) -> PipelineState:
        print(f"\n🔍 총 {len(state.companies)}개 회사에 대한 근거 자료 검색을 시작합니다...")
        all_companies: Dict[str, Dict[str, List[Evidence]]] = {}

        evaluation_axes: Dict[EvidenceCategory, str] = {
            "ai_tech": "기술 혁신성 및 독창성",
            "market": "시장 잠재력 및 성장성",
            "team": "팀 역량 및 전문성",
            "moat": "경쟁 환경 및 차별성",
            "risk": "규제 및 법적 리스크",
            "traction": "사업 성과 및 매출/지표",
            "deployability": "도입 용이성·보안·운영",
        }

        for company in state.companies:
            print(f"\n  🏢 '{company.name}' (ID: {company.id}) 처리 중...")
            base_site = getattr(company, "website", None)
            per_axis: Dict[str, List[Evidence]] = {}

            for axis_key, axis_desc in evaluation_axes.items():
                # 1) 질의 생성 + 임베딩
                q = f"{company.name} {axis_desc} evidence"
                try:
                    q_embed = self._embedding([q])[0]
                except Exception as e:
                    logging.warning(f"[RAG] embedding error: {e}")
                    per_axis[axis_key] = []
                    continue

                pool: List[Tuple[str, str, dict, float]] = []

                # 2) (A) company_id=ON 근거
                try:
                    res_a = self._query_chroma(
                        q_embed, {"company_id": company.id}, topk=self.chroma_topk_each
                    )
                    docs_a = res_a.get("documents", [[]])[0]
                    metas_a = res_a.get("metadatas", [[]])[0]
                    dists_a = res_a.get("distances", [[]])[0]
                    sims_a = _cosine_to_sim(dists_a) if dists_a else [0.0] * len(docs_a)
                    for t, m, sim in zip(docs_a, metas_a, sims_a):
                        pool.append(
                            (
                                t,
                                m.get("source", "Unknown"),
                                {
                                    "category": m.get("category", axis_key),
                                    "strength": m.get("strength", "weak"),
                                    "published": m.get("published"),
                                },
                                sim,
                            )
                        )
                except Exception as e:
                    logging.warning(f"[RAG] chroma(company) error: {e}")

                # 3) (B) 필터 OFF 글로벌 근거
                try:
                    res_b = self._query_chroma(q_embed, None, topk=self.chroma_topk_each)
                    docs_b = res_b.get("documents", [[]])[0]
                    metas_b = res_b.get("metadatas", [[]])[0]
                    dists_b = res_b.get("distances", [[]])[0]
                    sims_b = _cosine_to_sim(dists_b) if dists_b else [0.0] * len(docs_b)
                    for t, m, sim in zip(docs_b, metas_b, sims_b):
                        pool.append(
                            (
                                t,
                                m.get("source", "Unknown"),
                                {
                                    "category": m.get("category", axis_key),
                                    "strength": m.get("strength", "weak"),
                                    "published": m.get("published"),
                                },
                                sim,
                            )
                        )
                except Exception as e:
                    logging.warning(f"[RAG] chroma(global) error: {e}")

                # 4) (C) Tavily 외부 보강
                if self.tavily_key:
                    tav_q = f"{company.name} {axis_desc}"
                    hits = self._tavily_search(tav_q, max_results=self.tavily_max_results)
                    for h in hits:
                        url = h.get("url")
                        if not url:
                            continue
                        txt = (h.get("content") or h.get("title") or "").strip()
                        if len(txt) < 400:  # 짧으면 직접 페치
                            fetched = self._fetch_text(url)
                            if len(fetched) > len(txt):
                                txt = fetched
                        if len(txt) < 400:
                            continue
                        dtype = _domain_type(url, getattr(company, "website", None))
                        strength = "weak"
                        if dtype == "media":
                            strength = "medium"
                        if dtype == "regulator":
                            strength = "strong"
                        meta = {"category": axis_key, "strength": strength, "published": None}
                        # 간단 sim 힌트(텍스트 임베딩 1회로 near-NN)
                        try:
                            txt_embed = self._embedding([txt[:1200]])[0]
                            sim = _cosine_to_sim(
                                self.col.query(query_embeddings=[txt_embed], n_results=1).get(
                                    "distances", [[1.0]]
                                )[0]
                            )[0]
                        except Exception:
                            sim = 0.0
                        pool.append((txt, url, meta, sim))

                # 5) 재랭크 + 다양성 보장 TopN
                ranked = self._rerank(axis_key, base_site, q_embed, pool, top_n=self.topn_per_axis)
                evs = self._to_evidence(axis_key, ranked, company.name)
                per_axis[axis_key] = evs

            axis_counts = {k: len(v) for k, v in per_axis.items()}
            logging.info(
                f"[RAG] retrieved[{company.id}] axis_counts={axis_counts} total={sum(axis_counts.values())}"
            )
            all_companies[company.id] = per_axis

        state.retrieved_evidence = all_companies
        print("\n✅ 모든 회사에 대한 근거 자료 검색을 완료했습니다.")
        return state
