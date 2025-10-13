# agents/rag_retriever_agent.py

import os
import logging
from typing import List, Dict
from openai import OpenAI
import chromadb

# 실제 프로젝트의 상태 및 모델 정의를 가져옵니다.
from graph.state import PipelineState, CompanyMeta, Evidence, EvidenceCategory


class RAGRetrieverAgent:
    """
    각 회사와 평가 축에 따라 ChromaDB에서 구조화된 근거(Evidence)를 검색하는 에이전트.
    """

    def __init__(
        self, db_path: str | None = None, collection_name: str = "financial_companies_evidence"
    ):
        """
        RAGRetrieverAgent를 초기화합니다.
        """
        print("🤖 RAGRetrieverAgent 초기화 중...")
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        db_path = db_path or os.path.join(os.getcwd(), "db", "chroma_db")
        self.db_client = chromadb.PersistentClient(path=db_path)
        self.collection = self.db_client.get_collection(name=collection_name)
        print(f"✅ ChromaDB 컬렉션 '{collection_name}'에 성공적으로 연결했습니다.")

    def __call__(self, state: PipelineState) -> PipelineState:
        return self.invoke(state)  # 기존 invoke 재사용

    def _generate_search_query(self, axis: str, company_name: str) -> str:
        """
        평가 축과 회사 이름을 기반으로 검색에 최적화된 질문을 생성합니다.
        (이전 코드와 동일)
        """
        prompt = f"""
        당신은 투자 심사역을 위한 검색 쿼리 생성 전문가입니다.
        스타트업 '{company_name}'에 대해 다음 평가 항목을 검증하기 위한 가장 효과적인 검색 질문을 한 문장으로 만들어주세요.
        질문은 해당 스타트업의 구체적인 정보(기술, 시장, 팀, 재무 등)를 최대한 이끌어낼 수 있도록 구체적으로 작성해야 합니다.

        평가 항목: "{axis}"
        """
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=100,
            )
            return response.choices[0].message.content.strip().strip('"')
        except Exception as e:
            print(f"쿼리 생성 중 오류 발생 (축: {axis}): {e}")
            return f"{company_name}의 {axis}에 대한 정보"

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

        for company in state.companies:
            print(f"\n  🏢 '{company.name}' (ID: {company.id}) 처리 중...")
            ev_per_axis: Dict[str, List[Evidence]] = {}

            for axis_key, axis_description in evaluation_axes.items():
                search_query = self._generate_search_query(axis_description, company.name)
                try:
                    vec = (
                        self.openai_client.embeddings.create(
                            input=[search_query], model="text-embedding-3-small"
                        )
                        .data[0]
                        .embedding
                    )

                    results = self.collection.query(
                        query_embeddings=[vec],  # ← query_texts 대신 임베딩 직접 전달
                        n_results=3,
                        where={"company_id": company.id},
                    )
                    docs = results.get("documents", [[]])[0]
                    metas = results.get("metadatas", [[]])[0]
                    evs: List[Evidence] = []
                    for text, meta in zip(docs, metas):
                        evs.append(
                            Evidence(
                                source=meta.get("source", "Unknown"),
                                text=text,
                                category=meta.get("category", axis_key),
                                strength=meta.get("strength", "weak"),
                                published=meta.get("published"),
                            )
                        )
                    ev_per_axis[axis_key] = evs
                except Exception as e:
                    print(f"      - 🚨 문서 검색 중 오류 발생: {e}")
                    ev_per_axis[axis_key] = []

            # ★ 회사별 axis 개수 로깅
            axis_counts = {k: len(v) for k, v in ev_per_axis.items()}
            logging.info(
                f"[RAG] retrieved[{company.id}] axis_counts={axis_counts} total={sum(axis_counts.values())}"
            )

            all_companies_evidence[company.id] = ev_per_axis

        state.retrieved_evidence = all_companies_evidence
        print("\n✅ 모든 회사에 대한 근거 자료 검색을 완료했습니다.")
        return state


# --- 로컬 테스트를 위한 코드 ---
if __name__ == "__main__":
    # 테스트 전, AugmentAgent가 ChromaDB에 데이터를 저장했다고 가정합니다.
    # collection.add(documents=[...], metadatas=[{"company_id": "...", "source": "..."}])
    try:
        retriever_agent = RAGRetrieverAgent()

        # 가상의 PipelineState 생성 (Seraph/FilterAgent가 생성한 결과)
        initial_state = PipelineState(
            query="AI financial advisory startup",
            companies=[
                CompanyMeta(id="acme-corp", name="Acme Corp", website="https://acme.example.com"),
                CompanyMeta(
                    id="beta-fi", name="Beta Finance", website="https://betafi.example.com"
                ),
            ],
        )

        final_state = retriever_agent.invoke(initial_state)

        print("\n--- 최종 상태의 검색 결과 ---")
        for company_id, evidence_data in final_state.retrieved_evidence.items():
            print(f"\n🏢 Company ID: {company_id}")
            for axis, evidences in evidence_data.items():
                print(f"  - Axis: {axis} ({len(evidences)}개)")
                for ev in evidences:
                    print(f"    - [Source: {ev.source}] {ev.text[:80]}...")

    except Exception as e:
        print(f"\n테스트 실행 중 오류가 발생했습니다: {e}")
