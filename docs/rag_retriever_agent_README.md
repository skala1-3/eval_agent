# 🧭 Agentic RAG v2 — **RAGRetriever 파트 README**

## 📘 1. 개요
> **RAGRetriever 단계**는 **ChromaDB**에서 후보 기업별/평가 축별 **근거(Evidence)를 검색**하여
> 다음 에이전트(**Scoring**)가 사용할 수 있도록 구조화하여 전달합니다.

본 README는 **RAGRetriever 로직 및 테스트 실행 방법** 중심으로 구성되어 있습니다.

---

## ⚙️ 2. 핵심 로직

### 🧩 (A) `agents/rag_retriever_agent.py` 로직 요약

**LLM 기반 동적 쿼리 생성**
- 각 평가 축(axis)에 대해 GPT-4o-mini를 사용하여 **검색에 최적화된 질문을 동적으로 생성**합니다.
- 단순 키워드 검색이 아닌, 문맥을 이해하는 시맨틱 검색의 효율을 극대화합니다.
```python
# 예시 프롬프트
prompt = f"""
스타트업 '{company_name}'에 대해 다음 평가 항목을 검증하기 위한
가장 효과적인 검색 질문을 한 문장으로 만들어주세요.
평가 항목: "{axis}"
"""
````

**메타데이터 기반 정밀 필터링**

  - ChromaDB에 벡터 검색을 실행할 때, **`company_id` 메타데이터 필터**를 반드시 사용합니다.
  - 다른 회사의 정보가 실수로 검색 결과에 포함되는 것을 원천 차단하여 검색의 정확성을 보장합니다.

<!-- end list -->

```python
results = self.collection.query(
    query_texts=[search_query],
    n_results=3,
    where={"company_id": company.id} # <-- 핵심 필터링
)
```

**`Evidence` 객체 재구성**

  - ChromaDB에서 반환된 `documents`와 `metadatas`를 조합하여 `graph.state`에 정의된 `Evidence` Pydantic 모델로 변환합니다.
  - 이를 통해 파이프라인의 모든 데이터가 일관된 스키마를 유지하도록 합니다.

---

### 🧪 (B) 테스트 체계

  - **목표**: 실제 ChromaDB 환경을 모방하여 에이전트의 핵심 기능(쿼리 생성, 검색, 구조화) 검증
  - **테스트 유형**
    1.  **정상 검색 (Normal Retrieval)**
        → DB에 데이터가 존재하는 회사 ID로 검색 시, `Evidence` 객체들이 정상적으로 반환되는지 확인
    2.  **결과 없음 (No Results)**
        → DB에 데이터가 없는 회사 ID로 검색 시, 각 축에 대해 빈 리스트(`[]`)가 반환되는지 확인
  - **사전 조건**: 테스트 실행 전, `AugmentAgent` 등을 통해 테스트용 데이터가 ChromaDB에 저장되어 있어야 함

## 📝 RAGRetriever & Scoring 연동 주요 수정사항 요약
이번 업데이트에서는 RAGRetrieverAgent를 개발하고 ScoringAgent와의 데이터 흐름을 완벽하게 연동하여, AI 기반의 정밀한 근거 검색과 정량 평가가 유기적으로 연결되도록 파이프라인을 개선했습니다.

## 1. RAGRetrieverAgent 신규 개발 🧭
ChromaDB에서 각 회사의 평가 근거를 정밀하게 검색하는 RAGRetrieverAgent를 개발했습니다.

- LLM 기반 동적 쿼리 생성: gpt-4o-mini를 활용하여 각 평가 축에 최적화된 검색 질문을 동적으로 생성합니다.

- 메타데이터 정밀 필터링: company_id로 필터링된 벡터 검색을 수행하여 다른 회사의 정보가 섞이지 않도록 보장합니다.

- 구조화된 출력: 검색 결과를 Evidence Pydantic 모델로 변환하여 파이프라인의 데이터 일관성을 유지합니다.

## 2. ScoringAgent 로직 수정 🧮
RAGRetrieverAgent의 결과물을 직접 사용하도록 ScoringAgent의 데이터 입력 소스를 변경했습니다.

- (기존) state.chunks의 모든 데이터를 대상으로 단순 키워드 매칭을 수행하던 비효율적인 방식

- (변경) RAGRetrieverAgent가 미리 정제하고 필터링한 state.retrieved_evidence를 입력으로 받아 점수 계산에만 집중하도록 역할을 명확히 분리했습니다.

- 결과: 불필요한 중복 필터링 로직(_matches_company 등)을 제거하여 코드를 간소화하고, AI 검색 결과를 활용해 평가의 정확도를 높였습니다.

## 3. PipelineState 확장 🔗
두 에이전트를 연결하는 다리 역할을 하도록 graph/state.py의 PipelineState를 수정했습니다.

- retrieved_evidence 필드 추가: RAGRetrieverAgent의 구조화된 출력물을 ScoringAgent에 전달하기 위한 전용 데이터 필드를 추가했습니다.

- 데이터 흐름: AugmentAgent → ChromaDB → RAGRetrieverAgent → state.retrieved_evidence → ScoringAgent 로 이어지는 데이터 파이프라인을 완성했습니다.

-----

## 🗂️ 3. 파일 구조 (RAGRetriever 중심)

```
agents/
  └── rag_retriever_agent.py      # RAGRetrieverAgent 로직 (쿼리생성·검색·구조화)
data/
  └── processed/chroma_db/        # 로컬 ChromaDB 저장 경로
graph/
  ├── state.py                    # PipelineState / Evidence 스키마
  └── graph.py, run.py            # 그래프 조립 및 CLI 실행
tests/
  └── test_rag_retriever_agent.py # 정상 검색 / 결과 없음 케이스 테스트
```

-----

## 🚀 4. 실행 방법

### 🔹 A) 파이프라인 스모크 실행

```bash
uv sync
python -m graph.run --query "AI financial advisory startup"
```

> ※ `AugmentAgent`가 ChromaDB에 데이터를 저장한 후에 실행해야 의미 있는 결과를 확인할 수 있습니다.

-----

### 🔹 B) 단위 테스트

```bash
# 루트에서 실행
PYTHONPATH=. uv run pytest -s -k rag_retriever
```

  - `-k rag_retriever`: `rag_retriever`가 포함된 테스트 함수만 특정하여 실행

-----

## 📊 5. 테스트 시나리오 요약

| 시나리오 | 구성 | 기대 결과 |
|-----------|-------|------------|
| **정상 검색** | ChromaDB에 `company-A`의 데이터 존재<br>메타데이터에 `company_id` 포함 | `state.retrieved_evidence['company-A']`에<br>각 축별로 `Evidence` 객체 리스트가 채워짐 |
| **결과 없음** | ChromaDB에 `company-B`의 데이터 부재 | `state.retrieved_evidence['company-B']`에<br>각 축별로 빈 리스트(`[]`)가 채워짐 |

-----

## 🧰 6. 트러블슈팅

| 문제 | 원인/해결 |
|------|-------------|
| `ModuleNotFoundError: graph` | `graph/__init__.py` 생성 + `PYTHONPATH=.` 로 실행 |
| `ChromaDB 연결 실패` | DB 경로 오류 또는 DB 미생성<br>→ `AugmentAgent`를 먼저 실행하여 DB를 생성했는지 확인 |
| `검색 결과 없음` | 1. `AugmentAgent`가 `company_id`를 메타데이터에 저장하지 않음<br>2. 생성된 검색 쿼리의 품질이 낮음 → 프롬프트 튜닝 고려 |
| `OpenAI API 오류` | `OPENAI_API_KEY` 환경 변수 누락 또는 오류 |

-----

## ✅ 7. PR 전 체크리스트

  - [v] `agents/rag_retriever_agent.py` 핵심 로직 반영 (동적 쿼리, `company_id` 필터)
  - [v] `graph/state.py`에 `retrieved_evidence` 필드 추가됨
  - [v] `tests/test_rag_retriever_agent.py` 통과
  - [v] 문서/로그/비밀키 노출 없음
  - [v] `ScoringAgent`가 `state.retrieved_evidence`를 사용하도록 수정되었는지 확인

-----

```
```