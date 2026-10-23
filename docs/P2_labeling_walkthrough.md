# P2 라벨링 따라하기

전체 과정은 세 부분입니다.

| 부분 | 내용 | 방식 | 시간 |
|---|---|---|---|
| A. 준비 | 파일 교체, 노트북 실행 | **복붙만** | 15분 |
| B. 라벨링 | 15건 판정 | 셀 2개를 번갈아 실행 + **사람이 판정** | 2~3시간 |
| C. 마무리 | 검증, 커밋, 기록 | **복붙만** | 15분 |

B는 자동화할 수 없습니다. 사람이 읽고 판정한 결과가 나중에 LLM을 채점하는 정답이 되기 때문입니다. 코드는 후보 문장을 찾아 보여주고, 입력이 맞는지 검사하는 역할만 합니다.

---

# A. 준비 (복붙만)

## A-1. 파일 교체

받은 `blindspot.zip`에서 아래 두 파일을 기존 저장소 위치에 덮어씁니다.

- `notebooks/02_exposure_labeling.ipynb` → `C:\Projects\blindspot\notebooks\`
- `docs/P2_labeling_walkthrough.md` → `C:\Projects\blindspot\docs\` (docs 폴더가 없으면 새로 만듭니다)

`data/` 폴더는 건드리지 않습니다.

## A-2. 설정 셀 고치기

VS Code에서 `notebooks/02_exposure_labeling.ipynb`를 열고, 맨 위 **두 번째 칸(설정 셀)**을 아래 내용으로 통째로 바꿉니다. 이메일만 본인 것으로 고칩니다.

```python
# ── 설정 ─────────────────────────────────────────────
USE_FIXTURES = False
USER_AGENT = "Blind Spot pilot Hyeseong Kim 본인이메일@주소"
TOP_N = 5
LABELER = "Hyeseong Kim"
```

## A-3. 실행

1. 오른쪽 위 커널 이름이 `.venv`인지 확인합니다. 아니면 클릭해서 `.venv`를 고릅니다.
2. 상단 **Restart**를 누릅니다.
3. 상단 **Run All**을 누릅니다.
4. 1~2분 기다립니다.

## A-4. 실행 결과 확인

노트북 화면을 위에서부터 내려가며 아래 표와 비교합니다.

| 위치 | 이렇게 나오면 정상 |
|---|---|
| "항목 구분 점검" 아래 | 5개 회사 모두 `ok`가 `True`, NVIDIA의 `fin_notes_in`이 `Item 15` |
| "라벨링 시트" 아래 | `기존 시트를 유지한다` |
| "라벨 입력 도구" 아래 | 빈 표와 `완료 0/15` |
| **"작업 셀 A"** 아래 | `작업: rank 1 NVIDIA CORP / T2a` 로 시작하는 화면 |
| "4. 라벨 검증" 아래 | 15행 모두 `label 값 '' 허용 안 됨` (아직 비어 있으니 정상) |

다르게 나오면 B로 넘어가지 말고 그 화면을 보내주세요.

## A-5. 커밋

VS Code 하단 터미널에 아래 명령을 한 줄씩 붙여넣습니다.

```bash
cd C:\Projects\blindspot
uv run pytest -q
git add notebooks/02_exposure_labeling.ipynb docs/P2_labeling_walkthrough.md
git commit -m "feat: add guided labeling workflow to P2 notebook"
git push
```

`pytest` 결과에 `failed`가 없어야 합니다.

---

# B. 라벨링 (15번 반복)

## B-1. 사용하는 셀은 두 개뿐입니다

노트북에서 **"라벨링 작업 (15건 반복)"** 제목 아래로 스크롤합니다. 셀이 두 개 있습니다.

| 셀 | 내용 | 역할 |
|---|---|---|
| **작업 셀 A** | `label_next()` | 다음 할 항목을 연다. 기준, 후보 문장, 입력할 줄을 보여준다 |
| **작업 셀 B** | 주석만 있는 빈 셀 | `set_label(...)` 한 줄을 붙여넣고 실행해 저장한다 |

다른 셀은 실행하지 않습니다.

## B-2. 한 건 처리 순서

### ① 작업 셀 A를 실행합니다

셀 A를 클릭하고 `Shift + Enter`를 누릅니다. 아래와 같은 화면이 나옵니다(내용은 예시입니다).

```
====================================================================
작업: rank 1 NVIDIA CORP / T2a      (전체 진행 0/15)
====================================================================
[T2a 중국 수요·매출 의존]
  confirmed        : 중국 매출 금액·비중이 있거나 ...
  possibly_related : ...
  not_found        : ...

후보 문단 23개 (탐색 순서: 지역별 매출 표·주석 → ...)

[0] 15-p01234  (지역별 매출 표·주석)
China (including Hong Kong) | 12,345 | 10,000

[1] 15-p01235  (지역별 매출 표·주석)
...
… 0~7번 표시. 다음 후보: more()

▼ 판정 방법: 인용할 후보가 있으면 pick(번호) 실행 → ...
set_label(1, "T2a", "not_found", searched="자동 탐색 후보 23개 전체 검토 (...)")
```

### ② 맨 위의 판정 기준을 읽습니다

화면 맨 위에 그 테마의 confirmed / possibly_related / not_found 기준이 나옵니다.

### ③ 후보를 읽습니다

후보는 confirmed가 나올 가능성이 높은 곳부터 순서대로 나옵니다.

- 8개보다 많으면 화면 끝에 `다음 후보: more()`가 보입니다.
- 다음 후보를 보려면 셀 A의 `label_next()` 줄 **아래에** `more()`를 한 줄 추가해 실행하거나, 셀 A 바로 밑에 새 셀을 만들어 `more()`를 실행합니다.
- 기준에 맞는 문장을 찾으면 **그 자리에서 읽기를 멈춥니다.** 남은 후보를 끝까지 읽을 필요는 없습니다.

### ④-가. 인용할 문장을 찾았다면: `pick(번호)`

후보 번호가 `[3]`이라면, 셀 A 아래에 `pick(3)`을 입력해 실행합니다(새 셀을 만들어도 됩니다). 그러면 다음 세 가지가 나옵니다.

- 그 문단의 **원문 전체** (줄바꿈 없음)
- 앞뒤 문단 (맥락 확인용)
- 붙여넣을 줄, 예: `set_label(1, "T2a", "confirmed", direction="unknown", quote="", pid="15-p01234", note="")`

맨 아래 `set_label(...)` 줄을 복사해 **작업 셀 B**에 붙여넣고, 다음 세 곳을 고칩니다.

| 고칠 곳 | 넣을 값 |
|---|---|
| `"confirmed"` | 판정 결과: `"confirmed"` 또는 `"possibly_related"` |
| `direction=` | `"positive"` / `"negative"` / `"mixed"` / `"unknown"` (공시가 직접 말한 방향만. 없으면 그대로 `unknown`) |
| `quote=""` | 큰따옴표 사이에 **원문 전체** 출력에서 1~2문장을 복사해 붙여넣기 |

`note=""`는 필요할 때만 채웁니다. 예: 공시된 지역명, 금액 단위, 애매했던 이유.

완성된 모습은 다음과 같습니다(예시).

```python
set_label(1, "T2a", "confirmed", direction="unknown",
          quote="China (including Hong Kong) | 12,345 | 10,000",
          pid="15-p01234", note="지역명 China (including Hong Kong), 단위 백만 달러")
```

### ④-나. 후보를 모두 읽었는데 해당 문장이 없다면: `not_found`

`── 후보 N개를 모두 표시했다.`가 나올 때까지 `more()`로 후보를 **끝까지** 읽은 뒤에만 이 방법을 씁니다.

셀 A 화면 맨 아래에 있는 `set_label(..., "not_found", searched=...)` 줄을 **그대로 복사해** 작업 셀 B에 붙여넣습니다. 고칠 것은 없습니다.

### ⑤ 작업 셀 B를 실행합니다

`Shift + Enter`를 누릅니다.

| 결과 | 할 일 |
|---|---|
| `✓ 저장: rank 1 / T2a → confirmed` | 끝. ①로 돌아가 작업 셀 A를 다시 실행 |
| `✗ 저장하지 않음 — 인용 검증 not_in_document` | quote가 원문과 다름. `pick()`의 **원문 전체**에서 다시 복사 |
| `✗ … wrong_pid (실제 위치 …)` | pid를 괄호 안의 값으로 바꿔 다시 실행 |
| `AssertionError: …` | 메시지대로 고침 (B-4 표 참고) |

### ⑥ 반복합니다

작업 셀 A를 다시 실행하면 다음 항목이 자동으로 열립니다. 순서는 아래처럼 정해져 있습니다.

1. T2a: NVIDIA → Apple → Alphabet → Microsoft → Amazon
2. T2b: 같은 순서
3. T1: 같은 순서

15건을 모두 마치면 셀 A가 `모든 행 라벨 완료`를 출력합니다. 그때 C로 넘어갑니다.

## B-3. 판정할 때 헷갈리는 경우

| 상황 | 라벨 |
|---|---|
| confirmed인지 possibly_related인지 결정이 안 됨 | `possibly_related`, note에 이유 |
| possibly_related인지 not_found인지 결정이 안 됨 | `not_found`, note에 이유 |
| T1: AI가 여러 번 나오지만 회사 매출·제품·투자와 연결된 문장이 없음 | `possibly_related` |
| T2a: 대만만 따로 나옴 | 중국으로 보지 않음 |
| T2a: 중국이 생산·부품 조달로만 나옴 | `not_found`, note "공급망 언급만" |
| T2b: 제품명 없이 "수출통제가 영향을 줄 수 있다"만 있음 | `possibly_related` |

이미 저장한 항목을 다시 보거나 고치려면 셀 A 아래에서 `label_task(순위, "테마")`를 실행합니다. 예: `label_task(2, "T1")`. 그다음 작업 셀 B에서 다시 저장하면 덮어씁니다. 이 수정은 **LLM을 실행하기 전까지만** 허용됩니다.

## B-4. 오류 메시지별 해결

| 메시지 | 해결 |
|---|---|
| `label 은 … 중 하나` | `"confirmed"`, `"possibly_related"`, `"not_found"` 중 하나로 정확히 입력 |
| `direction 은 …` | `"positive"`, `"negative"`, `"mixed"`, `"unknown"` 중 하나 |
| `not_found 는 quote 없이 …` | not_found 줄에 quote를 넣지 않음 (셀 A에 나온 줄을 그대로 사용) |
| `confirmed/possibly_related 는 quote 와 pid 가 필요` | quote를 비워 두었음. 원문을 붙여넣기 |
| `NameError: name 'label_next' is not defined` | 커널이 재시작되었음. **Run All**을 다시 실행 (저장한 라벨은 파일에 있어 사라지지 않음) |
| `PermissionError` | `labels_P2.csv`를 Excel로 열어 두었음. Excel을 닫고 다시 실행 |

---

# C. 마무리 (복붙만)

## C-1. 검증

노트북에서 **"4. 라벨 검증"** 아래 셀을 실행합니다.

- `모든 행 통과`가 나오면 다음으로 넘어갑니다.
- 표가 나오면 `problems` 열에 적힌 행을 `label_task(순위, "테마")`로 다시 열어 고칩니다.

## C-2. 추가 쌍 확인

바로 아래 **"confirmed가 아닌 라벨이 4건 미만일 때"** 셀을 실행합니다.

| 출력 | 할 일 |
|---|---|
| `→ 조건 충족. 추가 쌍 필요 없음.` | C-3으로 |
| `→ 추가: rank 6 … / T1` | 작업 셀 A를 실행하면 추가된 행이 열립니다. B와 같은 방법으로 라벨링 → C-1 → C-2를 `조건 충족`이 나올 때까지 반복 |

## C-3. 라벨 커밋 (LLM 실행 전에)

터미널에 붙여넣습니다.

```bash
git add data/labeling/labels_P2.csv
git commit -m "data: human gold labels for P2 (before LLM extraction)"
git push
git log -1 --format="%h %ci"
```

마지막 줄이 `a1b2c3d 2026-10-23 15:40:00 +0900` 같은 형태로 커밋 해시와 시각을 출력합니다.

## C-4. 실행 기록

노트북 아무 곳에 새 셀을 만들고 아래 코드를 실행합니다. `experiment_log.md`에 붙여넣을 줄을 만들어 줍니다.

```python
L = pd.read_csv(LABEL_PATH, encoding="utf-8-sig", keep_default_na=False)
dist = L["label"].value_counts().to_dict()
added = L[L["added_by_rule"] == "yes"]
added_txt = ", ".join(f"rank {r.rank} {r.theme}" for r in added.itertuples()) or "없음"
print(f"| {datetime.now():%Y-%m-%d %H:%M} | P2 정답 라벨 | labels_P2.csv, 커밋 (해시) | "
      f"{len(L)}행 완료, 분포 confirmed {dist.get('confirmed', 0)} / possibly_related {dist.get('possibly_related', 0)} "
      f"/ not_found {dist.get('not_found', 0)}, 추가 쌍 {added_txt} | 기준서 v1.1 적용, LLM 실행 전 커밋 |")
```

출력된 줄을 `experiment_log.md`의 실행 기록 표 맨 아래에 붙여넣고, `(해시)`를 C-3에서 나온 7자리로 바꿉니다. 그다음 커밋합니다.

```bash
git add experiment_log.md
git commit -m "docs: log P2 gold labeling"
git push
```

## C-5. 알려줄 것

라벨 파일은 보내지 말고, C-4에서 만든 **한 줄만** 보내주세요.

정답 라벨을 보지 않은 상태에서 LLM 추출 프롬프트(03 노트북)를 먼저 만들어 고정해야, 프롬프트가 정답에 맞춰지지 않습니다. 라벨 파일은 그 뒤 비교 단계에서 보내주시면 됩니다.
