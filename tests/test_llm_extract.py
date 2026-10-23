"""P2 LLM 추출·비교 오프라인 검증 (가짜 LLM 응답 사용). 실행: uv run pytest -q"""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import filings as f  # noqa: E402
import llm_extract as L  # noqa: E402
from fixtures import FakeClient  # noqa: E402

GUIDE = (ROOT / "labeling_guide.md").read_text(encoding="utf-8")


class FakeLLM:
    """테마별로 정해 둔 JSON 을 돌려주는 가짜 Anthropic 클라이언트."""

    def __init__(self, answers):
        self.answers, self.calls = answers, []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        key = next(k for k in self.answers if k in kw["messages"][0]["content"])
        text = json.dumps(self.answers[key])
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn",
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20))


@pytest.fixture
def doc101():
    c = FakeClient()
    return f.assign_items(f.html_to_paragraphs(c.get_bytes(f.primary_document_url(c, 101, "0000000101-26-000001"))))


def test_guide_rules_extracts_sections_2_to_7():
    rules = L.guide_rules(GUIDE)
    assert rules.startswith("## 2.") and "## 7." in rules and "## 8." not in rules
    assert "## 3." in rules and "confirmed" in rules
    assert "## 1." not in rules  # 대상·범위 절은 프롬프트에 넣지 않는다


def test_build_prompt_includes_pids_and_handles_no_hits(doc101):
    hits = f.keyword_hits(doc101, "T1")
    system, user = L.build_prompt("RULES", "Alpha", "T1", hits)
    assert "RULES" in system and f"[{hits.iloc[0].pid}]" in user
    _, empty = L.build_prompt("RULES", "Alpha", "T2a", hits.iloc[0:0])
    assert "문단이 없음" in empty


def _labels(doc):
    pid = doc[doc["text"].str.contains("Data center revenue")]["pid"].iloc[0]
    return pd.DataFrame([
        {"rank": 1, "cik": 101, "company": "Alpha", "theme": "T1", "label": "confirmed"},
        {"rank": 1, "cik": 101, "company": "Alpha", "theme": "T2a", "label": "not_found"},
        {"rank": 1, "cik": 101, "company": "Alpha", "theme": "T2b", "label": "possibly_related"},
    ]), pid


def test_run_and_evaluate(tmp_path, doc101):
    labels, pid = _labels(doc101)
    answers = {
        "T1 —": {"label": "confirmed", "exposure_direction": "positive",
                 "evidence_text": "Data center revenue increased 80% driven by demand for AI infrastructure.",
                 "evidence_location": pid, "rationale": "r"},
        "T2a —": {"label": "confirmed", "exposure_direction": "unknown",
                  "evidence_text": "China revenue was huge.", "evidence_location": "8-p00001", "rationale": "r"},
        "T2b —": {"label": "possibly_related", "exposure_direction": "negative",
                  "evidence_text": "Our products are subject to U.S. export license requirements",
                  "evidence_location": "1-p00000", "rationale": "r"},
    }
    llm = FakeLLM(answers)
    preds = L.run_extraction(llm, "test-model", labels, {101: doc101}, L.guide_rules(GUIDE), tmp_path)
    assert len(llm.calls) == 3
    assert llm.calls[0]["output_config"]["format"]["type"] == "json_schema"
    assert (tmp_path / "calls.jsonl").read_text(encoding="utf-8").count("\n") == 3

    res = L.evaluate(labels, preds, {101: doc101})
    m = res["metrics"]
    # T2a 인용은 원문에 없음 → 인용 일치율 < 100% → P2 불통과
    assert m["quote_verbatim_rate"] == pytest.approx(2 / 3)
    assert m["quote_wrong_pid"] == 1               # T2b 인용은 원문에 있지만 문단 ID 가 틀림
    assert m["overall_agreement"] == pytest.approx(2 / 3)
    assert m["p2_pass"] is False
    assert res["confusion"].loc["not_found", "confirmed"] == 1


def test_gate_check():
    labels = pd.DataFrame({"label": ["confirmed", "", "not_found"]})
    val = pd.DataFrame({"ok": [True, False, True]})
    probs = L.gate_check(labels, val, {"committed": False})
    assert any("미작성" in p for p in probs) and any("커밋" in p for p in probs) and any("< 4" in p for p in probs)
    ok_labels = pd.DataFrame({"label": ["not_found"] * 4 + ["confirmed"]})
    assert L.gate_check(ok_labels, pd.DataFrame({"ok": [True] * 5}),
                        {"committed": True, "clean": True}) == []
    assert "수정 사항" in L.gate_check(ok_labels, pd.DataFrame({"ok": [True] * 5}),
                                     {"committed": True, "clean": False})[0]


def test_git_label_commit(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
    p = tmp_path / "data" / "labels_P2.csv"
    p.parent.mkdir()
    p.write_text("a\n")
    assert L.git_label_commit(tmp_path, p)["committed"] is False
    git("add", "."); git("commit", "-q", "-m", "labels")
    info = L.git_label_commit(tmp_path, p)
    assert info["committed"] and info["clean"] and len(info["commit"]) == 40
    p.write_text("b\n")
    assert L.git_label_commit(tmp_path, p)["clean"] is False
