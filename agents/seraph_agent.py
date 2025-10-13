import os, json, logging, requests
from serpapi import GoogleSearch
from dotenv import load_dotenv
from typing import List, Dict, Any
from urllib.parse import urlparse

from graph.state import PipelineState, CompanyMeta

TAVILY_ENDPOINT = "https://api.tavily.com/search"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def _root_origin(u: str) -> str:
    try:
        p = urlparse(u)
        if not p.scheme or not p.netloc:
            return u
        return f"{p.scheme}://{p.netloc}"
    except Exception:
        return u


def _infer_company_name(title: str, url: str) -> str:
    """
    검색 결과의 장문 타이틀에서 노이즈 제거.
    - ' | ' 또는 ' – ' 구분자를 기준으로 좌측 토큰 우선
    - 도메인 루트의 호스트명을 참고 (예: finchat.ai -> Finchat)
    """
    host = (urlparse(url).netloc or "").split(":")[0]
    host_core = host.split(".")[-2] if "." in host else host
    host_guess = host_core.capitalize() if host_core else ""
    cand = title.split(" | ")[0].split(" – ")[0].strip() or host_guess
    return cand if 1 <= len(cand) <= 50 else host_guess


class SeraphAgent:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("SERPAPI_KEY")
        self.tavily_key = os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("❌ SERPAPI_KEY not found in .env file")

    def _search_google(self, query: str, num_results: int = 2) -> List[Dict[str, Any]]:
        logging.info(f"🔍 Searching Google (via SerpApi) for: {query}")
        search = GoogleSearch(
            {
                "q": query,
                "num": num_results,
                "hl": "en",
                "engine": "google",
                "api_key": self.api_key,
            }
        )
        results = search.get_dict().get("organic_results", [])
        # 정규화: 홈 도메인/이름, 중복 도메인 제거
        cleaned = []
        for r in results:
            link = r.get("link")
            title = r.get("title", "") or ""
            if not link:
                continue
            website = _root_origin(link)
            name = _infer_company_name(title, link)
            cleaned.append({"name": name, "url": website, "summary": r.get("snippet", "")})
        seen = set()
        uniq = []
        for c in cleaned:
            host = urlparse(c["url"]).netloc
            if host in seen:
                continue
            seen.add(host)
            uniq.append(c)
        return uniq

    def _tavily_seed(self, query: str, max_results: int = 12) -> List[str]:
        if not self.tavily_key:
            return []
        try:
            r = requests.post(
                TAVILY_ENDPOINT,
                json={
                    "api_key": self.tavily_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": False,
                    "max_results": max_results,
                },
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            urls = [x["url"] for x in data.get("results", []) if x.get("url")]
            return urls
        except Exception as e:
            logging.warning(f"[Seraph] tavily seed error: {e}")
            return []

    def __call__(self, state: PipelineState) -> PipelineState:
        logging.info("--- 🚀 Starting SeraphAgent (SerpApi+Tavily) ---")
        raw = self._search_google(state.query)

        # candidates
        company_metas = [
            CompanyMeta(
                id=f"cand_{i+1:02d}",
                name=c["name"],
                website=c["url"],
                tags=[c["summary"]] if c["summary"] else [],
            )
            for i, c in enumerate(raw)
        ]
        state.companies = company_metas
        logging.info(f"✅ Retrieved {len(company_metas)} candidates from Google search.")

        # 저장(+보조 시드 urls.json)
        try:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            raw_dir = os.path.join(project_root, "data", "raw")
            os.makedirs(raw_dir, exist_ok=True)
            with open(os.path.join(raw_dir, "candidates.json"), "w", encoding="utf-8") as f:
                json.dump([c.model_dump() for c in company_metas], f, indent=2, ensure_ascii=False)

            if self.tavily_key:
                extra = self._tavily_seed(state.query, max_results=12)
                with open(os.path.join(raw_dir, "seed_urls.json"), "w", encoding="utf-8") as f:
                    json.dump(extra, f, indent=2, ensure_ascii=False)
                logging.info(f"💾 Saved seed_urls.json ({len(extra)} urls)")
        except Exception as e:
            logging.error(f"⚠️ Failed to save raw files: {e}")

        return state


if __name__ == "__main__":
    test_state = PipelineState(query="AI fintech robo-advisory wealth management startup")
    agent = SeraphAgent()
    final_state = agent(test_state)
    print(f"✅ {len(final_state.companies)} candidates saved to data/raw/candidates.json")
