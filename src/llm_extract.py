"""
P2: LLM 노출 추출과 정답 라벨 비교.

- 판정 기준은 labeling_guide.md 원문(2·3·5·6·7절)을 그대로 프롬프트에 넣는다. 사람과 LLM 이 같은 기준을 쓰게 하기 위함.
- LLM 입력은 사람이 읽기 보조로 쓴 것과 같은 '테마별 키워드 적중 문단'이다 (설계 선택, 한계로 기록).
- 정답 라벨이 검증·커밋되기 전에는 실행하지 않는다 (gate_check).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from filings import keyword_hits, verify_quote

LABELS = ["confirmed", "possibly_related", "not_found"]
DIRECTIONS = ["positive", "negative", "mixed", "unknown"]
THEME_NAMES = {"T1": "T1 — AI 인프라 투자 노출",
               "T2a": "T2a — 중국 수요·매출 의존",
               "T2b": "T2b — 대중국 수출규제 노출"}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": LABELS},
        "exposure_direction": {"type": "string", "enum": DIRECTIONS},
        "evidence_text": {"type": "string"},
        "evidence_location": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["label", "exposure_direction", "evidence_text", "evidence_location", "rationale"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# 프롬프트
# ---------------------------------------------------------------------------
def guide_rules(guide_text: str) -> str:
    """기준서에서 판정 규칙 부분(2절~7절)만 원문 그대로 잘라낸다."""
    m = re.search(r"^## 2\..*?(?=^## 8\.)", guide_text, flags=re.S | re.M)
    if not m:
        raise ValueError("labeling_guide.md 에서 2~7절을 찾지 못했습니다.")
    return m.group(0).strip()


SYSTEM_TEMPLATE = """당신은 미국 SEC 10-K 공시에서 특정 사업 노출의 근거를 찾는 분석가다.
아래 '라벨링 기준서'의 규칙만 사용해 판정한다. 기준서에 없는 추론이나 외부 지식은 사용하지 않는다.

출력 규칙:
- label 은 confirmed / possibly_related / not_found 중 하나.
- confirmed 또는 possibly_related 이면 evidence_text 에 제공된 문단의 문장을 한 글자도 바꾸지 말고 그대로 복사한다(1~2문장).
- evidence_location 에는 그 문장이 있는 문단 ID(대괄호 안의 값)를 적는다.
- not_found 이면 evidence_text 와 evidence_location 을 빈 문자열로 둔다.
- exposure_direction 은 공시가 직접 진술한 방향만 기록하고, 진술이 없으면 unknown.
- rationale 에 판정 이유를 한두 문장으로 적는다.

=== 라벨링 기준서 (발췌, 원문) ===
{rules}
"""

USER_TEMPLATE = """발행사: {company}
판정할 테마: {theme_name}

아래는 이 발행사 10-K 의 라벨링 범위(Item 1, 1A, 7, 재무제표 주석)에서 테마 키워드가 들어 있는 문단 전체다.
각 문단 앞의 대괄호 값이 문단 ID 다.

{paragraphs}
"""


def build_prompt(rules: str, company: str, theme: str, hits: pd.DataFrame) -> tuple[str, str]:
    if len(hits):
        paragraphs = "\n\n".join(f"[{h.pid}] {h.text}" for h in hits.itertuples(index=False))
    else:
        paragraphs = "(키워드가 들어 있는 문단이 없음)"
    return (SYSTEM_TEMPLATE.format(rules=rules),
            USER_TEMPLATE.format(company=company, theme_name=THEME_NAMES[theme], paragraphs=paragraphs))


def sha256(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


# ---------------------------------------------------------------------------
# 실행 전 잠금 (정답 라벨 고정 확인)
# ---------------------------------------------------------------------------
def git_label_commit(repo_root: Path, label_path: Path) -> dict:
    rel = str(label_path.relative_to(repo_root)).replace("\\", "/")
    def git(*args):
        return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True)
    commit = git("log", "-1", "--format=%H|%cI", "--", rel)
    dirty = git("status", "--porcelain", "--", rel)
    if commit.returncode != 0:
        return {"committed": False, "clean": False, "commit": None, "error": commit.stderr.strip()}
    h = commit.stdout.strip()
    return {"committed": bool(h), "clean": dirty.stdout.strip() == "",
            "commit": h.split("|")[0] if h else None, "committed_at": h.split("|")[1] if h else None}


def gate_check(labels: pd.DataFrame, validation: pd.DataFrame, git_info: dict | None) -> list[str]:
    """비어 있으면 실행 가능. 문제 목록을 돌려준다."""
    problems = []
    if (labels["label"] == "").any():
        problems.append(f"미작성 라벨 {int((labels['label'] == '').sum())}건")
    if not validation["ok"].all():
        problems.append(f"검증 실패 행 {int((~validation['ok']).sum())}건 (02 노트북 4절)")
    nc = int(labels["label"].isin(["possibly_related", "not_found"]).sum())
    if nc < 4:
        problems.append(f"confirmed가 아닌 라벨 {nc}건 < 4 (추가 쌍 규칙 미완료)")
    if git_info is not None:
        if not git_info.get("committed"):
            problems.append("labels_P2.csv 가 Git 에 커밋되지 않음")
        elif not git_info.get("clean"):
            problems.append("labels_P2.csv 에 커밋 이후 수정 사항이 있음")
    return problems


# ---------------------------------------------------------------------------
# LLM 호출
# ---------------------------------------------------------------------------
def call_llm(client, model: str, system: str, user: str, max_tokens: int = 2000) -> dict:
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    )
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    out = {"stop_reason": resp.stop_reason, "raw_text": text,
           "usage": {"input_tokens": getattr(resp.usage, "input_tokens", None),
                     "output_tokens": getattr(resp.usage, "output_tokens", None)}}
    try:
        out["parsed"] = json.loads(text) if resp.stop_reason == "end_turn" else None
    except json.JSONDecodeError:
        out["parsed"] = None
    return out


def run_extraction(client, model: str, labels: pd.DataFrame, docs: dict[int, pd.DataFrame],
                   rules: str, run_dir: Path, max_tokens: int = 2000) -> pd.DataFrame:
    """정답 라벨과 같은 (발행사, 테마) 쌍마다 1회 호출한다. 호출별 원본 응답을 JSONL 로 남긴다."""
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "calls.jsonl"
    rows = []
    for r in labels.itertuples(index=False):
        cik = int(r.cik)
        hits = keyword_hits(docs[cik], r.theme)
        system, user = build_prompt(rules, r.company, r.theme, hits)
        res = call_llm(client, model, system, user, max_tokens)
        rec = {"rank": int(r.rank), "cik": cik, "company": r.company, "theme": r.theme,
               "model": model, "n_hit_paragraphs": len(hits),
               "prompt_sha256": sha256(system, user),
               "called_at_utc": datetime.now(timezone.utc).isoformat(), **res}
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        p = res.get("parsed") or {}
        rows.append({"rank": int(r.rank), "cik": cik, "company": r.company, "theme": r.theme,
                     "llm_label": p.get("label", "error"),
                     "llm_direction": p.get("exposure_direction", ""),
                     "llm_evidence_text": p.get("evidence_text", ""),
                     "llm_evidence_location": p.get("evidence_location", ""),
                     "llm_rationale": p.get("rationale", ""),
                     "stop_reason": res["stop_reason"]})
    preds = pd.DataFrame(rows)
    preds.to_csv(run_dir / "predictions.csv", index=False, encoding="utf-8-sig")
    return preds


# ---------------------------------------------------------------------------
# 비교 (프로토콜 7.1 P2 기준)
# ---------------------------------------------------------------------------
def evaluate(labels: pd.DataFrame, preds: pd.DataFrame, docs: dict[int, pd.DataFrame]) -> dict:
    m = labels.merge(preds, on=["rank", "cik", "theme"], how="left", suffixes=("", "_p"))
    m["match"] = m["label"] == m["llm_label"]

    def quote_status(r):
        if r.llm_label not in ("confirmed", "possibly_related"):
            return "n/a"
        return verify_quote(r.llm_evidence_text, docs[int(r.cik)], r.llm_evidence_location or None)["status"]

    m["llm_quote_status"] = [quote_status(r) for r in m.itertuples(index=False)]
    quoted = m[m["llm_quote_status"] != "n/a"]
    verbatim = quoted["llm_quote_status"].isin(["ok", "wrong_pid"])
    non_conf = m[m["label"] != "confirmed"]

    metrics = {
        "n_pairs": int(len(m)),
        "quote_verbatim_rate": float(verbatim.mean()) if len(quoted) else 1.0,
        "quote_wrong_pid": int((quoted["llm_quote_status"] == "wrong_pid").sum()),
        "overall_agreement": float(m["match"].mean()),
        "non_confirmed_n": int(len(non_conf)),
        "non_confirmed_agreement": float(non_conf["match"].mean()) if len(non_conf) else float("nan"),
        "llm_errors": int((m["llm_label"] == "error").sum()),
    }
    metrics["p2_pass"] = bool(metrics["quote_verbatim_rate"] == 1.0
                              and metrics["overall_agreement"] >= 0.80
                              and metrics["non_confirmed_n"] >= 4
                              and metrics["non_confirmed_agreement"] >= 0.75)
    confusion = pd.crosstab(m["label"].rename("사람"), m["llm_label"].rename("LLM"), dropna=False)
    by_theme = m.groupby("theme")["match"].agg(["sum", "count"]).rename(columns={"sum": "일치", "count": "건수"})
    return {"metrics": metrics, "confusion": confusion, "by_theme": by_theme, "detail": m}
