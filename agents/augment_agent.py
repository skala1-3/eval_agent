# agents/augment_agent.py

import json
import os # os 모듈을 임포트합니다.
import requests
from bs4 import BeautifulSoup

class AugmentAgent:
    # (이 클래스 부분은 이전과 동일합니다. 수정할 필요 없습니다.)
    def __init__(self, ai_model_client=None):
        self.ai_client = ai_model_client
        print("AugmentAgent가 활성화되었습니다.")

    def _summarize_with_ai(self, text):
        print(f"AI 요약 요청 (테스트): {text[:40]}...")
        return f"이 텍스트는 {text[:20]}...에 대한 AI 요약입니다."

    def _label_with_ai(self, text):
        print(f"AI 라벨링 요청 (테스트): {text[:40]}...")
        return ["AI", "핀테크", "투자", "자동화", "데이터"]
        
    def run(self, input_path, output_path):
        print(f"데이터 처리 시작: {input_path} -> {output_path}")
        
        with open(input_path, 'r', encoding='utf-8') as f:
            companies = json.load(f)

        all_chunks = []

        for company in companies:
            company_id = company['id']
            company_name = company['name']
            url = company['url']
            print(f"--- 처리 중: {company_name} ---")
            
            try:
                response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                full_text = ' '.join([p.get_text() for p in soup.find_all('p')])
                
                chunk_size = 1000
                text_chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
                
                for i, chunk_text in enumerate(text_chunks):
                    if len(chunk_text.strip()) < 50: continue
                    
                    summary = self._summarize_with_ai(chunk_text)
                    labels = self._label_with_ai(chunk_text)
                    
                    chunk_data = {
                        "chunk_id": f"{company_id}_chunk_{i}",
                        "company_id": company_id,
                        "company_name": company_name,
                        "source_url": url,
                        "original_text": chunk_text.strip(),
                        "summary": summary,
                        "labels": labels
                    }
                    all_chunks.append(chunk_data)

            except requests.exceptions.RequestException as e:
                print(f"오류 발생 ({company_name}): {e}")
                continue

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_chunks, f, indent=2, ensure_ascii=False)

        print(f"\n--- 성공! '{output_path}' 파일이 생성되었습니다. ---")
        return output_path

# --- ▼▼▼ 이 아랫부분을 수정했습니다 ▼▼▼ ---
if __name__ == '__main__':
    print("Augment Agent를 단독으로 실행합니다.")
    
    # 현재 스크립트 파일의 절대 경로를 찾습니다.
    script_path = os.path.abspath(__file__)
    # 스크립트가 있는 디렉토리 ('.../eval_agent/agents')
    script_dir = os.path.dirname(script_path)
    # 프로젝트 루트 디렉토리 ('.../eval_agent')
    project_root = os.path.dirname(script_dir)

    # 프로젝트 루트를 기준으로 파일들의 절대 경로를 생성합니다.
    input_file = os.path.join(project_root, 'data', 'raw', 'candidates.json')
    output_file = os.path.join(project_root, 'data', 'processed', 'chunks.json')

    # 1. 에이전트 인스턴스 생성
    agent = AugmentAgent()
    
    # 2. 에이전트 실행
    agent.run(input_path=input_file, output_path=output_file)