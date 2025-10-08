# 🧭 Agentic RAG v2 – AI Financial Advisory Startup Evaluation System

## 0️⃣ 프로젝트 개요

> AI 기술을 활용하는 금융상담 스타트업을 대상으로
> 기술력·시장성·리스크 등을 정량 평가하여 **투자 가치가 있는 기업만 PDF 보고서로 출력**하는
> **LangGraph 기반 Agentic RAG 시스템**이다.

### 핵심 목표

* Seraph(검색 API)로 후보 스타트업 자동 탐색
* Web 크롤링·요약·라벨링을 통한 데이터 보강 (Augment)
* RAG로 근거 검색 + 7축 **F-AI Score** 평가
* **Invest 권장 기업만 PDF 보고서 생성**
* 모든 과정은 **로컬 VectorDB(Chroma)** 기반, DB 서버 無
* 모든 지능형 단계는 **OpenAI API(GPT-4o-mini, Embeddings)** 이용

---

## 1️⃣ 폴더 구조

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
│   ├── architecture.md          # (본 문서)
│   ├── scorecard.md             # 7축 평가 기준표
│   ├── templates/report.html.j2 # PDF 템플릿
│   └── README.md
│
├── pyproject.toml               # uv sync용 패키지 명세
└── .gitignore
```

---

## 2️⃣ 실행 예시

```bash
uv sync
python graph/run.py --query "AI financial advisory startup"
```

---

## 3️⃣ 파이프라인 구조 (LangGraph)

```
[SeraphAgent] → [Filter] → [AugmentAgent]
                           ↓
                     [RAGRetrieverAgent]
                           ↓
                     [ScoringAgent]
                           ↓
                     [ReportWriterAgent]
```

* 각 노드는 독립적인 **Agent** 클래스로 구현
* 병렬 fan-out 가능 (회사별 병렬 평가)
* 각 Agent는 `PipelineState`를 주고받으며, 자신 책임 영역만 수정

---

## 4️⃣ 상태 스키마 (graph/state.py)

```python
class CompanyMeta(BaseModel):
    id: str
    name: str
    website: str | None = None
    founded_year: int | None = None
    stage: str | None = None
    headcount: int | None = None
    region: str | None = None
    tags: list[str] = []

class Evidence(BaseModel):
    source: str
    text: str
    category: Literal[
        "ai_tech","market","traction","moat","risk","team","deployability"]
    strength: Literal["weak","medium","strong"] = "weak"
    published: str | None = None

class ScoreItem(BaseModel):
    key: str
    value: float
    confidence: float
    notes: str = ""
    evidence: list[Evidence] = []

class ScoreCard(BaseModel):
    items: list[ScoreItem]
    total: float
    decision: Literal["invest","hold","conditional"]

class PipelineState(BaseModel):
    query: str
    companies: list[CompanyMeta] = []
    chunks: list[Evidence] = []
    scorecard: dict[str, ScoreCard] = {}
    reports: dict[str, str] = {}
```

---

## 5️⃣ 각 Agent의 역할

| Agent                 | 핵심 기능                                     | 주요 입력/출력                      | 구현 요약                                                   |
| --------------------- | ----------------------------------------- | ----------------------------- | ------------------------------------------------------- |
| **SeraphAgent**       | SerpApi/검색 API로 AI+금융 상담 키워드 후보 50~100 수집 | query → companies             | API 호출 or LLM URL 제안                                    |
| **Filter (내부)**       | 비관련/중복/비AI 기업 제거, 상위 20~30                | companies → companies         | 키워드·도메인 기반 규칙                                           |
| **AugmentAgent**      | 회사별 공식 URL 탐색 → 크롤링 → 텍스트 정제/라벨링/청크화      | companies → chunks (Evidence) | OpenAI + requests + BeautifulSoup + pdfplumber + Chroma |
| **RAGRetrieverAgent** | 축별 질의 프롬프트로 evidence 상위 2~3 선택            | chunks → filtered chunks      | Chroma cosine search                                    |
| **ScoringAgent**      | 7축 평가 점수 및 confidence 계산                  | evidence → scorecard          | 신호 강도 기반 scoring rule                                   |
| **ReportWriterAgent** | “투자 추천” 기업만 PDF 생성                        | scorecard → reports           | Jinja2 템플릿 + WeasyPrint PDF                             |

---

## 6️⃣ 평가 지표 (7축 F-AI Score)

| 축             | 정의           | 신호 강도별 점수 가중치                   | 비중 |
| ------------- | ------------ | ------------------------------- | -- |
| ai_tech       | AI 기술 구체성/심도 | weak +1 / medium +2 / strong +3 | 25 |
| market        | 시장 규모/세그먼트   | ↑                               | 20 |
| traction      | 지표/성과 존재     | ↑                               | 15 |
| moat          | 경쟁우위         | ↑                               | 10 |
| risk          | 규제/보안 리스크 관리 | ↑                               | 10 |
| team          | 팀 전문성        | ↑                               | 10 |
| deployability | 배포/운영 현실성    | ↑                               | 10 |

**confidence(0~1)**
= 0.4×coverage + 0.3×diversity + 0.3×recency

**결정식**

```python
total = Σ(weight * score) / 10
decision = "invest" if total>=7.5 and mean(conf)>=0.55 else "hold"
```

---

## 7️⃣ PDF 생성 조건

* PDF는 **투자 가치가 있다고 판단된 기업만** 생성한다.
* 기준:

  * `total ≥ 7.5`
  * `mean(confidence) ≥ 0.55`
* 그 외 기업은 “skip” 처리 후 로그에만 기록한다.

```python
if scorecard.total >= 7.5 and mean_conf >= 0.55:
    generate_pdf()
else:
    log.info(f"[skip] {company.name}: not recommended")
```

---

## 8️⃣ PDF 사양 (docs/templates/report.html.j2)

* 생성 도구: **WeasyPrint** (HTML → 2단 PDF)
* 기본 서식:

  1. 표지(회사명, 총점, 핵심요약)
  2. Scorecard(표 + 레이더차트)
  3. Company Snapshot
  4. AI 기술력 (evidence 2~3개)
  5. 시장성 및 경쟁력
  6. 성과/트랙션
  7. 리스크/준법
  8. 팀 역량
  9. 배포 현실성
  10. 결론 및 추천
  11. 출처(하이퍼링크)
* **레이더차트**: matplotlib 생성 후 PNG 삽입
* **폰트**: Noto Sans / Noto Serif (CJK 포함)
* **md→pdf 변환은 선택** (WeasyPrint를 기본으로 채택)

---

## 9️⃣ 로깅 및 진행 표시 (graph/run.py)

* **logging + rich.Progress** 조합
* 콘솔 + 로그 파일 동시 출력
  → 단계별 진행상황 표시(Discovery → Augment → Scoring → Report)
* 체크포인트: `/outputs/logs/run_YYYYMMDD_HHMM.log`

예시:

```
▶ Discovery/Filter     | ██████████ 1/1  0:00:01
▶ Augment (crawl+chunk)| ███████▌  12/30 0:00:25
▶ RAG+Scoring          | ████▍     10/30 0:00:37
▶ Report (PDF)         | ██▍       5/30  0:00:12
```

---

## 🔟 패키지 명세 (pyproject.toml)

```toml
[project]
name = "agentic-rag-financial-advisory"
requires-python = ">=3.11"
dependencies = [
  "openai>=1.50.0",
  "langgraph>=0.6.9",
  "chromadb>=1.1.1",
  "beautifulsoup4>=4.14.2",
  "pdfplumber>=0.11.7",
  "pymupdf>=1.26.4",
  "pandas>=2.3.3",
  "matplotlib>=3.9.0",
  "weasyprint>=61.0",
  "rich>=13.7.0",
]

[project.optional-dependencies]
dev = ["ruff>=0.6.9", "black>=24.8.0", "pytest>=8.3.0"]
```

---

## 1️⃣1️⃣ 팀 역할 (6인 기준)

| 팀원      | 역할               | 담당 파일                                  | 주요 산출          |
| ------- | ---------------- | -------------------------------------- | -------------- |
| A       | Discovery/Filter | seraph_agent.py                        | 후보 리스트업        |
| B       | Augment          | augment_agent.py                       | Evidence 청크 생성 |
| C       | Vector/RAG       | rag_retriever_agent.py                 | evidence 검색    |
| D       | Scoring          | scoring_agent.py + docs/scorecard.md   | 점수 계산          |
| E       | Report           | report_writer_agent.py + templates     | PDF 템플릿        |
| F (원기훈) | Graph/Infra      | graph/graph.py + run.py + visualize.py | 파이프라인 통합 & 로그  |

---

## 1️⃣2️⃣ 설계 의의

| 항목                 | 이유                           |
| ------------------ | ---------------------------- |
| **Agentic RAG 구조** | 단계별 모듈화로 병렬·리트라이·교체 용이       |
| **OpenAI 중심 설계**   | 요약/분류/임베딩 품질과 속도를 균일하게 확보    |
| **Chroma 사용**      | DB 설정 없이 바로 동작 (온보딩 속도↑)     |
| **PDF 우선 설계**      | “무엇을 보여줄지”가 명확하면 데이터 흐름이 단순화 |
| **조건부 출력**         | 불필요한 리소스 절약, 보고서 품질 관리 용이    |
