# agents/seraph_agent.py (SerpApi 버전 + JSON 저장 + LangGraph 호환)
import os, json, logging
from serpapi import GoogleSearch
from dotenv import load_dotenv
from typing import List, Dict, Any
from graph.state import PipelineState, CompanyMeta

# ────────────────────────────────────────────────
# 로깅 설정
# ────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class SeraphAgent:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("SERPAPI_KEY")
        if not self.api_key:
            raise ValueError("❌ SERPAPI_KEY not found in .env file")

    def _search_google(self, query: str, num_results: int = 20) -> List[Dict[str, Any]]:
        """SerpApi를 이용해 AI 금융 스타트업 후보 검색"""
        logging.info(f"🔍 Searching Google (via SerpApi) for: {query}")
        search = GoogleSearch({
            "q": query,
            "num": num_results,
            "hl": "en",
            "engine": "google",
            "api_key": self.api_key
        })
        results = search.get_dict().get("organic_results", [])
        return [
            {
                "name": r.get("title", ""),
                "url": r.get("link", ""),
                "summary": r.get("snippet", "")
            }
            for r in results if r.get("link")
        ]

    def __call__(self, state: PipelineState) -> PipelineState:
        """LangGraph에서 실행될 메인 호출 함수"""
        logging.info("--- 🚀 Starting SeraphAgent (SerpApi-Google) ---")

        # 1️⃣ 검색 수행
        raw = self._search_google(state.query)

        # 2️⃣ 검색 결과를 CompanyMeta로 매핑
        company_metas = [
            CompanyMeta(
                id=f"cand_{i+1:02d}",
                name=c["name"],
                website=c["url"],
                tags=[c["summary"]] if c["summary"] else [],
            )
            for i, c in enumerate(raw)
        ]

        # 3️⃣ state 업데이트
        state.companies = company_metas
        logging.info(f"✅ Retrieved {len(company_metas)} candidates from Google search.")

        # 4️⃣ 결과 저장 (data/raw/candidates.json)
        try:
            # run.py 실행 환경에서도 안정적으로 경로 인식
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            output_dir = os.path.join(project_root, "data", "raw")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "candidates.json")

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump([c.model_dump() for c in company_metas], f, indent=2, ensure_ascii=False)

            logging.info(f"💾 Saved candidates to {output_path}")

        except Exception as e:
            logging.error(f"⚠️ Failed to save candidates.json: {e}")

        return state


# ────────────────────────────────────────────────
# 독립 실행 (테스트용)
# ────────────────────────────────────────────────
if __name__ == "__main__":
    # 단독 테스트 시: state 객체 생성 → 실행
    test_state = PipelineState(query="AI fintech robo-advisory wealth management startup")
    test_agent = SeraphAgent()
    final_state = test_agent(test_state)

    print(f"✅ {len(final_state.companies)} candidates saved to data/raw/candidates.json")
