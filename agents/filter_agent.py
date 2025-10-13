# agents/filter_agent.py
import logging
from urllib.parse import urlparse
from typing import List
from graph.state import PipelineState, CompanyMeta

ALLOWED_TLDS = {".com", ".ai", ".io", ".co", ".net", ".app", ".dev", ".org"}
EXCLUDE_DOMAINS = {
    # 언론/규제/블로그 등 회사 아님
    "cnbc.com",
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "techcrunch.com",
    "wired.com",
    "theverge.com",
    "forbes.com",
    "sec.gov",
    "fca.org.uk",
    "mas.gov.sg",
    "fsb.org",
    "medium.com",
    "reddit.com",
    "pinterest.com",
    "tistory.com",
}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _is_company_like(url: str) -> bool:
    d = _domain(url)
    if not d:
        return False
    if d in EXCLUDE_DOMAINS or any(d.endswith("." + x) for x in EXCLUDE_DOMAINS):
        return False
    # TLD 체크(느슨)
    if not any(d.endswith(tld) for tld in ALLOWED_TLDS):
        return False
    # 서브도메인 너무 많은 경우(뉴스/블로그 서브도메인), 느슨 필터
    if d.count(".") >= 3 and not any(
        part in d for part in ("corp", "inc", "ltd", "llc", "ai", "tech", "app", "cloud")
    ):
        return False
    return True


class FilterAgent:
    """필터 단계: 언론/규제/블로그 도메인 제거, 회사로 보이는 후보만 유지"""

    def __call__(self, state: PipelineState) -> PipelineState:
        before = len(state.companies)
        dedup: dict[str, CompanyMeta] = {}
        for c in state.companies:
            if c.website and _is_company_like(c.website):
                key = _domain(c.website)
                if key and key not in dedup:
                    dedup[key] = c
        state.companies = list(dedup.values())
        logging.info(f"[Filter] candidates: {before} → {len(state.companies)} after filtering")
        return state
