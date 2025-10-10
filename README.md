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