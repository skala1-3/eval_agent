# Vector DB 데이터 가이드

이 디렉토리에는 `augment_agent.py`가 생성한 ChromaDB의 데이터 파일이 저장되어 있습니다.
이 데이터는 사전 임베딩된 기업 정보 벡터를 포함하며, 다른 에이전트들이 재현성 있는 결과를 얻기 위해 사용합니다.

## 사용 방법

`RAGRetrieverAgent` 등 다른 에이전트에서 아래와 같이 `PersistentClient`를 사용하여 DB를 로드할 수 있습니다.

```python
import chromadb

# 프로젝트 루트에서 실행하는 에이전트 기준 경로
db_path = "db/chroma_db" 
client = chromadb.PersistentClient(path=db_path)
collection = client.get_collection("financial_companies_evidence")

# 이제 collection 객체로 쿼리 가능
results = collection.query(query_texts=["AI in finance"], n_results=5)