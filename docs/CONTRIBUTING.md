# 🤝 Contributing Guide  
**AI Financial Advisory Startup Evaluation Agent (6인 협업 프로젝트)**  

이 문서는 본 프로젝트에서 팀원들이 일관된 방식으로 협업하기 위한  
📁 **폴더 구조**, 🌿 **브랜치 전략**, 🧩 **역할 분담**, 🧠 **워크플로우**를 정의합니다.

---

## 🧱 1️⃣ Repository Structure

```

📦 agentic-rag-financial-advisory
│
├── agents/                      # 각 에이전트 모듈
│   ├── seraph_agent.py          # 스타트업 탐색 (Seraph API)
│   ├── data_augment_agent.py    # 웹/문서 크롤링
│   ├── rag_retriever_agent.py   # 문서 검색 및 요약
│   ├── scoring_agent.py         # F-AI Score 계산
│   ├── report_writer_agent.py   # 보고서 생성
│   └── __init__.py
│
├── graph/                       # LangGraph 연결 구조
│   ├── graph.py                 # 전체 파이프라인 정의
│   ├── state.py                 # 상태(StateGraph) 정의
│   └── visualize.py             # agent_graph.png 생성
│
├── data/                        # 입력 데이터
│   ├── raw/                     # 원본 문서
│   └── processed/               # 정제된 데이터
│
├── outputs/                     # 산출물
│   ├── reports/                 # PDF 보고서
│   ├── agent_graph.png          # LangGraph 시각화 결과
│   └── logs/
│
├── docs/                        # 문서/발표자료
│   ├── project-overview.md      # 상세 프로젝트 설명
│   ├── CONTRIBUTING.md          # (현재 문서)
│   └── output.pdf
│
├── pyproject.toml               # 공통 패키지
├── README.md                    # 요약본
└── .gitignore

```

---

## 🌿 2️⃣ Branch Strategy

| 브랜치명 | 역할 | 비고 |
|-----------|------|------|
| `main` | 안정화 버전 (보호 브랜치) | 직접 push 금지 |
| `dev` | 통합 테스트용 | 모든 기능 병합용 |
| `feat/{이름}` | 개인 작업 브랜치 | ex) `feat/keehoon`, `feat/seoyoungjae` |

### 🔧 브랜치 생성 예시
```bash
git switch -c feat/keehoon_graph
```

---

## 🧩 3️⃣ Commit Convention (Gitmoji)

| 타입                         | 예시                                                | 의미        |
| -------------------------- | ------------------------------------------------- | --------- |
| `:sparkles: feat:`         | `:sparkles: feat: add TechEvaluatorAgent`         | 새로운 기능 추가 |
| `:bug: fix:`               | `:bug: fix: incorrect Seraph API parsing`         | 버그 수정     |
| `:memo: docs:`             | `:memo: docs: update project README`              | 문서 수정     |
| `:construction: chore:`    | `:construction: chore: add base folder structure` | 구조/설정     |
| `:white_check_mark: test:` | `:white_check_mark: test: add RAG retriever test` | 테스트 추가    |

---

## ⚙️ 4️⃣ Environment Setup

**Python 3.11 이상 권장**

### 가상환경 생성

```bash
python -m venv .venv
source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
uv sync
(혹은)
pip install -r requirements.txt
```

### 주요 패키지 (pyproject.toml)

지금의 의존성은 예시이고, 필요에 따라 제거/추가합니다.

```
"beautifulsoup4>=4.14.2",
"chromadb>=1.1.1",
"langchain>=0.3.27",
"langgraph>=0.6.9",
"openai>=2.2.0",
"pandas>=2.3.3",
"pdfplumber>=0.11.7",
"pgvector>=0.4.1",
"pymupdf>=1.26.4",
"requests>=2.32.5",
```

> ✅ 로컬마다 `.venv` 폴더를 만들어 독립 환경 유지
> ✅ DB 연결정보, API key는 `.env` 파일로 관리 (.gitignore에 포함)

---

## 👥 5️⃣ Team Roles

| 역할                                | 담당자  | 작업 브랜치 예시            |
| --------------------------------- | ---- | -------------------- |
| Seraph / Discovery Agent          | 팀원 A | `feat/a_discovery`   |
| Data Augmentation (Web)           | 팀원 B | `feat/b_augment`     |
| RAG / Retrieval                   | 팀원 C | `feat/c_rag`         |
| Evaluation / Scoring              | 팀원 D | `feat/d_scoring`     |
| Report Generator                  | 팀원 E | `feat/e_report`      |
| Graph Integration / System Design | 원기훈  | `feat/keehoon_graph` |

---

## 🧠 6️⃣ Workflow (협업 순서)

```bash
1️⃣ 브랜치 생성
git checkout -b feat/이름

2️⃣ 코드 작성 및 커밋
git add .
git commit -m ":sparkles: feat: add ScoringAgent"

3️⃣ 원격 저장소 푸시
git push origin feat/이름

4️⃣ Pull Request 생성
→ base: dev / compare: feat/이름

5️⃣ 코드 리뷰
→ 리뷰어 확인 후 승인 시 dev 병합

6️⃣ 최종 병합
→ dev → main (팀 리드 승인 후)
```

---

## 🧾 7️⃣ Checklist Before Merge

| 항목             | 설명                        |
| -------------- | ------------------------- |
| ✅ 코드 실행 확인     | Agent 단위로 실행 테스트          |
| ✅ 커밋 메시지 규칙 준수 | Gitmoji + 타입 형식           |
| ✅ 충돌 해결        | merge 전 rebase / pull dev |
| ✅ PR 설명 작성     | 변경 내용 / 테스트 결과 명시         |
| ✅ 리뷰 승인        | 최소 1명 이상 승인 후 병합          |

---

## 📄 8️⃣ Folder Ownership (담당 권한)

| 폴더         | 담당자    | 주의사항                       |
| ---------- | ------ | -------------------------- |
| `agents/`  | 개별 담당자 | 각자 책임 영역, PR로 병합           |
| `graph/`   | 통합 담당자 | Agent 간 연결 구조 관리           |
| `docs/`    | 전체 공유  | README, CONTRIBUTING, 발표자료 |
| `outputs/` | 공용     | 자동 생성물 (PDF, 이미지 등)        |
| `data/`    | 공유     | 크롤링 데이터 저장소                |

---

## 🧭 9️⃣ 협업 시 유의사항

* **FastAPI / UI는 선택사항** — 본 실습의 핵심은 **LangGraph 기반 Agent 설계**
* **개발 충돌 방지** — 각자 Agent 단위로 모듈화 후 PR
* **문서 일관성 유지** — `README.md`와 `docs/project-overview.md`는 팀 리더가 최종 업데이트
* **출력 경로 통일** — 모든 결과물은 `/outputs/reports/` 하위에 저장

---

## ✅ 1️⃣0️⃣ Summary

> * **main**: 보호 브랜치 (최종본)
> * **dev**: 통합 테스트용
> * **feat/**: 개인별 기능 개발
> * **PR → 리뷰 → dev → main** 순으로 병합
> * **LangGraph 기반 Agent 설계 + F-AI Score 평가**가 핵심

---

📚 **참고 문서**

* [프로젝트 개요 (docs/project-overview.md)](./project-overview.md)
* [발표자료 (output.pdf)](./output.pdf)
