import os
import json
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any
from duckduckgo_search import DDGS
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────
# Configure Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ─────────────────────────────────────────────────────────────
# Pydantic Models for Structured Output
# ─────────────────────────────────────────────────────────────
class Candidate(BaseModel):
    name: str = Field(description="Name of the AI financial advisory startup")
    url: str = Field(description="Valid URL of the startup")
    summary: str = Field(description="Concise one-sentence summary of the startup's services")
    category: str = Field(description="Primary category of the startup (e.g., Robo-Advisory, Wealth Management, Fintech)")
    country: str = Field(description="Country of origin of the startup")

class CandidateList(BaseModel):
    candidates: List[Candidate] = Field(description="List of AI financial advisory startup candidates")

# ─────────────────────────────────────────────────────────────
# 1️⃣ DuckDuckGo Search (Seraph API 대체)
# ─────────────────────────────────────────────────────────────
def search_candidates(query: str, max_results: int = 20) -> List[Dict[str, Any]]:
    """
    Uses DuckDuckGo search to collect startup candidates related to the query.
    This replaces Seraph API.
    """
    results = []
    logging.info(f"🔍 Searching DuckDuckGo for: {query}")

    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "name": r.get("title", ""),
                    "url": r.get("href", ""),
                    "summary": r.get("body", "")
                })
    except Exception as e:
        logging.error(f"DuckDuckGo search failed: {e}")

    logging.info(f"✅ Retrieved {len(results)} raw candidates from search.")
    return results


# ─────────────────────────────────────────────────────────────
# 2️⃣ OpenAI Filtering
# ─────────────────────────────────────────────────────────────
def filter_candidates_with_llm(raw_results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """
    Filters and refines raw search results using GPT-4o-mini.
    Keeps only AI-based financial advisory startups and formats output JSON.
    """
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.error("❌ OPENAI_API_KEY not found in .env file.")
        return []

    # Use with_structured_output to enforce JSON schema
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.3).with_structured_output(CandidateList)

    prompt = f"""
    You are an expert in fintech startup analysis.
    From the list below, select only companies that:
    - Are AI-based (machine learning, chatbot, or LLM usage)
    - Provide financial advisory or investment assistance services
    - Are real startups (exclude media, blogs, or unrelated sites)
    - Exclude companies from South Korea and focus on overseas companies, particularly from North America and Europe.
    Select 10 promising candidates.

    Query: "{query}"
    Raw Results:
    {json.dumps(raw_results, ensure_ascii=False, indent=2)}
    """

    try:
        # The response is now directly a CandidateList object
        response: CandidateList = llm.invoke(prompt)
        filtered_candidates = [candidate.model_dump() for candidate in response.candidates]
        logging.info(f"✅ LLM returned {len(filtered_candidates)} filtered candidates.")
        return filtered_candidates
    except Exception as e:
        logging.error(f"LLM filtering failed: {e}")
        return []


# ─────────────────────────────────────────────────────────────
# 3️⃣ Main Execution
# ─────────────────────────────────────────────────────────────
def run_seraph_agent(query: str = "AI financial advisory startup") -> List[Dict[str, Any]]:
    """
    Full SeraphAgent pipeline: search → filter → save.
    """
    logging.info("--- 🚀 Starting SeraphAgent_v2 (DuckDuckGo + OpenAI) ---")

    # 1. Search
    raw_results = search_candidates(query)

    # 2. Filter with LLM
    refined_results = filter_candidates_with_llm(raw_results, query)

    # 3. Add IDs
    for i, c in enumerate(refined_results):
        c["id"] = f"cand_{i+1:02d}"

    # 4. Save Output
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "candidates.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(refined_results, f, indent=2, ensure_ascii=False)

    logging.info(f"✅ Saved final candidates to {output_path}")
    return refined_results


# ─────────────────────────────────────────────────────────────
# 4️⃣ Entry Point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    candidates = run_seraph_agent()
    if candidates:
        print(json.dumps(candidates, indent=2, ensure_ascii=False))
    else:
        print("❌ No candidates generated.")