# P2 라벨링 따라하기 (생략 없는 전체 절차)

- 대상: `notebooks/02_exposure_labeling.ipynb`, `data/labeling/labels_P2.csv`
- 판정 기준: `labeling_guide.md` v1.1 (이 안내서와 충돌하면 기준서가 우선)
- 예상 소요: 준비 20분 + 라벨링 15건 2~3시간 + 마무리 20분

이 안내서에 나오는 문단 ID(`7-p00123` 등)와 문장은 **설명용 예시**입니다. 실제 값은 노트북 화면에서 직접 찾아야 합니다.

---

## 0단계. 새 파일 반영 (10분)

### 0-1. 파일 덮어쓰기

받은 `blindspot.zip`에서 아래 두 파일만 기존 저장소에 복사합니다.

| 받은 파일 | 넣을 위치 |
|---|---|
| `notebooks/02_exposure_labeling.ipynb` | `C:\Projects\blindspot\notebooks\` |
| `docs/P2_labeling_walkthrough.md` | `C:\Projects\blindspot\docs\` (폴더가 없으면 만든다) |

`data/` 폴더와 `labels_P2.csv`는 **덮어쓰지 않습니다.**

### 0-2. 바뀐 점

- 설정 셀에 `LABELER = "Hyeseong Kim"` 줄이 추가되었습니다.
- 라벨 입력 함수 `set_label()`과 진행 현황 함수 `progress()`가 노트북에 들어 있어, 셀을 직접 추가할 필요가 없습니다.
- 원문 검색 함수 `find_text()`와, 줄바꿈 없이 원문을 보여주는 함수 `raw()`가 추가되었습니다.
- 화면에 줄을 나눠 표시할 때 하이픈에서 끊지 않도록 바꿨습니다. 예전에는 `data-center-scale`이 `data-` / `center-scale`로 끊겨, 화면에서 복사한 인용이 원문과 어긋날 수 있었습니다.

### 0-3. USER_AGENT 다시 입력

노트북을 덮어썼으므로 설정 셀의 `USER_AGENT`가 기본값으로 돌아갔습니다. 다시 입력합니다.

```python
USE_FIXTURES = False
USER_AGENT = "Blind Spot pilot Hyeseong Kim (본인 이메일)"
TOP_N = 5
LABELER = "Hyeseong Kim"
```

### 0-4. 커밋

터미널(VS Code 하단 터미널)에서 실행합니다.

```bash
cd C:\Projects\blindspot
uv run pytest -q
git add notebooks/02_exposure_labeling.ipynb docs/P2_labeling_walkthrough.md
git commit -m "feat: add labeling helpers to P2 notebook"
git push
```

`pytest`는 `failed` 없이 모두 `passed`로 끝나야 합니다.

> 커밋 전에 노트북 출력 안에 이메일이 보여도 문제는 없습니다. 다만 공개 저장소라면, 커밋 전에 VS Code 메뉴에서 **Clear All Outputs**를 누르고 저장하는 편이 깔끔합니다.

---

## 1단계. 노트북 실행 (10분)

1. VS Code에서 `notebooks/02_exposure_labeling.ipynb`를 엽니다.
2. 오른쪽 위 커널 이름이 `.venv`인지 봅니다. 아니면 **Select Kernel**에서 `.venv`를 고릅니다.
3. 상단의 **Restart**를 눌러 커널을 재시작합니다.
4. **Run All**을 누릅니다. 처음 실행이면 SEC에서 10-K를 받느라 1~2분 걸리고, 그 뒤로는 캐시에서 바로 읽습니다.

### 실행 후 볼 것

| 셀 | 정상 결과 |
|---|---|
| 1. 10-K 원문 추출 | 5개 회사 모두 `문단 1,000개 이상` |
| 항목 구분 점검 | 5개 회사 모두 `ok = True`, NVIDIA의 `fin_notes_in` = `Item 15` |
| 2. 키워드 적중 | NVIDIA T2a 숫자가 이전의 33보다 큼 (Item 15가 포함됨) |
| 3. 라벨링 시트 | `기존 시트를 유지한다` (이미 만들어 둔 빈 시트) |
| 라벨 입력 도구 | `완료 0/15` 표가 나옴 |
| 4. 라벨 검증 | 아직 비어 있으므로 15행 모두 `label 값 '' 허용 안 됨` (정상) |

### 실행 기록 남기기

`experiment_log.md`의 실행 기록 표에 한 줄을 추가합니다. 괄호 안은 화면에 나온 숫자로 바꿉니다.

```markdown
| 2026-10-23 11:30 | P2 원문 재추출 | 기준서 v1.1 (Item 15 포함) | 항목 점검 5/5 ok, NVDA 주석 위치 Item 15, 적중 T1/T2a/T2b: NVDA (  )/(  )/(  ), AAPL (  )/(  )/(  ), GOOGL (  )/(  )/(  ), MSFT (  )/(  )/(  ), AMZN (  )/(  )/(  ) | 라벨 0/15 |
```

---

## 2단계. 라벨링 전에 알아둘 것 (5분)

### 2-1. 작업할 위치

**"라벨 입력 도구" 셀 바로 아래에 빈 셀을 하나 추가**하고, 모든 탐색과 입력을 그 셀에서 합니다. 한 건을 끝내면 셀 내용을 지우고 다음 건을 씁니다. 노트북의 원래 셀은 고치지 않습니다.

### 2-2. 도구 5개

| 함수 | 용도 | 예시 |
|---|---|---|
| `show_hits(rank, theme, start, n)` | 키워드 적중 문단을 15개씩 보기 | `show_hits(1, "T2b")` |
| `find_text(rank, 패턴, items)` | 원하는 표현으로 직접 검색 | `find_text(1, "Hong Kong", items=["8","15"])` |
| `show_paragraph(rank, pid)` | 특정 문단의 앞뒤 맥락 보기 | `show_paragraph(1, "7-p00123")` |
| `raw(rank, pid)` | 문단 원문을 줄바꿈 없이 출력 (**인용 복사용**) | `raw(1, "7-p00123")` |
| `set_label(...)` | 라벨 저장 (인용 자동 검증) | 아래 참고 |

`rank`는 S1 순위 번호입니다: 1 = NVIDIA, 2 = Apple, 3 = Alphabet, 4 = Microsoft, 5 = Amazon.

### 2-3. 작업 순서: 테마별로 5개 회사를 연달아

회사별(NVIDIA의 T1·T2a·T2b → Apple …)이 아니라 **테마별로 5개 회사를 한 번에** 처리합니다.

1. T2a (중국 매출) — 표에서 찾으므로 가장 빠름
2. T2b (수출규제)
3. T1 (AI 인프라) — 문단이 많고 판정이 가장 까다로움

같은 기준을 5개 회사에 연속으로 적용해야 판정이 회사마다 흔들리지 않습니다.

---

## 3단계. 한 건을 처리하는 표준 절차

모든 15건에 아래 8단계를 똑같이 적용합니다.

| 단계 | 할 일 | 명령 |
|---|---|---|
| ① | 적중 문단을 처음 15개 읽는다 | `show_hits(r, "T2a")` |
| ② | 더 있으면 다음 15개를 읽는다 | `show_hits(r, "T2a", start=15)` → `start=30` … |
| ③ | 4단계의 테마별 검색을 실행한다 | `find_text(...)` |
| ④ | 후보 문단의 앞뒤 맥락을 본다 | `show_paragraph(r, "pid")` |
| ⑤ | `labeling_guide.md` 3절 조건과 대조해 라벨을 정한다 | — |
| ⑥ | 인용할 문단을 원문 그대로 출력한다 | `raw(r, "pid")` |
| ⑦ | ⑥의 출력에서 1~2문장을 복사해 저장한다 | `set_label(...)` |
| ⑧ | `✓ 저장`이 나왔는지 본다. `✗`가 나오면 7단계 문제 해결표로 | — |

**confirmed 조건을 충족하는 문장을 찾으면 그 자리에서 멈춥니다**(기준서 4절 3단계). 남은 적중 문단을 끝까지 읽을 필요는 없습니다.

### 저장 명령 형식

```python
# confirmed / possibly_related : 인용과 문단 ID 필수
set_label(1, "T2a", "confirmed",
          direction="unknown",
          quote="(raw() 출력에서 복사한 원문 1~2문장)",
          pid="15-p01234",
          note="(필요할 때만) 판단 근거 한 줄")

# not_found : 인용 없이, 탐색 범위를 적는다
set_label(3, "T2a", "not_found",
          searched="T2a 적중 문단 전체 + find_text(China|Hong Kong) Item 8 + 지역별 매출 표")
```

### 인용 복사 요령

- `raw()` 출력에서 복사합니다. `show_hits()` 화면은 줄을 나눠 보여주므로 거기서 복사해도 대부분 통과하지만, `raw()`가 가장 안전합니다.
- 문장 **일부만** 복사해도 됩니다. 원문 안에 그대로 들어 있기만 하면 됩니다.
- 단어를 빼거나 `…`로 줄이면 안 됩니다. 앞뒤를 자르는 것만 허용됩니다.
- 표의 행은 `China (including Hong Kong) | 12,000`처럼 ` | `까지 포함해 화면에 보이는 그대로 복사합니다.
- 인용 안에 판정 근거가 함께 들어 있어야 합니다. 예를 들어 T1이라면 "AI"와 "revenue"가 같은 인용 안에 있어야 합니다.

---

## 4단계. 테마별 상세 절차

### 4-1. T2a — 중국 수요·매출 의존 (5건)

**① 지역별 매출 표를 찾습니다.**

```python
find_text(r, "China|Hong Kong|Greater China", items=["8", "15"])
```

NVIDIA는 재무제표 주석이 Item 15에 있고, 나머지 회사는 Item 8에 있습니다.

**② 표가 안 보이면 지역 단위 표현으로 다시 찾습니다.**

```python
find_text(r, "geographic|by region|Americas|Asia Pacific|International", items=["8", "15"])
```

**③ 사업 설명에서 중국 수요 진술을 찾습니다.**

```python
show_hits(r, "T2a")
```

**④ 판정합니다.**

| 상황 | 라벨 | note에 적을 것 |
|---|---|---|
| 중국 또는 중국을 포함한 지역의 매출 금액이나 비중이 있음 | `confirmed` | 공시된 지역명 그대로 (예: "Greater China, 홍콩·대만 포함") |
| 매출이 청구지 기준이라고 명시됨 | `confirmed` | "청구지 기준, 최종 수요지와 다를 수 있음" |
| 중국을 시장이나 고객으로 언급만 하고 금액·비중·의존 진술이 없음 | `possibly_related` | — |
| 중국이 생산·조달 측면으로만 나옴 | `not_found` | "공급망 언급만 있음 (범위 밖)" |
| 중국 관련 언급이 없음 (예: 지역 구분이 "미국 / 기타"뿐) | `not_found` | 지역 구분 방식 (예: "지역 구분: 미국/기타") |

- 대만 단독 매출은 중국으로 합산하지 않습니다.
- 표의 행 하나만 인용하면 금액의 단위가 빠집니다. 그 경우 `note`에 단위를 적습니다(예: "단위 백만 달러, FY2025").

**⑤ 방향:** 표의 숫자만 있으면 `unknown`입니다. "중국 매출이 수요 약세로 감소했다"처럼 공시가 직접 말할 때만 `negative` 또는 `positive`를 씁니다.

### 4-2. T2b — 대중국 수출규제 노출 (5건)

**① 적중 문단을 읽습니다.**

```python
show_hits(r, "T2b")
```

**② 위험요인 항목에서 다시 찾습니다.**

```python
find_text(r, "export", items=["1A"])
```

**③ 사업·경영진 분석 항목에서도 찾습니다.** 일부 회사는 매출 영향을 이곳에 적습니다.

```python
find_text(r, "export control|export licen|license requirement", items=["1", "7"])
```

**④ 판정합니다.**

| 상황 | 라벨 |
|---|---|
| 회사의 **특정 제품·제품군**에 미국 수출 허가 요건이나 제한이 적용되었다고 적혀 있음 | `confirmed` |
| "수출통제가 사업에 영향을 줄 수 있다"는 일반적 위험 문구만 있음 | `possibly_related` |
| 수출통제 언급이 없음 | `not_found` |

- 판단 기준은 **제품이 특정되었는가**입니다. 제품명(예: 특정 GPU 모델)이나 제품군이 문장에 있어야 confirmed입니다.
- 다른 나라의 규제만 언급하고 미국 규제는 언급하지 않으면 `possibly_related`로 두고, `note`에 그 사실을 적습니다.

**⑤ 방향:** "매출이 감소했다/감소할 수 있다"는 `negative`, 영향 방향이 쓰여 있지 않으면 `unknown`입니다.

### 4-3. T1 — AI 인프라 투자 노출 (5건)

T1은 적중 문단이 많으므로(NVIDIA 100개 이상), 모두 읽지 말고 **confirmed가 나올 가능성이 높은 곳부터** 봅니다.

**① 경영진 분석(Item 7)에서 매출·투자 설명을 찾습니다.**

```python
find_text(r, r"\bAI\b|artificial intelligence|data center", items=["7"])
```

**② 설비투자 진술을 찾습니다.**

```python
find_text(r, "capital expenditure|property and equipment", items=["7"])
```

**③ 그래도 없으면 사업 설명(Item 1)을 봅니다.**

```python
find_text(r, r"\bAI\b|artificial intelligence|data center", items=["1"])
```

**④ 마지막으로 적중 목록을 처음부터 읽습니다.**

```python
show_hits(r, "T1")
show_hits(r, "T1", start=15)
```

**⑤ 판정합니다.** confirmed가 되려면 아래 다섯 요소 중 하나가 **이 회사 자신의** AI·데이터센터 사항과 한 문장(또는 바로 이어지는 문장) 안에서 연결되어야 합니다.

| 요소 | 연결 예 (설명용) |
|---|---|
| 제품 | 회사의 제품이 AI 학습·추론에 쓰인다 |
| 매출 | 매출 증가 원인으로 AI 수요가 적혀 있다 |
| 비용 | AI 인프라 관련 비용(감가상각 등)이 늘었다 |
| 투자 | AI 수요 대응을 위해 데이터센터 투자를 늘렸다 |
| 수요 | AI 서비스 수요가 사업 성장을 이끌었다 |

**possibly_related로 두는 경우:**

- AI를 산업 추세, 시장 전망, 경쟁 환경으로만 언급함
- AI를 규제·평판·윤리 위험으로만 언급함
- 미래 계획이나 포부만 있음
- 데이터센터를 언급하지만 AI와 연결하지 않음

"AI"라는 단어가 많이 나온다고 confirmed가 되지는 않습니다. 이 회사의 제품·매출·비용·투자·수요와 연결되었는지만 봅니다.

**⑥ 방향:** 매출 증가·수요 증가는 `positive`, 비용 증가만 적혀 있으면 `negative`, 둘 다 있으면 `mixed`, 방향 진술이 없으면 `unknown`입니다.

---

## 5단계. 방향(`direction`)과 애매한 경우

### 방향 규칙 (기준서 6절)

- 공시가 **직접 말한** 방향만 적습니다. "이 사업이면 AI 덕을 볼 것이다" 같은 추론은 하지 않습니다.
- 인용한 문장 안에 방향이 없으면 `unknown`입니다.

### 판정이 애매할 때 (기준서 7절)

- confirmed와 possibly_related 사이에서 결정하지 못하면 `possibly_related`를 고릅니다.
- possibly_related와 not_found 사이에서 결정하지 못하면 `not_found`를 고릅니다.
- 그 이유를 `note`에 한 줄로 적습니다. 예: `note="AI 매출 언급이 있으나 회사 전체 매출 추세 문장이라 연결이 약함"`

---

## 6단계. 진행 점검과 마무리

### 6-1. 진행 현황 보기

중간중간 아래 명령으로 진행 현황을 봅니다.

```python
progress()
```

15칸이 모두 채워지면 다음으로 넘어갑니다.

### 6-2. 검증 셀 실행

"4. 라벨 검증" 셀을 실행합니다. `모든 행 통과`가 나와야 합니다. 문제가 있는 행이 나오면 `problems` 열을 보고, 해당 행을 `set_label()`로 다시 입력합니다.

### 6-3. 추가 쌍 셀 실행

"confirmed가 아닌 라벨이 4건 미만일 때" 셀을 실행합니다. 결과에 따라 다음과 같이 합니다.

| 출력 | 할 일 |
|---|---|
| `→ 조건 충족. 추가 쌍 필요 없음.` | 7단계로 |
| `→ 추가: rank 6 Broadcom … / T1` | 그 행을 3~4단계 절차로 라벨링 → 검증 셀 → 추가 쌍 셀을 다시 실행. 조건을 충족할 때까지 반복 |

추가로 들어온 행은 `rank`가 6, 7…이며, `show_hits(6, "T1")`처럼 같은 방법으로 작업합니다.

---

## 7단계. 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `✗ 저장하지 않음 — 인용 검증 not_in_document` | 인용이 원문과 다름 (단어를 빼거나 고쳤음, 화면 줄바꿈에서 복사) | `raw(r, pid)` 출력에서 다시 복사 |
| `✗ … wrong_pid (실제 위치 7-p00456)` | 문단 ID를 잘못 적음 | 괄호 안의 ID로 `pid`를 바꿔 다시 실행 |
| `AssertionError: … 행이 시트에 없다` | rank나 theme 오타 (예: `"t2a"`) | 대소문자 그대로 `"T1"`, `"T2a"`, `"T2b"` |
| `AssertionError: label 은 …` | 라벨 오타 | `confirmed` / `possibly_related` / `not_found` |
| `AssertionError: not_found 는 …` | not_found인데 quote를 넣었거나 searched를 비움 | quote를 빼고 searched를 적음 |
| `NameError: docs` 또는 `set_label` | 커널 재시작 후 셀을 실행하지 않음 | **Run All** 다시 실행 (라벨은 파일에 저장되어 있어 사라지지 않음) |
| `PermissionError` | `labels_P2.csv`를 Excel로 열어 둠 | Excel을 닫고 다시 실행 |
| `IndexError` (show_paragraph, raw) | 없는 문단 ID | `find_text`나 `show_hits` 출력의 ID를 다시 복사 |

---

## 8단계. 커밋과 기록 (10분)

### 8-1. 최종 점검

```python
progress()      # 완료 15/15 이상
```

검증 셀이 `모든 행 통과`이고, 추가 쌍 셀이 `조건 충족`인지 봅니다.

### 8-2. 커밋

**LLM 추출을 하기 전에** 커밋해야 합니다.

```bash
git add data/labeling/labels_P2.csv
git commit -m "data: human gold labels for P2 (before LLM extraction)"
git push
git log -1 --format="%H %ci"
```

마지막 명령이 커밋 해시와 시각을 출력합니다.

### 8-3. 실행 기록

`experiment_log.md`에 한 줄을 추가합니다. 괄호 안을 채웁니다.

```markdown
| 2026-10-( ) ( : ) | P2 정답 라벨 | labels_P2.csv, 커밋 ( 해시 앞 7자리 ) | ( )행 완료, 분포 confirmed ( ) / possibly_related ( ) / not_found ( ), 추가 쌍 ( 없음 또는 rank 6 T1 등 ) | 기준서 v1.1 적용, LLM 실행 전 커밋 |
```

판정이 애매해 낮은 라벨을 고른 행이 있었다면, 아래에 한 줄씩 적어 둡니다.

```markdown
- 애매 판정: rank ( ) / ( ) → ( ), 사유: ( )
```

```bash
git add experiment_log.md
git commit -m "docs: log P2 gold labeling"
git push
```

---

## 9단계. 끝나면 보낼 것

라벨 시트 파일 자체는 **보내지 않습니다.** 대신 아래 세 가지만 알려주세요.

1. 커밋 해시 (앞 7자리)
2. 라벨 분포 (confirmed / possibly_related / not_found 건수)
3. 추가 쌍 여부

**이유:** 다음 단계인 03 노트북에서 LLM 추출 프롬프트를 만듭니다. 그 프롬프트를 만드는 쪽(Claude)이 정답 라벨을 먼저 보면, 정답에 맞춰 프롬프트를 조정하게 될 위험이 있습니다. 그래서 프롬프트를 먼저 고정해 커밋하고, 그 뒤에 LLM 결과와 정답 라벨을 비교합니다. 비교 단계에서는 라벨 파일을 보내도 됩니다.
