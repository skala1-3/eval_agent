# 🧭 AI Financial Advisory Startup Evaluation Agent

**AI 금융상담 스타트업 투자 평가 에이전트**

본 프로젝트는 **AI 기술을 핵심으로 하는 금융상담 스타트업**을 탐색하고,
그들의 **기술력·시장성·리스크** 등을 정량적으로 평가하여
**투자 가능성을 자동으로 판별하는 Multi-Agent 시스템**을 설계한 실습 프로젝트입니다.

---

## 📘 Overview

| 항목        | 내용                                               |
| --------- | ------------------------------------------------ |
| **프로젝트명** | AI Financial Advisory Startup Evaluation Agent   |
| **목표**    | 금융 상담을 수행하는 AI 스타트업의 기술력, 시장성, 경쟁력 등을 정량/정성으로 평가 |
| **핵심기술**  | LangGraph 기반 Multi-Agent + Agentic RAG           |
| **성과물**   | 스타트업별 투자 판단 보고서 (PDF)                            |
| **대상**    | AI를 중심 기술로 활용하는 해외 금융상담 스타트업                     |

---

## 💡 Project Background

‘상담 서비스’는 본질적으로 **정성적 판단**이 강해, 객관적 평가 기준을 만들기 어렵습니다.
특히 최근 **AI 기술(LLM, ML 추천엔진, 예측모델)** 이 금융 상담 영역에 빠르게 확산되며
기업의 “AI 기술력”과 “실제 투자 가치”를 **데이터로 검증**하는 수요가 높아지고 있습니다.

이 프로젝트는

> “AI 금융 상담 스타트업의 투자 가능성을 **정량적으로 평가할 수 있는가**?”
> 라는 질문에서 출발하여,
> AI 기술과 RAG 기반 평가 시스템을 활용해 **데이터 기반 투자 판단 구조**를 설계합니다.

---

## 🚀 Key Differentiators

| 구분         | 기존 접근            | 본 프로젝트                                        |
| ---------- | ---------------- | --------------------------------------------- |
| **대상 범위**  | 일반 금융 스타트업       | **AI를 활용한 금융상담 스타트업**                         |
| **데이터 구조** | 비정형 위주 (뉴스, 블로그) | **정형(Seraph, SEC)** + **비정형(Web, Report)** 융합 |
| **분석 방식**  | 수동 리서치/전문가 의존    | **LangGraph Multi-Agent 자동 평가**               |
| **평가 기준**  | 기술력/시장성 중심       | **AI 기술력 포함 7개 항목의 F-AI Score**               |
| **출력물**    | 텍스트 요약           | **정량 점수 + 정성 요약 + 출처 기반 보고서**                 |

---

## 🧩 System Architecture (Layer-based Design)

```
[1] Discovery Layer
 └── SeraphAgent: AI+Finance 키워드 기반 스타트업 탐색
 └── FilterAgent: 관련성 필터링 및 기업 메타데이터 수집

[2] Data Augmentation Layer
 └── WebCrawlerAgent: 공식 웹사이트/블로그/리포트 크롤링
 └── ParserAgent: PDF·HTML 정리 및 기술 문장 추출

[3] Retrieval & RAG Layer
 └── EmbeddingModule: paraphrase-MiniLM-L6-v2
 └── VectorStore: pgvector / Chroma
 └── RAGRetrieverAgent: 관련 문단 검색 및 요약

[4] Evaluation & Scoring Layer
 └── TechEvaluator: AI 기술력 분석
 └── MarketAnalyzer: 시장성·경쟁성 평가
 └── RiskEvaluator: 규제·윤리 리스크 검증
 └── FAIScorer: 정량 스코어 산출 (F-AI Score)

[5] Report Generation Layer
 └── ReportWriterAgent: 기업별 종합 요약 보고서 생성 (Markdown → PDF)
```

## 🧩 Agent Graph Visualization
LangGraph 내장 시각화 결과:
![Agent Graph](./agent_graph.png)

---

## 🧮 F-AI Score (Evaluation Framework)

| 항목         | 비중(%) | 평가 기준                    |
| ---------- | ----- | ------------------------ |
| **AI 기술력** | 25    | AI 모델 적용 수준, 독창성, 기술 투명성 |
| **시장성**    | 20    | 시장 성장률, TAM/SAM, 고객 세그먼트 |
| **성과/지표**  | 15    | 고객수, ARR, 투자단계           |
| **경쟁우위**   | 10    | 진입장벽, 데이터 락인             |
| **리스크**    | 10    | 규제, 윤리, 보안 위험            |
| **팀 역량**   | 10    | AI/금융 전문성, 핵심 인력 구조      |
| **배포현실성**  | 10    | API 배포, 보안·운영체계 완성도      |

> **Total ≥ 7.5 → 투자 추천 / < 7.5 → 보류**

---

## 🧱 Data Structure

### 1️⃣ Structured Layer (Seraph / SEC)

| 필드                | 설명                |
| ----------------- | ----------------- |
| company_name      | 스타트업명             |
| founded_year      | 설립연도              |
| funding_stage     | 투자 단계             |
| headcount         | 인력 규모             |
| investors         | 주요 투자자            |
| regulatory_status | SEC 등록 여부         |
| traction          | 성장률, 사용자 수, ARR 등 |

### 2️⃣ Unstructured Layer (Web / Report)

| 필드                | 설명                           |
| ----------------- | ---------------------------- |
| tech_description  | AI 모델 및 기술 개요                |
| ai_keywords       | GPT, Recommender, ML model 등 |
| market_trends     | 시장 및 경쟁사 동향                  |
| reviews_sentiment | 사용자 반응 요약                    |
| regulatory_risk   | 규제/보안 리스크 언급                 |

### 3️⃣ Metrics Table

| 필드           | 설명        |
| ------------ | --------- |
| metric_key   | 평가 항목 키   |
| value        | 0–10 스케일  |
| unit         | 지표 단위     |
| confidence   | 신뢰도 (0–1) |
| source       | 데이터 출처    |
| last_updated | 갱신일자      |

---

## ⚙️ Tech Stack

| 구분                   | 기술                                 |
| -------------------- | ---------------------------------- |
| **Framework**        | LangGraph, LangChain, Python       |
| **LLM**              | GPT-4o-mini (via OpenAI API)       |
| **Vector DB**        | pgvector / Chroma                  |
| **ETL**              | pandas, requests, BeautifulSoup    |
| **Parsing**          | pdfplumber, PyMuPDF                |
| **Visualization**    | Matplotlib, Markdown Report        |
| **Infra (optional)** | Docker / FastAPI / Jenkins (CI/CD) |

---

## 🧠 Expected Outcome

* **AI 스타트업 탐색 자동화**

  * Seraph 기반으로 ‘AI+Finance’ 스타트업 자동 리스트업
* **기술력 및 시장성 요약**

  * LLM RAG 기반으로 핵심 기술/시장 정보를 요약
* **정량화된 투자 판단**

  * 7축의 F-AI Score 모델로 객관적 평가
* **PDF 보고서 자동 생성**

  * 스타트업별 점수, 요약, 출처, 리스크 분석 포함

---

## 📄 Example Output (요약 예시)

```
회사명: FinChat AI
분야: LLM 기반 투자상담 챗봇
요약: FinChat은 GPT-4 기반 언어모델을 활용하여 개인 투자자 대상 실시간 상담 서비스를 제공함.
AI 기술력: 8.5 / 시장성: 7.8 / 리스크: 6.2 / 종합: 7.9
→ 투자 판단: 추천
주요 근거: 공식 블로그 기술 포스트, CBInsights 2025 리포트
```

---

## 👥 Contributors

| 이름     | 역할                                 |
| ------ | ---------------------------------- |
| 원기훈    | System Design, LangGraph Agent 설계  |
| (팀원 A) | Data Pipeline / Seraph Integration |
| (팀원 B) | AI 기술 요약 / RAG 튜닝                  |
| (팀원 C) | 평가 기준 설계 / Scorecard 정리            |
| (팀원 D) | Report Generation / 발표 자료 작성       |

---

## 🗓️ Submission

* **제출 파일**: `agentic_rag_1반_3조.pdf`
* **GitHub Repository**: [링크 예정]
* **발표 시간**: 과정 마지막날 오후 4시
* **발표 자료**: `README.md` + 시연 Notebook

---

## 🧭 Summary (요약문)

> 본 프로젝트는 AI 기술을 핵심으로 활용하는 금융상담 스타트업을 대상으로,
> 기술력·시장성·리스크를 정량적으로 평가하는 Multi-Agent RAG 시스템을 구축하였다.
> Seraph API를 통한 스타트업 발굴과 웹/보고서 기반 AI 기술 분석을 결합하여
> F-AI Score 모델로 투자 판단을 자동화하고, 보고서를 생성하는 과정을 설계하였다.
