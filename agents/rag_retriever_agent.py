# agents/rag_retriever_agent.py

import os
import logging
from typing import List, Dict, Tuple
from openai import OpenAI
import chromadb

# rank-bm25가 없더라도 동작하도록 폴백 지원
try:
    from rank_bm25 import BM25Okapi  # pip install rank-bm25

    _HAS_BM25 = True
except Exception:
    BM25Okapi = None
    _HAS_BM25 = False

from graph.state import PipelineState, CompanyMeta, Evidence, EvidenceCategory

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 축별 키워드(가벼운 축 적합성 부스트/폴백 랭킹에 사용)
# ─────────────────────────────────────────────────────────────
AXIS_KEYWORDS: Dict[EvidenceCategory, List[str]] = {
    "ai_tech": [
        "model",
        "llm",
        "inference",
        "rag",
        "fine-tune",
        "architecture",
        "on-prem",
        "latency",
        "embedding",
    ],
    "market": ["tam", "cagr", "market", "growth", "adoption", "segment", "share"],
    "traction": ["arr", "mrr", "revenue", "customers", "users", "contracts", "logo", "paying"],
    "moat": ["patent", "proprietary", "moat", "barrier", "exclusive", "differentiation"],
    "risk": ["regulation", "regulatory", "sec", "compliance", "privacy", "liability", "risk"],
    "team": ["founder", "ceo", "cto", "background", "experience", "hiring", "headcount"],
    "deployability": [
        "integration",
        "sla",
        "on-prem",
        "vpc",
        "security",
        "soc2",
        "iso27001",
        "sso",
        "audit",
    ],
}


def _norm(xs: List[float]) -> List[float]:
    if not xs:
        return []
    lo, hi = min(xs), max(xs)
    if hi == lo:
        return [0.0 for _ in xs]
    return [(x - lo) / (hi - lo) for x in xs]


def _distance_to_similarity(dists: List[float]) -> List[float]:
    # chroma distance → 간단 유사도(가까울수록 크다)
    return [1.0 / (1.0 + float(d)) for d in dists]


def _keyword_hits(text: str, kws: List[str]) -> int:
    t = (text or "").lower()
    return sum(1 for k in kws if k and k.lower() in t)


def _bm25_scores(query: str, docs: List[str], axis: str) -> List[float]:
    """BM25 점수(없으면 경량 키워드 카운트로 대체)."""
    q = (query + " " + " ".join(AXIS_KEYWORDS.get(axis, []))).lower()
    if _HAS_BM25:
        tokens = [(d or "").lower().split() for d in docs]
        bm25 = BM25Okapi(tokens)
        return list(bm25.get_scores(q.split()))
    # 폴백: 단순 키워드 히트 수(정규화 전 원시값)
    kws = AXIS_KEYWORDS.get(axis, [])
    return [_keyword_hits(d or "", [*kws, *q.split()]) for d in docs]


def _hybrid_rank(
    search_query: str, docs: List[str], dists: List[float], axis: EvidenceCategory
) -> Tuple[List[int], List[float]]:
    sims = _distance_to_similarity(dists)  # 벡터 유사도
    bm25 = _bm25_scores(search_query, docs, axis)  # 렉시컬 점수
    kw = [
        _keyword_hits(d or "", AXIS_KEYWORDS.get(axis, [])) for d in docs
    ]  # 약한 축 키워드 부스트

    sim_n = _norm(sims)
    bm25_n = _norm(bm25)
    kw_n = _norm(kw)

    final = [0.6 * sn + 0.35 * bn + 0.05 * kn for sn, bn, kn in zip(sim_n, bm25_n, kw_n)]
    order = sorted(range(len(docs)), key=lambda i: final[i], reverse=True)
    return order, final


class RAGRetrieverAgent:
    """
    회사/축별 하이브리드 검색(벡터 TopK → BM25/키워드 재랭크 → Evidence 생성)
    """

    def __init__(
        self, db_path: str | None = None, collection_name: str = "financial_companies_evidence"
    ):
        print("🤖 RAGRetrieverAgent 초기화 중...")
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        db_path = db_path or os.path.join(os.getcwd(), "db", "chroma_db")
        self.db_client = chromadb.PersistentClient(path=db_path)
        self.collection = self.db_client.get_collection(name=collection_name)
        print(f"✅ ChromaDB 컬렉션 '{collection_name}'에 성공적으로 연결했습니다.")

    def __call__(self, state: PipelineState) -> PipelineState:
        return self.invoke(state)

    def _generate_search_query(self, axis: str, company_name: str) -> str:
        prompt = f"""
        당신은 투자 심사역을 위한 검색 쿼리 생성 전문가입니다.
        스타트업 '{company_name}'에 대해 다음 평가 항목을 검증하기 위한 가장 효과적인 검색 질문을 한 문장으로 만들어주세요.
        질문은 해당 스타트업의 구체적인 정보(기술, 시장, 팀, 재무 등)를 최대한 이끌어낼 수 있도록 구체적으로 작성해야 합니다.
        평가 항목: "{axis}"
        """
        try:
            res = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=100,
            )
            return res.choices[0].message.content.strip().strip('"')
        except Exception as e:
            logger.warning(f"쿼리 생성 오류(axis={axis}): {e}")
            return f"{company_name} {axis}"

    def _embed_query(self, text: str) -> List[float]:
        return (
            self.openai_client.embeddings.create(input=[text], model="text-embedding-3-small")
            .data[0]
            .embedding
        )

    def invoke(self, state: PipelineState) -> PipelineState:
        print(f"\n🔍 총 {len(state.companies)}개 회사에 대한 근거 자료 검색을 시작합니다...")
        all_companies_evidence: Dict[str, Dict[str, List[Evidence]]] = {}

        evaluation_axes: Dict[EvidenceCategory, str] = {
            "ai_tech": "기술 혁신성 및 독창성",
            "market": "시장 잠재력 및 성장성",
            "team": "팀 역량 및 전문성",
            "moat": "경쟁 환경 및 차별성",
            "risk": "규제 및 법적 리스크",
            "traction": "사업 성과 및 매출/지표",
            "deployability": "도입 용이성·보안·운영",
        }

        TOPK = 50  # 벡터 1차 후보
        TOPN = 3  # 최종 Evidence 개수

        for company in state.companies:
            print(f"\n  🏢 '{company.name}' (ID: {company.id}) 처리 중...")
            ev_per_axis: Dict[str, List[Evidence]] = {}

            for axis_key, axis_desc in evaluation_axes.items():
                # 1) 쿼리 + 임베딩
                q = self._generate_search_query(axis_desc, company.name)
                try:
                    qvec = self._embed_query(q)
                except Exception as e:
                    logger.warning(f"임베딩 실패(axis={axis_key}, company={company.id}): {e}")
                    ev_per_axis[axis_key] = []
                    continue

                try:
                    # 2) 벡터 TopK (+ 회사 필터)
                    res = self.collection.query(
                        query_embeddings=[qvec],
                        n_results=TOPK,
                        where={"company_id": company.id},
                        include=["documents", "metadatas", "distances"],
                    )
                    docs = res.get("documents", [[]])[0] or []
                    metas = res.get("metadatas", [[]])[0] or []
                    dists = res.get("distances", [[]])[0] or []

                    if not docs:
                        ev_per_axis[axis_key] = []
                        continue

                    # 3) 하이브리드 재랭크
                    order, final = _hybrid_rank(q, docs, dists, axis_key)

                    # 4) Evidence 구성(+ 축 키워드 부스트에 따른 weak→medium 승급)
                    evs: List[Evidence] = []
                    axis_kws = AXIS_KEYWORDS.get(axis_key, [])
                    for i in order[:TOPN]:
                        text, meta = docs[i], metas[i]
                        strength = meta.get("strength", "weak")
                        if strength == "weak" and _keyword_hits(text, axis_kws) >= 2:
                            strength = "medium"
                        evs.append(
                            Evidence(
                                source=meta.get("source", "Unknown"),
                                text=text,
                                category=meta.get("category", axis_key),
                                strength=strength,
                                published=meta.get("published"),
                            )
                        )
                    ev_per_axis[axis_key] = evs

                except Exception as e:
                    print(f"      - 🚨 문서 검색 중 오류 발생: {e}")
                    ev_per_axis[axis_key] = []

            axis_counts = {k: len(v) for k, v in ev_per_axis.items()}
            logging.info(
                f"[RAG] retrieved[{company.id}] axis_counts={axis_counts} total={sum(axis_counts.values())}"
            )
            all_companies_evidence[company.id] = ev_per_axis

        state.retrieved_evidence = all_companies_evidence
        print("\n✅ 모든 회사에 대한 근거 자료 검색을 완료했습니다.")
        return state


# --- 로컬 테스트 ---
if __name__ == "__main__":
    try:
        agent = RAGRetrieverAgent()
        init = PipelineState(
            query="AI financial advisory startup",
            companies=[
                CompanyMeta(id="acme-corp", name="Acme Corp", website="https://acme.example.com"),
                CompanyMeta(
                    id="beta-fi", name="Beta Finance", website="https://betafi.example.com"
                ),
            ],
        )
        out = agent(init)
        for company_id, evmap in out.retrieved_evidence.items():
            print(f"\n🏢 Company ID: {company_id}")
            for axis, evs in evmap.items():
                print(f"  - {axis} ({len(evs)}개)")
                for ev in evs:
                    print(f"    • [{ev.strength}] {ev.source} :: {ev.text[:80]}...")
    except Exception as e:
        print(f"테스트 오류: {e}")
