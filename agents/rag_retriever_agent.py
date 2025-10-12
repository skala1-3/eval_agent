# agents/rag_retriever_agent.py

import os
from typing import List, Dict
from openai import OpenAI
import chromadb

# 실제 프로젝트의 상태 및 모델 정의를 가져옵니다.
from graph.state import PipelineState, CompanyMeta, Evidence, EvidenceCategory

class RAGRetrieverAgent:
    """
    각 회사와 평가 축에 따라 ChromaDB에서 구조화된 근거(Evidence)를 검색하는 에이전트.
    """
    def __init__(self, db_path: str = "./data/processed/chroma_db", collection_name: str = "startup_data"):
        """
        RAGRetrieverAgent를 초기화합니다.
        """
        print("🤖 RAGRetrieverAgent 초기화 중...")
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        try:
            self.db_client = chromadb.PersistentClient(path=db_path)
            self.collection = self.db_client.get_collection(name=collection_name)
            print(f"✅ ChromaDB 컬렉션 '{collection_name}'에 성공적으로 연결했습니다.")
        except Exception as e:
            print(f"🚨 ChromaDB 연결 실패: {e}")
            raise

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
                max_tokens=100
            )
            return response.choices[0].message.content.strip().strip('"')
        except Exception as e:
            print(f"쿼리 생성 중 오류 발생 (축: {axis}): {e}")
            return f"{company_name}의 {axis}에 대한 정보"

    def invoke(self, state: PipelineState) -> PipelineState:
        """
        후보 회사 목록을 순회하며 각 평가 축에 대한 근거를 검색하고 상태를 업데이트합니다.
        """
        print(f"\n🔍 총 {len(state.companies)}개 회사에 대한 근거 자료 검색을 시작합니다...")
        
        all_companies_evidence: Dict[str, Dict[str, List[Evidence]]] = {}
        
        # scorecard.md에서 정의된 7축 평가 기준을 가져옵니다.
        # 실제로는 scorecard.md를 파싱하거나 상수로 관리하는 것이 좋습니다.
        evaluation_axes: Dict[EvidenceCategory, str] = {
            "ai_tech": "기술 혁신성 및 독창성",
            "market": "시장 잠재력 및 성장성",
            "team": "팀 역량 및 전문성",
            "moat": "경쟁 환경 및 차별성", # EvidenceCategory에 맞게 수정
            "risk": "규제 및 법적 리스크",
            "traction": "사업 모델 및 수익성", # EvidenceCategory에 맞게 수정
            "deployability": "재무 건전성 및 투자 매력도", # EvidenceCategory에 맞게 수정
        }

        for company in state.companies:
            print(f"\n  🏢 '{company.name}' (ID: {company.id}) 처리 중...")
            evidence_per_axis: Dict[str, List[Evidence]] = {}

            for axis_key, axis_description in evaluation_axes.items():
                print(f"    - 평가 축 '{axis_description}' 검색...")
                
                search_query = self._generate_search_query(axis_description, company.name)
                print(f"      - 생성된 쿼리: \"{search_query}\"")
                
                try:
                    results = self.collection.query(
                        query_texts=[search_query],
                        n_results=3,
                        # AugmentAgent가 저장한 메타데이터를 기반으로 필터링
                        where={"company_id": company.id}
                    )
                    
                    retrieved_evidences: List[Evidence] = []
                    documents = results.get('documents', [[]])[0]
                    metadatas = results.get('metadatas', [[]])[0]

                    if not documents:
                        print("      - 근거를 찾지 못했습니다.")
                    else:
                        for text, meta in zip(documents, metadatas):
                            # 메타데이터에서 정보를 추출하여 Evidence 객체 재구성
                            evidence = Evidence(
                                source=meta.get("source", "Unknown"),
                                text=text,
                                category=meta.get("category", axis_key), # 저장된 카테고리 우선 사용
                                strength=meta.get("strength", "weak"),
                                published=meta.get("published"),
                            )
                            retrieved_evidences.append(evidence)
                        print(f"      - {len(retrieved_evidences)}개의 구조화된 근거를 찾았습니다.")
                    
                    evidence_per_axis[axis_key] = retrieved_evidences

                except Exception as e:
                    print(f"      - 🚨 문서 검색 중 오류 발생: {e}")
                    evidence_per_axis[axis_key] = []

            all_companies_evidence[company.id] = evidence_per_axis

        # PipelineState의 새 필드에 검색 결과 전체를 업데이트
        state.retrieved_evidence = all_companies_evidence
        print("\n✅ 모든 회사에 대한 근거 자료 검색을 완료했습니다.")
        
        return state

# --- 로컬 테스트를 위한 코드 ---
if __name__ == '__main__':
    # 테스트 전, AugmentAgent가 ChromaDB에 데이터를 저장했다고 가정합니다.
    # collection.add(documents=[...], metadatas=[{"company_id": "...", "source": "..."}])
    try:
        retriever_agent = RAGRetrieverAgent()

        # 가상의 PipelineState 생성 (Seraph/FilterAgent가 생성한 결과)
        initial_state = PipelineState(
            query="AI financial advisory startup",
            companies=[
                CompanyMeta(id="acme-corp", name="Acme Corp", website="https://acme.example.com"),
                CompanyMeta(id="beta-fi", name="Beta Finance", website="https://betafi.example.com"),
            ]
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