"""P2 원문 추출 오프라인 검증 (모의 10-K 사용). 실행: uv run pytest -q"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import filings as f  # noqa: E402
from fixtures import FakeClient  # noqa: E402

ACC = "0000000101-26-000001"


def _doc(cik=101, acc=ACC):
    client = FakeClient()
    url = f.primary_document_url(client, cik, acc)
    return f.assign_items(f.html_to_paragraphs(client.get_bytes(url)))


def test_primary_document_from_submissions():
    url = f.primary_document_url(FakeClient(), 101, ACC)
    assert url.endswith("/000000010126000001/t101-202610k.htm")


def test_hidden_ixbrl_header_removed():
    df = _doc()
    assert not df["text"].str.contains("hidden China AI").any()


def test_toc_skipped_and_items_assigned():
    df = _doc()
    # 목차 행(표 안의 'Item 1A. | Risk Factors | 10')은 항목 시작점으로 쓰이지 않는다
    risk = df[df["text"].str.contains("export license requirements")]
    assert risk["item"].tolist() == ["1A"]
    assert df[df["text"].str.contains("Data center revenue increased")]["item"].tolist() == ["7"]
    assert df[df["text"].str.startswith("Item 1B")]["item"].tolist() == ["1B"]
    summary = f.item_summary(df)
    assert {"1", "1A", "7", "8"} <= set(summary.index)


def test_table_rows_become_paragraphs():
    df = _doc()
    row = df[df["text"].str.contains("China \\(including Hong Kong\\)")]
    assert row["text"].iloc[0] == "China (including Hong Kong) | 12,000"
    assert row["item"].iloc[0] == "8"


def test_keyword_hits_case_rules():
    df = _doc(103, "0000000103-26-000001")
    t1 = f.keyword_hits(df, "T1")
    # 'AI' 는 대문자 단어로만, 'artificial intelligence' 는 대소문자 무관
    assert any("artificial intelligence" in t for t in t1["terms"])
    assert not f.keyword_hits(df, "T2b").shape[0]  # 103 문서에는 수출통제 언급 없음
    assert set(t1["item"]) <= set(f.LABEL_ITEMS)


def test_verify_quote():
    df = _doc()
    pid = df[df["text"].str.contains("Data center revenue")]["pid"].iloc[0]
    q = "Data center revenue increased 80% driven by demand for AI infrastructure."
    assert f.verify_quote(q, df, pid)["status"] == "ok"
    assert f.verify_quote(q, df, "1-p00000")["status"] == "wrong_pid"
    assert f.verify_quote("Data center revenue doubled.", df, pid)["status"] == "not_in_document"
    # 공백·따옴표 차이는 허용
    assert f.verify_quote("Data  center revenue increased 80%", df, pid)["status"] == "ok"


def test_validate_labels():
    df = _doc()
    pid = df[df["text"].str.contains("Data center revenue")]["pid"].iloc[0]
    labels = pd.DataFrame([
        {"rank": 1, "cik": 101, "company": "A", "theme": "T1", "label": "confirmed",
         "exposure_direction": "positive", "evidence_text": "Data center revenue increased 80% driven by demand for AI infrastructure.",
         "evidence_location": pid, "searched": "", "note": "", "added_by_rule": "no"},
        {"rank": 1, "cik": 101, "company": "A", "theme": "T2a", "label": "not_found",
         "exposure_direction": "unknown", "evidence_text": "", "evidence_location": "",
         "searched": "", "note": "", "added_by_rule": "no"},
        {"rank": 1, "cik": 101, "company": "A", "theme": "T2b", "label": "confirmd",
         "exposure_direction": "negative", "evidence_text": "made up text", "evidence_location": "",
         "searched": "", "note": "", "added_by_rule": "no"},
    ])
    res = f.validate_labels(labels, {101: df})
    assert res["ok"].tolist() == [True, False, False]
    assert "searched" in res["problems"].iloc[1]
    assert "허용 안 됨" in res["problems"].iloc[2]
