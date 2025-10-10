import os
import json
import requests
from bs4 import BeautifulSoup
import pdfplumber
from openai import OpenAI
import chromadb
from urllib.parse import urljoin, urlparse
import io
import time
from dotenv import load_dotenv

class AugmentAgent:
    """
    주어진 회사 목록으로 웹 스파이더링을 시작하여 콘텐츠를 수집, 처리, 임베딩하고 
    ChromaDB에 영구 저장하는 에이전트. (크롤링 차단 방지 헤더 적용)
    """
    def __init__(self, openai_api_key, db_path):
        print("AugmentAgent를 초기화합니다.")
        if not openai_api_key:
            raise ValueError("OpenAI API 키가 필요합니다.")
        
        # --- 클라이언트 초기화 ---
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.collection = self.chroma_client.get_or_create_collection(
            name="financial_companies_evidence",
            metadata={"hnsw:space": "cosine"}
        )
        
        # --- ▼▼▼ 1단계 보강: 크롤링 차단 방지를 위한 헤더 추가 ▼▼▼ ---
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.google.com/"
        }
        # --- ▲▲▲ 여기까지 추가 ---
        
    def run(self, companies, crawl_limit_per_company=5):
        """에이전트의 메인 실행 로직"""
        print("데이터 증강 프로세스를 시작합니다.")
        for company in companies:
            company_name = company['name']
            initial_url = company['website']
            
            print(f"\n===== '{company_name}' 회사 처리 시작 =====")
            
            urls_to_visit = [initial_url]
            visited_urls = set()
            crawled_count = 0

            while urls_to_visit and crawled_count < crawl_limit_per_company:
                url = urls_to_visit.pop(0)
                if url in visited_urls:
                    continue
                
                print(f"[{crawled_count + 1}/{crawl_limit_per_company}] 크롤링 중: {url}")
                visited_urls.add(url)
                crawled_count += 1

                try:
                    raw_text, new_links = self._fetch_and_extract(url)
                    
                    if raw_text:
                        enriched_chunks = self._process_and_enrich(raw_text, url, company_name)
                        self._embed_and_store(enriched_chunks)

                    for link in new_links:
                        if link not in visited_urls:
                            urls_to_visit.append(link)
                    
                    time.sleep(1)

                except Exception as e:
                    print(f"  [오류] 처리 중 문제 발생 ({url}): {e}")
                    continue
        
        print("\n===== 모든 회사에 대한 데이터 증강 프로세스 완료 =====")

    def _fetch_and_extract(self, url):
        """주어진 URL에서 콘텐츠를 가져오고 텍스트와 새로운 링크를 추출"""
        # ❗️ 변경점: self.headers 사용, timeout 증가
        response = requests.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '').lower()
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        
        text = ""
        links = []

        if 'html' in content_type:
            soup = BeautifulSoup(response.content, 'html.parser')
            body = soup.find('body')
            if body:
                text = body.get_text(separator='\n', strip=True)
            for link in soup.find_all('a', href=True):
                new_url = urljoin(base_url, link['href']).split('#')[0]
                if urlparse(new_url).netloc == urlparse(base_url).netloc:
                    links.append(new_url)
        elif 'pdf' in content_type:
            with io.BytesIO(response.content) as pdf_file:
                with pdfplumber.open(pdf_file) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
        
        return text, list(set(links))

    def _process_and_enrich(self, raw_text, source_url, company_name):
        """텍스트를 청크화하고 OpenAI로 요약/라벨링 (현재는 테스트용)"""
        chunks = [raw_text[i:i+1000] for i in range(0, len(raw_text), 800)]
        enriched_chunks = []

        for i, chunk_text in enumerate(chunks):
            if len(chunk_text.strip()) < 100: continue
            
            summary = f"Summary of content from {company_name}." 
            labels = ["finance", "AI", company_name.lower().replace(" ", "")]
            
            enriched_chunks.append({
                "text": chunk_text,
                "metadata": {
                    "source": source_url,
                    "company": company_name,
                    "summary": summary,
                    "labels": ", ".join(labels)
                }
            })
        return enriched_chunks

    def _embed_and_store(self, chunks):
        """청크를 임베딩하고 ChromaDB에 저장"""
        if not chunks: return

        texts_to_embed = [chunk['text'] for chunk in chunks]
        
        response = self.openai_client.embeddings.create(
            input=texts_to_embed,
            model="text-embedding-3-small"
        )
        embeddings = [item.embedding for item in response.data]

        metadatas = [chunk['metadata'] for chunk in chunks]
        ids = [f"{chunk['metadata']['source']}-chunk{i}" for i, chunk in enumerate(chunks)]

        self.collection.upsert(
            embeddings=embeddings,
            documents=texts_to_embed,
            metadatas=metadatas,
            ids=ids
        )
        print(f"  [성공] {len(chunks)}개의 청크를 ChromaDB에 저장/업데이트했습니다.")


if __name__ == '__main__':
    load_dotenv()

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 

    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(script_path))
    
    input_file_path = os.path.join(project_root, 'data', 'raw', 'candidates.json')
    db_directory_path = os.path.join(project_root, 'db', 'chroma_db')
    
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            initial_companies = json.load(f)
    except FileNotFoundError:
        print(f"[오류] 입력 파일 '{input_file_path}'를 찾을 수 없습니다.")
        exit()

    try:
        agent = AugmentAgent(openai_api_key=OPENAI_API_KEY, db_path=db_directory_path)
        agent.run(companies=initial_companies, crawl_limit_per_company=5)
    except ValueError as e:
        print(f"에이전트 실행 실패: {e}")
        print("OPENAI_API_KEY가 .env 파일 또는 환경 변수에 올바르게 설정되었는지 확인하세요.")