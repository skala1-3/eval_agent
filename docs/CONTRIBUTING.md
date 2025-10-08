# 🤝 Contributing Guide (v2)

**6인 협업 프로젝트**를 위한 일관된 개발·리뷰·배포 규칙입니다.
브랜치 전략, 커밋 컨벤션(Gitmoji), 코드 스타일, PR 체크리스트를 반드시 준수해주세요.

---

## 🧱 1) Repository Structure (요약)

* `agents/` : 개별 에이전트(탐색/보강/RAG/평가/리포트)
* `graph/`  : 상태/그래프/실행/시각화(통합 지점)
* `data/`   : 원본·정제 데이터
* `outputs/`: 보고서, 로그, 그래프 이미지
* `docs/`   : 설계/평가표/템플릿

> 상세 구조는 `README.md` 참조

---

## 🌿 2) Branch Strategy

| 브랜치         | 용도           | 규칙                                          |
| ----------- | ------------ | ------------------------------------------- |
| `main`      | 릴리스/발표용 (보호) | 직접 push 금지, PR만 병합                          |
| `dev`       | 통합 테스트       | 모든 기능 브랜치의 머지 대상                            |
| `feat/{이름}` | 개인/기능 작업     | 예: `feat/keehoon_graph`, `feat/a_discovery` |

```bash
git switch -c feat/yourname_feature
```

---

## 🧩 3) Commit Convention (Gitmoji)

| 타입                         | 예시                                                 | 의미    |
| -------------------------- | -------------------------------------------------- | ----- |
| `:sparkles: feat:`         | `:sparkles: feat: add ScoringAgent decision rule`  | 기능 추가 |
| `:bug: fix:`               | `:bug: fix: handle empty serp results`             | 버그 수정 |
| `:memo: docs:`             | `:memo: docs: write architecture.md (v2)`          | 문서    |
| `:recycle: refactor:`      | `:recycle: refactor: split chunks by label`        | 리팩터   |
| `:white_check_mark: test:` | `:white_check_mark: test: add chroma search tests` | 테스트   |
| `:construction: chore:`    | `:construction: chore: add logging config`         | 빌드/설정 |

> 메시지 형식: `:emoji: type: subject`
> 본문에 **변경 이유/영향/테스트 결과**를 간단히 명시

---

## ⚙️ 4) Environment & Run

### Python & 패키지

* Python **3.11+** 권장
* 설치: `uv sync`
* 실행: `python graph/run.py --query "..."`
* 시각화: `python graph/visualize.py`

### 환경 변수(.env)

```
OPENAI_API_KEY=
SERAPH_API_KEY=
```

> API Key는 **절대 커밋 금지**. `.gitignore` 확인.

---

## 🧠 5) 코드 스타일 & 구조

* **타입힌트 필수**, Pydantic 모델은 `graph/state.py` 단일 소스 유지
* **로깅**: `logging` + `rich` 로 통일 (레벨/포맷 공용 설정)
* **I/O 경로**: `outputs/` 하위 고정 (보고서/로그/이미지)
* **Chroma**: 동일한 컬렉션명 규약 사용(문서 상단 상수/설정화)
* **LLM 프롬프트**: 각 Agent 내부 `prompts/` 섹션 또는 상수로 분리

---

## 🔁 6) 워크플로우

```bash
# 1) 브랜치 생성
git switch -c feat/yourname_part

# 2) 작업/테스트
uv run pytest -q   # (테스트가 있다면)

# 3) 커밋/푸시
git add .
git commit -m ":sparkles: feat: add RAGRetrieverAgent top-k filtering"
git push origin feat/yourname_part

# 4) PR 생성 (base: dev)
# 5) 리뷰/수정 → 승인
# 6) dev 병합 → (릴리스 시) main 병합
```

---

## 🧾 7) PR 체크리스트

* [ ] 로컬 실행/에러 없음 (`run.py`)
* [ ] 로그/경로 준수 (`outputs/…`)
* [ ] 타입힌트 & Docstring
* [ ] 커밋 컨벤션 준수(Gitmoji)
* [ ] **PDF 생성 조건** 로직 훼손 없음
* [ ] 데이터/비밀키 미노출

---

## 📂 8) Folder Ownership

| 폴더                 | 기본 담당         | 비고                |
| ------------------ | ------------- | ----------------- |
| `agents/seraph_*`  | Discovery 담당  | API 키/쿼리 정책 관리    |
| `agents/augment_*` | Augment 담당    | 크롤러/파서/라벨러        |
| `agents/rag_*`     | Vector/RAG 담당 | 임베딩/검색 파라미터       |
| `agents/scoring_*` | Scoring 담당    | 가중치/decision rule |
| `agents/report_*`  | Report 담당     | 템플릿/렌더링           |
| `graph/*`          | Graph/Infra   | 상태/흐름/진행표시        |

---

## 🔒 9) 데이터/보안

* 외부 문서/링크는 **출처(URL) 저장**
* 민감정보(이메일·전화 등)는 로그/보고서에서 **마스킹**
* 크롤링 정책 준수 (robots.txt/Rate Limit)

---

## ✅ 10) Summary

* 기능 단위 **작게 PR**, **명확한 로그/타입힌트**, **조건부 PDF** 보장
* 공통 설정(상수/경로/포맷)은 문서화하고 재사용
