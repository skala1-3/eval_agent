# 🧭 SeraphAgent Summary

---

## 🚀 1. 주요 목표

| 항목 | 설명 |
|------|------|
| **목적** | AI 금융상담(Advisory) 스타트업 자동 탐색 및 후보 수집 |
| **입력** | `state.query` (`"AI fintech robo-advisory wealth management startup"`) |
| **출력** | `state.companies` + `data/raw/candidates.json` |
| **사용 API** | SerpApi (Google Search Results API) |
| **LangGraph 연동** | `PipelineState` 기반 state 업데이트 구조 (`__call__`) |
| **데이터 스키마** | `CompanyMeta(id, name, website, tags, founded_year, stage, headcount, region)` |

---

## 🧠 2. 주요 기능 정리

| 기능 | 설명 | 상태 |
|------|------|------|
| **SerpApi 연동** | Google 검색 API를 통해 최신 스타트업 탐색 | ✅ |
| **검색 결과 파싱** | title, link, snippet → name, url, summary 매핑 | ✅ |
| **state 업데이트** | `state.companies` 에 CompanyMeta 객체 저장 | ✅ |
| **JSON 저장** | `data/raw/candidates.json` 자동 생성 | ✅ |
| **LangGraph 호환성** | `__call__` 구조로 graph에서 직접 호출 가능 | ✅ |
| **독립 실행 지원** | `python3 agents/seraph_agent.py` 가능 | ✅ |

---

## 📊 3. 실행 결과 예시

**실행 명령**
```bash
python3 agents/seraph_agent.py

출력 로그

--- 🚀 Starting SeraphAgent (SerpApi-Google) ---
🔍 Searching Google (via SerpApi) for: AI fintech robo-advisory wealth management startup
✅ Retrieved 10 candidates from Google search.
💾 Saved candidates to /Users/changhyun/eval_agent/data/raw/candidates.json
✅ 10 candidates saved to data/raw/candidates.json

