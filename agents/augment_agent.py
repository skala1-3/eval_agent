import os
import json
import requests
import logging
from bs4 import BeautifulSoup
import pdfplumber
from openai import OpenAI
import chromadb
from urllib.parse import urljoin, urlparse
import io
import time
from dotenv import load_dotenv

from graph.state import Evidence, PipelineState


ALLOWED_EXTERNAL_DOMAINS = {
    # 신뢰 언론/테크/산업
    "cnbc.com",
    "bloomberg.com",
    "reuters.com",
    "ft.com",
    "techcrunch.com",
    "wired.com",
    "theverge.com",
    "forbes.com",
    "wsj.com",
    # 규제/공시
    "sec.gov",
    "fca.org.uk",
    "mas.gov.sg",
    "europa.eu",
    # 파트너/생태계 (예시)
    "salesforce.com",
    "appexchange.salesforce.com",
    "stripe.com",
}
ALLOWED_PATH_HINTS = (
    "/blog",
    "/news",
    "/press",
    "/case",
    "/stories",
    "/resource",
    "/whitepaper",
    "/report",
)

# 간이 축별 키워드(라벨러)
AXIS_HINTS = {
    "ai_tech": [
        "model",
        "fine-tune",
        "benchmark",
        "agent",
        "retrieval",
        "latency",
        "embedding",
        "LLM",
        "RAG",
    ],
    "market": ["market", "segment", "customers", "advisors", "AUM", "TAM", "growth"],
    "traction": ["ARR", "MRR", "users", "clients", "case study", "won", "deployed", "live"],
    "moat": ["patent", "proprietary", "unique", "defensible", "edge", "advantage"],
    "risk": ["compliance", "SEC", "FCA", "regulation", "privacy", "licen", "risk", "policy"],
    "team": ["founder", "CEO", "CTO", "background", "hiring", "team", "leadership"],
    "deployability": ["on-prem", "VPC", "SOC2", "SAML", "SSO", "SLA", "integration", "SDK", "API"],
}
STRENGTH_BY_DOMAIN = {
    "first_party": "weak",  # 회사 내부 도메인
    "trusted_media": "medium",  # 언론 등
    "regulator": "strong",  # 규제/공시
    "partner": "medium",  # 파트너/생태
}


class AugmentAgent:
    """
    회사 웹/사이트맵/화이트리스트 외부 링크까지 확장 수집 → 임베딩 → Chroma 저장.
    Evidence는 state.chunks에도 누적.
    """

    def __init__(self, openai_api_key: str | None = None, db_path: str | None = None):
        load_dotenv()
        openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OpenAI API 키가 필요합니다.")

        self.openai_client = OpenAI(api_key=openai_api_key)

        self.db_path = db_path or os.path.join(os.getcwd(), "db", "chroma_db")
        os.makedirs(self.db_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.chroma_client.get_or_create_collection(
            name="financial_companies_evidence", metadata={"hnsw:space": "cosine"}
        )

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
            "Referer": "https://www.google.com/",
        }
        self._state_ref: PipelineState | None = None

    def __call__(self, state: PipelineState) -> PipelineState:
        self._state_ref = state
        companies = [c.model_dump() for c in state.companies]
        self.run(companies=companies, crawl_limit_per_company=10)
        logging.info(f"[Augment] state.chunks appended = {len(state.chunks)}")
        return state

    # -------------------- Crawl --------------------
    def run(self, companies, crawl_limit_per_company=10):
        print("데이터 증강 프로세스를 시작합니다.")
        for company in companies:
            company_name = company["name"]
            initial_url = company.get("website")
            company_id = company.get("id")

            print(f"\n===== '{company_name}' 회사 처리 시작 =====")
            seed_links = []
            if initial_url:
                seed_links.append(initial_url)
                seed_links += self._discover_from_sitemap(initial_url)
                seed_links = list(dict.fromkeys(seed_links))  # dedupe

            urls_to_visit = list(seed_links)
            visited_urls = set()
            crawled_count = 0

            while urls_to_visit and crawled_count < crawl_limit_per_company:
                url = urls_to_visit.pop(0)
                if url in visited_urls:
                    continue
                visited_urls.add(url)
                crawled_count += 1
                print(f"[{crawled_count}/{crawl_limit_per_company}] 크롤링 중: {url}")
                try:
                    raw_text, new_links = self._fetch_and_extract(url)
                    if raw_text:
                        enriched = self._process_and_enrich(
                            raw_text, url, company_name, company_id, base_site=initial_url
                        )
                        self._embed_and_store(enriched)

                    # 내부링크 + 화이트리스트 외부만 큐에 추가
                    for link in new_links:
                        if link in visited_urls:
                            continue
                        if self._allow_link(initial_url, link):
                            if any(
                                h in link for h in ALLOWED_PATH_HINTS
                            ) or self._is_external_allowed(initial_url, link):
                                urls_to_visit.append(link)

                    time.sleep(0.6)
                except Exception as e:
                    print(f"  [오류] 처리 중 문제 발생 ({url}): {e}")
                    continue
        print("\n===== 모든 회사에 대한 데이터 증강 프로세스 완료 =====")

    def _discover_from_sitemap(self, site_url: str) -> list[str]:
        out = []
        root = f"{urlparse(site_url).scheme}://{urlparse(site_url).netloc}"
        for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
            sm = root + path
            try:
                r = requests.get(sm, headers=self.headers, timeout=10)
                if r.status_code != 200 or "xml" not in r.headers.get("content-type", ""):
                    continue
                soup = BeautifulSoup(r.content, "xml")
                for loc in soup.find_all("loc"):
                    u = loc.text.strip()
                    if any(h in u for h in ALLOWED_PATH_HINTS):
                        out.append(u.split("#")[0])
            except Exception:
                continue
        return list(dict.fromkeys(out))

    def _allow_link(self, base: str | None, link: str) -> bool:
        if not base:
            return False
        b = urlparse(base).netloc
        u = urlparse(link).netloc
        # 내부 도메인 허용
        if u == b or u.endswith("." + b):
            return True
        # 외부 화이트리스트 도메인 허용
        return self._is_external_allowed(base, link)

    def _is_external_allowed(self, base: str | None, link: str) -> bool:
        u = urlparse(link).netloc
        return any(u == d or u.endswith("." + d) for d in ALLOWED_EXTERNAL_DOMAINS)

    def _extract_published(self, soup: BeautifulSoup) -> str | None:
        """
        간단한 게시일 추출:
        - <time datetime="...">
        - meta[property='article:published_time'|'og:updated_time']
        - meta[itemprop='datePublished'|'dateModified']
        """
        try:
            t = soup.find("time", attrs={"datetime": True})
            if t and t.get("datetime"):
                return t["datetime"].strip()
            for sel, key in [
                ("meta[property='article:published_time']", "content"),
                ("meta[property='og:updated_time']", "content"),
                ("meta[itemprop='datePublished']", "content"),
                ("meta[itemprop='dateModified']", "content"),
            ]:
                m = soup.select_one(sel)
                if m and m.get(key):
                    return m.get(key).strip()
        except Exception:
            pass
        return None

    def _fetch_and_extract(self, url):
        r = requests.get(url, headers=self.headers, timeout=20)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").lower()
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        text, links = "", []
        if "html" in ctype:
            soup = BeautifulSoup(r.content, "html.parser")
            # main/article 우선
            main = soup.find("main") or soup.find("article") or soup.find("body")
            if main:
                for t in main(["script", "style", "noscript", "nav", "footer", "header", "form"]):
                    t.decompose()
                text = main.get_text(separator="\n", strip=True)
            # 게시일 추출 시도 → 텍스트 선두에 마커 삽입
            pub = self._extract_published(soup)
            if pub:
                text = f"[PUBLISHED:{pub}]\n{text}"
            for a in soup.find_all("a", href=True):
                new_url = urljoin(base_url, a["href"]).split("#")[0]
                links.append(new_url)
        elif "pdf" in ctype:
            with io.BytesIO(r.content) as f:
                with pdfplumber.open(f) as pdf:
                    for p in pdf.pages:
                        pt = p.extract_text() or ""
                        text += pt + "\n"

        return text, list(dict.fromkeys(links))

    # -------------------- Enrich/Embed --------------------
    def _guess_axis(self, txt: str) -> str:
        t = (txt or "").lower()
        best_axis, best_hits = "market", 0
        for axis, kws in AXIS_HINTS.items():
            hits = sum(1 for k in kws if k.lower() in t)
            if hits > best_hits:
                best_axis, best_hits = axis, hits
        return best_axis

    def _guess_strength(self, source: str, base_site: str | None) -> str:
        dom = urlparse(source).netloc
        if base_site:
            base = urlparse(base_site).netloc
            if dom == base or dom.endswith("." + base):
                return STRENGTH_BY_DOMAIN["first_party"]
        if any(dom == d or dom.endswith("." + d) for d in ("sec.gov", "fca.org.uk", "mas.gov.sg")):
            return STRENGTH_BY_DOMAIN["regulator"]
        if any(dom == d or dom.endswith("." + d) for d in ALLOWED_EXTERNAL_DOMAINS):
            return STRENGTH_BY_DOMAIN["trusted_media"]
        return "weak"

    def _process_and_enrich(
        self, raw_text, source_url, company_name, company_id=None, base_site=None
    ):
        chunks = [raw_text[i : i + 1200] for i in range(0, len(raw_text), 900)]
        enriched = []
        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) < 120:
                continue
            # 텍스트 선두의 게시일 마커를 메타에 이관
            published = None
            if chunk.startswith("[PUBLISHED:") and "]" in chunk:
                published = chunk[len("[PUBLISHED:") : chunk.find("]")]
                chunk = (
                    chunk[chunk.find("]\n") + 2 :]
                    if "]\n" in chunk
                    else chunk[chunk.find("]") + 1 :]
                )

            axis = self._guess_axis(chunk)
            strength = self._guess_strength(source_url, base_site)
            enriched.append(
                {
                    "text": chunk,
                    "metadata": {
                        "source": source_url,
                        "company": company_name,
                        "company_id": company_id or (company_name or "").lower().replace(" ", ""),
                        "category": axis,
                        "strength": strength,
                        "published": published,
                        "summary": f"{company_name} - {axis} evidence",
                        "labels": axis,
                    },
                }
            )
        return enriched

    def _embed_and_store(self, chunks):
        if not chunks:
            return
        docs = [c["text"] for c in chunks]
        resp = self.openai_client.embeddings.create(input=docs, model="text-embedding-3-small")
        embeds = [d.embedding for d in resp.data]
        metas = [c["metadata"] for c in chunks]
        # 회사별/URL별 고유화: company_id:source#idx
        ids = [f"{m.get('company_id','unknown')}:{m['source']}#{i}" for i, m in enumerate(metas)]

        self.collection.upsert(embeddings=embeds, documents=docs, metadatas=metas, ids=ids)
        print(f"  [성공] {len(chunks)}개의 청크를 ChromaDB에 저장/업데이트했습니다.")

        if self._state_ref is not None:
            for c in chunks:
                m = c["metadata"]
                self._state_ref.chunks.append(
                    Evidence(
                        source=m.get("source"),
                        text=c["text"],
                        category=m.get("category", "market"),
                        strength=m.get("strength", "weak"),
                        published=m.get("published"),
                    )
                )
