# Blind Spot Agent 경로 테스트 v1.0 (사전 등록)

- 작성일: 2026-10-13
- 상태: **사전 등록 — Agent 구현 전 고정**
- 버전 기록: Git 커밋 이력 참조 (문서 안에는 커밋 해시를 기입하지 않음)
- 연계 문서: `experiment_protocol.md` v1.0 (P5)

---

## 1. 테스트 환경 원칙

- **결정적 모의 응답:** 공시 조회와 정량 분석 도구는 사전에 고정한 모의 응답(fixture)을 반환한다. 외부 API 오류나 LLM 추출 결과의 변동이 경로 테스트에 영향을 주지 않게 하기 위해서다. 실제 API 통합 테스트는 이 문서와 별도로 수행한다.
- **합성 Registry:** 운영 Registry(프로토콜 6절)에는 정량 프록시가 등록된 테마가 없다. 따라서 Case 2·3·4는 테스트 전용 합성 Registry `T_TEST`를 사용한다.
- **해석 제한:** 이 테스트는 Agent의 판단 경로만 검증한다. 합성 사례의 통과를 실제 테마(T1, T2a, T2b)의 시장 민감도 검증 결과로 해석하지 않는다.

### 1.1 합성 Registry `T_TEST`

| 노출 유형 | 프록시 | 데이터 |
|---|---|---|
| `T_TEST` | `PROXY_TEST` | 모의 시계열 (fixture에 고정) |

---

## 2. 도구 목록

| 도구 | 역할 |
|---|---|
| `get_filing_text` | EDGAR 공시 원문 조회 |
| `extract_exposure` | 인용 기반 노출 추출 → 증거 레코드 생성 |
| `lookup_proxy_registry` | 노출 유형별 등록 프록시 조회 (측정 가능성) |
| `check_estimation_quality` | 관측치, 결측률, VIF 점검 (추정 품질) |
| `estimate_sensitivity` | 계수, 신뢰구간, 하위기간 부호 산출 (민감도 결과) |
| `run_alt_window` | 대체 분석 기간으로 민감도 재추정 |
| `get_segment_revenue` | 10-K 지역·부문 매출 표 추출 + 전체 매출 합계 대조 |
| `search_counter_evidence` | 반대 방향 또는 상쇄 근거 재탐색 |
| `write_report` | 등급, 인용, 가정을 포함한 보고서 생성 |

---

## 3. 판정 규칙

각 사례는 다음 세 조건을 **모두** 충족해야 통과한다.

1. **필수 호출:** 지정된 필수 도구가 지정된 순서대로 호출된다. 사이에 다른 호출이 끼는 것은 허용한다.
2. **금지 호출:** 금지 도구가 한 번도 호출되지 않는다.
3. **최종 상태:** 출력 필드값이 기대값과 일치한다.

먼저 규칙 기반 오케스트레이터로 기대 경로가 재현되는지 확인한다. 그다음 LLM Planner를 같은 입력과 같은 모의 응답으로 실행해 결과를 비교한다.

---

## 4. 테스트 사례

### Case 1 — 사업 노출 확인, 등록된 프록시 없음

- **입력:** 운영 Registry 사용. T1 노출 confirmed, T1 프록시 없음.
- **필수:** `lookup_proxy_registry` → `write_report`
- **금지:** `check_estimation_quality`, `estimate_sensitivity`, `run_alt_window`
- **기대 상태:** `measurability = not_registered`, `sensitivity_result = not_estimated`, `evidence_agreement = undetermined`. 정량 판단을 보류하고 공시 근거만 제시한다.

### Case 2 — 품질 통과, 민감도 유의하지 않음 (실질 불일치)

- **입력:** `T_TEST` 사용. 노출 confirmed(방향: negative). 모의 응답은 품질 pass, 민감도 not_significant.
- **필수:** `lookup_proxy_registry` → `check_estimation_quality` → `estimate_sensitivity` → `get_segment_revenue` → `search_counter_evidence` → `write_report`
- **금지:** 없음
- **기대 상태:** `estimation_quality = pass`, `sensitivity_result = not_significant`, `evidence_agreement = disagree`. 불일치 원인 후보(매출 비중 작음, 상쇄 효과 등)에 증거 기반 순위를 매기며, 원인을 확정하지 않는다.
- **해석:** 여기서 `disagree`는 "사업상 노출을 시장 데이터가 뒷받침하지 못함"을 뜻하며, "반대 방향의 증거가 확인됨"을 뜻하지 않는다(프로토콜 6.1절). 보고서도 이 의미에 맞는 표현을 써야 하며, "시장이 노출을 부정함"과 같은 표현이 나오면 실패로 판정한다.

### Case 3 — 추정 품질 미달 (측정 공백)

- **입력:** `T_TEST` 사용. 노출 confirmed. 모의 응답은 관측치 24개(36개 미만)로 품질 fail.
- **필수:** `lookup_proxy_registry` → `check_estimation_quality` → `write_report`
- **금지:** `estimate_sensitivity`, `get_segment_revenue`, `search_counter_evidence`
- **기대 상태:** `estimation_quality = fail`, `sensitivity_result = not_estimated`, `evidence_agreement = undetermined`. 측정 공백으로 분류하며, 원인 조사를 하지 않는다.

### Case 4 — 품질 통과, 민감도 유의하고 방향 일치 (불필요한 조사 방지)

- **입력:** `T_TEST` 사용. 노출 confirmed(방향: negative). 모의 응답은 품질 pass, 민감도 negative.
- **필수:** `lookup_proxy_registry` → `check_estimation_quality` → `estimate_sensitivity` → `write_report`
- **금지:** `run_alt_window`, `get_segment_revenue`, `search_counter_evidence`
- **기대 상태:** `sensitivity_result = negative`, `evidence_agreement = agree`. 이중 근거 관찰(●)로 분류하며, 재탐색을 생략한다.

### Case 5 — 규제 노출 근거 미발견 (위험 없음으로 오판 방지)

- **입력:** 사건 T2b. 모의 공시 원문에는 관련 문구가 없다.
- **필수:** `get_filing_text` → `extract_exposure` → `write_report`
- **금지:** 없음
- **기대 상태:** `verification_status = not_found`. 보고서에 "근거 미발견"으로 표기한다. "노출 없음" 또는 "위험 없음"이라는 표현이 나오면 실패로 판정한다.

---

## 5. 통과 기준

- 5개 사례 모두 통과 (5/5)
- 실패한 사례는 판단 조건을 수정한 뒤, **기존 사례가 아닌 새 사례**로 재검증한다. 수정 이력은 v1.1로 기록한다.
