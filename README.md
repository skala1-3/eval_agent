# 🧭 AI Financial Advisory Startup Evaluation Agent

본 프로젝트는 **AI 기술을 활용하는 금융상담 스타트업**의  
기술력·시장성·리스크를 분석하고, 투자 가능성을 **Agentic RAG 기반으로 자동 평가**하는  
Multi-Agent 시스템을 설계한 실습 과제입니다.

---

## 🎯 Overview

| 항목 | 내용 |
|------|------|
| **주제** | AI 금융상담 스타트업의 정량 평가 및 투자 판단 |
| **핵심 기술** | LangGraph 기반 Multi-Agent + RAG + F-AI Scoring |
| **성과물** | 스타트업별 투자 판단 보고서 (PDF 자동 생성) |
| **참여 인원** | 총 6인 (1반 3조) |
| **담당 지도** | SKALA AI 실습 – Agentic RAG 설계 과제 |

---

## ⚙️ Quick Start

```bash
# 환경 설정
# (둘 중 하나 선택)
pip install -r requirements.txt
# 또는
uv sync

# LangGraph 시각화 생성
python graph/visualize.py

# Agentic RAG 실행
python graph/graph.py
```

결과 보고서는 `/outputs/reports/` 폴더에 저장됩니다.

---

## 🧩 Repository Structure

```
📦 agentic-rag-financial-advisory
│
├── agents/              # 에이전트 모듈 (Seraph, RAG, Scoring, Report 등)
├── graph/               # LangGraph 그래프 정의 및 시각화
├── data/                # 입력 문서 / 사전 데이터
├── outputs/             # PDF 보고서, 시각화 결과
├── docs/                # 설계 문서 및 발표 자료
│   └── project-overview.md   ← 상세 프로젝트 설명
├── requirements.txt     # 의존성 패키지
└── README.md            # (현재 문서)
```

---

## 📚 Documents

* 📄 [프로젝트 상세 설명](./docs/project-overview.md)
* ⚙️ [협업 및 브랜치 관리 가이드](./docs/CONTRIBUTING.md)
* 🗓️ [발표 자료 (PDF)](./docs/output.pdf)

---

## 👥 Contributors

| 이름   | 역할                                           |
| ---- | -------------------------------------------- |
| 원기훈  | System Design / Graph 설계 / Agent Integration |
| 팀원 A | SeraphAgent 개발                               |
| 팀원 B | Data Augmentation / Web Crawler              |
| 팀원 C | RAG Retriever / Embedding                    |
| 팀원 D | Evaluation / Scoring                         |
| 팀원 E | Report Generator / 발표 정리                     |

---

📖 **자세한 프로젝트 개요는 [docs/project-overview.md](./docs/project-overview.md)를 참고하세요.**
