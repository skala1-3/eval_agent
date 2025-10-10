# 🧭 Agentic RAG v2 – AI Financial Advisory Startup Evaluation System

**AI 금융상담 스타트업**을 자동 탐색·요약·평가하고, **투자 가치가 있는 기업만 PDF 보고서로 출력**하는
**LangGraph 기반 Agentic RAG 시스템**입니다. 모든 지능형 단계는 **OpenAI API(GPT-4o-mini/Embeddings)** 를 사용하며,
벡터 스토어는 **로컬 Chroma**를 사용합니다(별도 DB 서버 無).

---

## 🎯 핵심 목표

* Seraph(검색 API)로 후보 스타트업 자동 탐색
* Web 크롤링→요약→라벨링으로 데이터 **Augment**
* RAG로 **근거 기반** 평가 + **7축 F-AI Score** 산출
* **Invest 권장 기업만 PDF** 보고서 생성
* 진행 상황은 **터미널 로그/Progress Bar**로 표시

---

## ⚙️ Quick Start

```bash
# 1) 설치
uv sync

# 2) 그래프 시각화
python graph/visualize.py   # -> outputs/agent_graph.png

# 3) 파이프라인 실행
python graph/run.py --query "AI financial advisory startup"

# (옵션) 단일 기업 보고서 재생성
python scripts/make_report.py --company "FinChat AI" --out outputs/reports/FinChat_AI.pdf
```

> 📌 PDF는 **투자 권장 기준**에 부합하는 기업만 생성됩니다. (규칙: total ≥ 7.5 & mean(conf) ≥ 0.55)

---

## 🧩 Repository Structure

```
📦 agentic-rag-financial-advisory
│
├── agents/
│   ├── seraph_agent.py          # 후보 스타트업 탐색
│   ├── augment_agent.py         # URL 탐색 + 크롤링 + 청크화 + 라벨링
│   ├── rag_retriever_agent.py   # RAG evidence 검색
│   ├── scoring_agent.py         # 7축 점수 및 confidence 계산
│   ├── report_writer_agent.py   # 조건부 PDF 생성
│   └── __init__.py
│
├── graph/
│   ├── state.py                 # PipelineState (pydantic)
│   ├── graph.py                 # LangGraph 전체 플로우
│   ├── visualize.py             # agent_graph.png 시각화
│   └── run.py                   # 메인 실행 엔트리 + 로그 진행 표시
│
├── data/
│   ├── raw/                     # Seraph 원본 결과
│   └── processed/               # 정제된 크롤링 텍스트
│
├── outputs/
│   ├── reports/                 # 조건부 PDF 산출
│   ├── logs/                    # 로그 및 체크포인트
│   └── agent_graph.png
│
├── docs/
│   ├── architecture.md          # v2 아키텍처(본설계)
│   ├── scorecard.md             # 7축 평가 기준표
│   ├── templates/report.html.j2 # PDF 템플릿
│   └── README.md
│
├── scripts/
│   └── make_report.py           # 개별 PDF 생성 유틸
│
├── pyproject.toml               # uv sync용 패키지 명세
└── .gitignore
```

---

## 🧮 F-AI Score (요약)

* **축**: ai_tech(25), market(20), traction(15), moat(10), risk(10), team(10), deployability(10)
* **confidence** = 0.4×coverage + 0.3×diversity + 0.3×recency
* **투자 권장**: total ≥ 7.5 **AND** mean(confidence) ≥ 0.55

---

## 📚 Documents

* 🧱 [Architecture (docs/architecture.md)](https://github.com/skala1-3/eval_agent/blob/main/docs/architecture.md)
* 🧩 [Scorecard (docs/scorecard.md)](https://github.com/skala1-3/eval_agent/blob/main/docs/scorecard.md)
* 📝 [Contributing Guide (CONTRIBUTING.md)](https://github.com/skala1-3/eval_agent/blob/main/docs/CONTRIBUTING.md)

---

## 👥 Contributors (6인)

| 이름     | 역할                  | 브랜치 예시               |
| ------ | ------------------- | -------------------- |
| A      | Discovery/Filter    | `feat/a_discovery`   |
| B      | Augment             | `feat/b_augment`     |
| C      | Vector/RAG          | `feat/c_rag`         |
| D      | Scoring             | `feat/d_scoring`     |
| E      | Report              | `feat/e_report`      |
| 원기훈(F) | Graph/Infra/Logging | `feat/keehoon_graph` |

---

## ✅ 요약

* **Agentic RAG v2**: 단계별 모듈화 + 병렬 확장 + 조건부 PDF
* **OpenAI + Chroma(로컬)**: 셋업 간소화/온보딩 빠름
* **투자 가치가 있는 결과만 출력**해 리소스와 품질을 동시에 관리

### 한창현 정리
## 🔍 Why We Used DuckDuckGo Instead of Seraph API 

### 🧭 Overview

Originally, the **Seraph API** was designed in this project as a conceptual *Search Layer*  
responsible for automatically discovering AI financial advisory startups.  

However, since **Seraph API is not a public or real API**,  
we replaced it with the **DuckDuckGo Search API (`ddgs` library)** —  
a practical, free, and open-source alternative that provides similar functionality.

---

### ⚙️ Implementation Choice

| 구분 | 이유 | 설명 |
|------|------|------|
| ✅ **실행 가능성** | DuckDuckGo는 무료 오픈소스 API로 즉시 사용 가능 (`pip install ddgs`) |
| ✅ **키 불필요** | API Key가 필요 없어 로컬·교육 환경에서 배포 및 실행이 쉬움 |
| ✅ **검색 결과 다양성** | 뉴스, 회사 웹사이트, 블로그 등 다양한 출처에서 결과를 반환 |
| ✅ **JSON 포맷 지원** | `{ "title": "...", "href": "...", "body": "..." }` 구조로 결과 제공 |
| ✅ **RAG 구조 적합성** | 텍스트 중심의 검색 결과로, 후속 요약·임베딩 단계에 바로 활용 가능 |
| ⚙️ **대체 가능성** | 향후 Seraph, SerpAPI, Crunchbase API 등으로 쉽게 교체 가능 |

---

### 🧩 DuckDuckGo vs Seraph (Conceptual Comparison)

| 항목 | **DuckDuckGo** | **Seraph API (Conceptual)** |
|------|----------------|-----------------------------|
| **API 유형** | 오픈소스 웹 검색 API | 스타트업/투자정보 전용 API (가정) |
| **인증 방식** | ❌ 필요 없음 | ✅ API Key 필요 |
| **데이터 형태** | 비정형(웹문서, 뉴스, 블로그 등) | 정형(기업명, 산업, 투자정보 등) |
| **응답 속도** | 빠름 (1~2초 내) | 서비스별 상이 |
| **비용** | 무료 | 보통 월 과금 (예: SerpAPI $50/월) |
| **데이터 품질** | 다양하나 필터링 필요 | 도메인 특화 고정밀도 데이터 |
| **적합 환경** | 교육, 연구, 로컬 개발 | 상용 서비스, 대규모 분석 |
| **Agent 적합도** | ✅ LLM 필터링 병행 시 충분히 실용적 | ✅ 정형데이터로 직접 평가 가능 |

---

### 📊 장단점 요약

| 구분 | 장점 | 단점 |
|------|------|------|
| **DuckDuckGo** | - 완전 무료, 인증 불필요<br>- 설치 간단 (`pip install ddgs`)<br>- 빠른 검색 결과 수집<br>- LLM 필터링과 결합 시 정확도 향상<br>- 교육/실습 환경에 최적 | - 결과가 비정형이라 후속 필터링 필요<br>- 기업정보 세부 데이터(매출, 투자단계 등) 없음<br>- 동일 검색어 결과 변동 가능 |
| **Seraph API** | - 정형 스타트업 데이터 제공<br>- 투자, 산업, 재무 정보 등 도메인 특화<br>- 대규모 분석에 적합 | - 유료/비공개 서비스일 가능성 높음<br>- 키 관리, 요청 제한 존재<br>- 온보딩 및 테스트 어려움 |

---

### 💡 Summary

> “Seraph API was conceptually designed as a startup discovery engine,  
> but we replaced it with the **DuckDuckGo Search API** for real-world execution.  
> This approach maintains automated discovery while avoiding authentication or cost barriers,  
> making it ideal for **local, educational, and experimental RAG pipelines**.”

---

### 🔁 Future Extension

DuckDuckGo is ideal for the prototype phase,  
but can easily be replaced with higher-fidelity APIs in production environments:

| 대체 API | 설명 |
|-----------|------|
| **SerpAPI** | Google 검색 결과를 JSON 형태로 반환 |
| **Crunchbase API** | 스타트업의 실제 투자/산업/팀 데이터를 제공 |
| **NewsAPI / Bing Search** | 최신 뉴스 기반 기업 탐색용 |
| **PitchBook / CB Insights** | 상용 스타트업 데이터베이스 연동 가능 |

---

## 🚀 Gemini 에이전트의 기여 (SeraphAgent 구현)

이 섹션은 Gemini 에이전트가 시스템의 `SeraphAgent` (발견/필터링) 구성 요소를 구현하고 개선하기 위해 수행한 작업을 요약합니다.

### 🎯 핵심 임무 달성

`SeraphAgent`는 다음을 성공적으로 구현했습니다:
1.  **동적 스타트업 발굴:** `duckduckgo_search`를 활용하여 'AI 금융 자문 스타트업'을 실시간으로 웹 검색합니다.
2.  **지능형 필터링 및 형식화:** `langchain_openai` (GPT-4o-mini)를 사용하여 원본 검색 결과를 지능적으로 필터링하고, 기업 정보를 요약하며, 구조화된 JSON 출력으로 형식화합니다.
3.  **정교화된 검색 기준:** 한국 기업을 제외하고 해외 기업(북미, 유럽)에 집중하도록 구성되었습니다.
4.  **수량 제어:** 10개의 유망한 스타트업 후보 목록을 생성합니다.
5.  **견고한 출력:** Pydantic 모델과 LangChain의 `with_structured_output` 기능을 사용하여 유효한 JSON 출력을 보장하며, 결과를 `data/raw/candidates.json`에 저장합니다.

### ⚙️ 설정 및 실행

`SeraphAgent`를 실행하고 `candidates.json` 파일을 생성하려면:

1.  **API 키 설정:**
    *   프로젝트 루트 디렉토리의 `.env` 파일에 OpenAI API 키가 설정되어 있는지 확인하십시오:
        ```
        OPENAI_API_KEY=YOUR_API_KEY_HERE
        ```

2.  **의존성 설치:**
    *   프로젝트 루트 디렉토리(`/Users/changhyun/eval_agent/`)로 이동하십시오.
    *   `uv`를 사용하여 `duckduckgo_search` 및 `langchain-openai`를 포함한 모든 필수 Python 패키지를 설치하십시오:
        ```bash
        uv sync
        ```

3.  **SeraphAgent 실행:**
    *   프로젝트 루트 디렉토리(`/Users/changhyun/eval_agent/`)에서 스크립트를 실행하십시오:
        ```bash
        python3 agents/seraph_agent.py
        ```

### ✅ 예상 출력

성공적으로 실행되면, `data/raw/` 디렉토리에 `candidates.json`이라는 파일이 생성되거나 업데이트됩니다. 이 파일에는 10개의 해외 AI 금융 자문 스타트업 후보 목록이 JSON 배열 형태로 포함되며, 각 후보는 이름, URL, 요약, 카테고리 및 국가 정보를 가집니다.

---
