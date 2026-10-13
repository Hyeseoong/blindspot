# Blind Spot

업종 분류 뒤에 숨은 공통 사업 노출을 발견하고, 시장 근거를 검증해 투자자의 위험 검토 우선순위를 결정하도록 돕는 AI Agent — 국부펀드 KIC AI 에이전트 공모전 출품 준비 저장소.

## 구성

| 경로 | 내용 |
|---|---|
| `experiment_protocol.md` | 실험 프로토콜 v1.0 (사전 등록) |
| `agent_test_cases.md` | Agent 경로 테스트 v1.0 (사전 등록) |
| `experiment_log.md` | 사전 등록 커밋 해시와 실행 기록 |
| `src/kic13f.py` | P1: KIC 13F 기반 표본(S1, S3) 구성 |
| `notebooks/01_kic_13f_extraction.ipynb` | P1 실행 노트북 |
| `tests/` | 모의 SEC 응답 기반 처리 규칙 검증 |
| `data/manual/cusip_cik_manual.csv` | CUSIP→CIK 수작업 대응표 |

## 실행 (uv)

```bash
uv sync
uv run pytest -q                      # 처리 규칙 오프라인 검증
uv run jupyter lab notebooks/01_kic_13f_extraction.ipynb
```

노트북의 `USER_AGENT`에 본인 영문 이름과 이메일을 넣어야 SEC EDGAR에 접근할 수 있다. `USE_FIXTURES = True`로 두면 네트워크 없이 모의 응답으로 흐름을 점검할 수 있다(실제 데이터 아님).

## 데이터 출처

- SEC EDGAR: Form 13F-HR(제출 기관 CIK 1441689), 발행사 제출 이력, 공시 헤더, `company_tickers.json`
- SEC 원본 응답은 `data/raw/`에 캐시되며 저장소에는 포함하지 않는다. 사용한 접수번호와 URL은 `data/processed/*/metadata.json`에 기록된다.

## 해석상 유의

이 저장소의 표본은 KIC가 SEC에 공시한 13F 보유내역에서 추출해 비중을 재정규화한 샘플이며, KIC 전체 포트폴리오나 그 위험을 대표하지 않는다.
