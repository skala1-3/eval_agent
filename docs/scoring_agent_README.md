# 🧮 Agentic RAG v2 — **Scoring 파트 README (Recent)**

## 📘 1. 개요
> **Scoring 단계**는 증거(Evidence)를 **7개 축(axis)** 으로 정량화
> **총점(Total) / 신뢰도(Confidence) / 투자 판단(Decision)** 을 산출

본 README는 **Scoring 로직 및 테스트 실행 방법** 중심으로 구성되어 있습니다.

---

## ⚙️ 2. 핵심 변경사항

### 🧩 (A) `agents/scoring_agent.py` 패치 요약

**회사-증거 매칭 로직 고도화**
- 회사 공식 도메인(`finchat.ai`) → **강한 매칭**
- 텍스트/URL 경로에 회사명(슬러그 포함) → **명시적 매칭**
- **market 축 특례**: `CompanyMeta.tags`(세그먼트 키워드)가 텍스트에 포함되면 **간접 근거로 인정**

**총점 산식**
```python
total = Σ(weight × axis_score) / 100   # (0–10 스케일의 가중 평균)
```

**중복 출처 페널티**
> 동일 도메인 + 동일 강도 반복 시 → 두 번째부터 0.5배 기여

**신뢰도(confidence) 산식**
```python
confidence = 0.4×coverage + 0.3×diversity + 0.3×recency
```

| 요소 | 의미 |
|------|------|
| coverage | 축별 권장 최소 문장수 충족도 |
| diversity | 고유 도메인 다양성 |
| recency | 최근 18개월 이내 비율 |

**의사결정 규칙**
```text
total ≥ 7.5 AND mean(confidence) ≥ 0.55 → "invest"
그 외 → "hold"
```

---

### 🧪 (B) 테스트 체계 정비

- **성공 시에도 점수표 출력** (pytest + `rich` 테이블 사용)
- **테스트 유형**
  1. **Full 7 axes**  
     → 7개 축 모두 strong 위주, 도메인 다양 / 최근 자료 → `invest` (총점 ≈ 8.4)
  2. **Partial 2 axes**  
     → `ai_tech`, `market`만 근거 → `hold` (총점·신뢰도 기준 미달)
- **매칭 보장**: Evidence에 회사명 전체(예: `FinChat AI`) 포함
- **market 특례**: `CompanyMeta.tags=["RIA","Wealth","US"]`

---

## 🗂️ 3. 파일 구조 (Scoring 중심)

```
agents/
  └── scoring_agent.py          # ScoringAgent 로직 (매칭·점수·신뢰도·결정)
graph/
  ├── __init__.py               # 패키지 인식용
  ├── state.py                  # PipelineState / ScoreCard / Evidence 스키마
  ├── graph.py, run.py          # 그래프 조립 및 CLI 실행
tests/
  └── test_scoring_agent_full.py  # 7축 invest + 2축 hold 테스트, rich 테이블 출력
scripts/
  └── test_scoring.py (선택)      # 단독 스모크 테스트
```

---

## 🚀 4. 실행 방법

### 🔹 A) 파이프라인 스모크 실행
```bash
uv sync
python graph/run.py --query "AI financial advisory startup"
# 또는
python -m graph.run --query "AI financial advisory startup"
```

> ※ 다른 에이전트가 더미인 경우, 회사/증거가 비어 있으므로  
> Scoring은 안전 통과(`hold`)만 확인됩니다.

---

### 🔹 B) 단위 테스트 (점수표 출력 포함)
```bash
# 루트에서 실행
PYTHONPATH=. uv run pytest -s -q
```
- `-s`: 출력 캡처 해제 → **성공 시에도 rich 테이블 표시**

특정 테스트만 실행:
```bash
PYTHONPATH=. uv run pytest -s -k full_7_axes_invest
```

---

## 📊 5. 테스트 시나리오 요약

| 시나리오 | 구성 | 기대 결과 |
|-----------|-------|------------|
| **Full 7 axes** | 각 축 strong 근거 2~3개<br>서로 다른 도메인<br>최근 18개월 이내 자료<br>Evidence에 회사명 포함 | 총점 ≈ 8.3~8.6<br>mean(conf) ≥ 0.9<br>→ **invest** |
| **Partial 2 axes** | `ai_tech`, `market` 근거만 존재 | 총점 < 7.5<br>mean(conf) < 0.55<br>→ **hold** |

---

## 🧰 6. 트러블슈팅

| 문제 | 원인/해결 |
|------|-------------|
| `ModuleNotFoundError: graph` | `graph/__init__.py` 생성 + `PYTHONPATH=.` 로 실행 |
| 평균 신뢰도 낮음 | 축별 문장수 부족 → coverage<br>도메인 다양성 부족 → diversity<br>최근 자료 적음 → recency |
| 축 점수 과대/과소 | `STRENGTH_BONUS` (weak=1 / medium=2 / strong=3)<br>`AXIS_WEIGHTS` (예: 25/20/15/10…) 조정 필요 |

---

## ✅ 7. PR 전 체크리스트

- [x] `agents/scoring_agent.py` 패치본 반영 (매칭·총점 산식·페널티·결정 규칙)  
- [x] `graph/__init__.py` 존재 확인  
- [x] `tests/test_scoring_agent_full.py` 통과 (`-s` 옵션으로 표 확인)  
- [x] 문서/로그/비밀키 노출 없음  
- [x] 결정 규칙(`7.5 & 0.55`) 준수  

---

