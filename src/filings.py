"""
P2 준비: 10-K 원문을 문단 단위로 추출하고, 라벨링 보조용 키워드 적중 목록을 만든다.

판정은 하지 않는다. 판정 기준은 labeling_guide.md v1.0 을 따른다.
"""
from __future__ import annotations

import re
import unicodedata
from copy import deepcopy

import pandas as pd
from lxml import html as lxml_html

from kic13f import SEC_WWW, SecClient, acc_nodash, load_submissions

# 라벨링 범위 (labeling_guide.md 1절)
LABEL_ITEMS = ["1", "1A", "7", "8"]

THEME_PATTERNS = {
    "T1": [r"artificial intelligence", r"\bAI\b", r"generative", r"data ?cent(er|re)s?",
           r"accelerated computing", r"\bGPUs?\b", r"\baccelerators?\b", r"machine learning",
           r"\bLLMs?\b", r"large language model"],
    "T2a": [r"\bChina\b", r"\bChinese\b", r"Greater China", r"Hong Kong", r"\bPRC\b",
            r"People.s Republic of China"],
    "T2b": [r"export control", r"export licen[cs]e", r"licen[cs]e requirement",
            r"Entity List", r"Bureau of Industry and Security", r"\bBIS\b",
            r"Export Administration Regulations", r"\bEAR\b", r"export restriction"],
}
_CASE_SENSITIVE = {r"\bAI\b", r"\bGPUs?\b", r"\bLLMs?\b", r"\bPRC\b", r"\bBIS\b", r"\bEAR\b"}

_BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "table", "section"}
_ITEM_RE = re.compile(
    r"^item\s*(1a|1b|1c|1|2|3|4|5|6|7a|7|8|9a|9b|9c|9|10|11|12|13|14|15|16)\b\s*[\.\:\-—–]?",
    re.IGNORECASE)


# ---------------------------------------------------------------------------
# 문서 조회
# ---------------------------------------------------------------------------
def primary_document_url(client: SecClient, cik, accession: str) -> str:
    """10-K 본문 HTML 의 URL. 제출 이력의 primaryDocument 를 우선 사용한다."""
    _, filings = load_submissions(client, cik)
    row = filings[filings["accessionNumber"] == accession]
    base = f"{SEC_WWW}/Archives/edgar/data/{int(cik)}/{acc_nodash(accession)}"
    if not row.empty and row.iloc[0]["primaryDocument"]:
        return f"{base}/{row.iloc[0]['primaryDocument']}"
    items = client.get_json(f"{base}/index.json")["directory"]["item"]
    htm = [i for i in items if i["name"].lower().endswith((".htm", ".html")) and "index" not in i["name"].lower()]
    if not htm:
        raise LookupError(f"{accession}: 본문 HTML 을 찾지 못했습니다.")
    return f"{base}/{max(htm, key=lambda i: int(i.get('size') or 0))['name']}"


# ---------------------------------------------------------------------------
# HTML → 문단
# ---------------------------------------------------------------------------
def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("​", "")
    return re.sub(r"\s+", " ", text).strip()


def html_to_paragraphs(raw: bytes) -> list[str]:
    """
    본문 HTML 을 문단 목록으로 바꾼다.
    - iXBRL 숨김 헤더(ix:header, display:none)와 script/style 은 제거한다.
    - 표는 행 단위로 한 문단씩, 셀은 ' | ' 로 이어 붙인다 (지역별 매출 표 판독용).
    """
    doc = lxml_html.fromstring(raw)
    for el in list(doc.iter()):
        tag = el.tag if isinstance(el.tag, str) else ""
        style = (el.get("style") or "").replace(" ", "").lower()
        hidden = (tag.lower() in {"script", "style"}
                  or (":" in tag and tag.lower().endswith("header"))
                  or "display:none" in style)
        if hidden and el.getparent() is not None:
            el.drop_tree()  # 뒤따르는 텍스트(tail)는 보존한다

    for table in list(doc.iter("table")):
        container = lxml_html.Element("div")
        for tr in table.iter("tr"):
            cells = [_clean(td.text_content()) for td in tr if td.tag in ("td", "th")]
            cells = [c for c in cells if c and c not in {"$", "%", ")"}]
            if cells:
                p = lxml_html.Element("p")
                p.text = " | ".join(cells)
                container.append(p)
        container.tail = table.tail
        table.getparent().replace(table, container)

    for el in doc.iter():
        if isinstance(el.tag, str) and el.tag.lower() in _BLOCK_TAGS:
            el.tail = "\n\n" + (el.tail or "")
            if el.tag.lower() != "br":
                el.text = "\n\n" + (el.text or "")

    blocks = re.split(r"\n\s*\n", doc.text_content())
    return [b for b in (_clean(x) for x in blocks) if len(b) > 1]


# ---------------------------------------------------------------------------
# 항목(Item) 구분
# ---------------------------------------------------------------------------
def _item_key(paragraph: str) -> str | None:
    if len(paragraph) > 200:
        return None
    m = _ITEM_RE.match(paragraph)
    return m.group(1).upper() if m else None


def assign_items(paragraphs: list[str]) -> pd.DataFrame:
    """
    목차(TOC)에도 'Item 1A' 같은 제목이 나오므로, 같은 항목 제목이 여러 번 나오면
    다음 제목까지의 본문이 가장 긴 위치를 실제 시작점으로 고른다.
    """
    heads = [(i, k) for i, p in enumerate(paragraphs) if (k := _item_key(p))]
    starts: dict[str, int] = {}
    for idx, (i, key) in enumerate(heads):
        nxt = heads[idx + 1][0] if idx + 1 < len(heads) else len(paragraphs)
        span = nxt - i
        if key not in starts or span > starts[key][1]:
            starts[key] = (i, span)
    order = sorted((pos, key) for key, (pos, _) in starts.items())

    item_of = ["0"] * len(paragraphs)  # 0: 표지·목차 등 항목 밖
    for j, (pos, key) in enumerate(order):
        end = order[j + 1][0] if j + 1 < len(order) else len(paragraphs)
        for i in range(pos, end):
            item_of[i] = key

    df = pd.DataFrame({"seq": range(len(paragraphs)), "item": item_of, "text": paragraphs})
    df["pid"] = df["item"] + "-p" + df["seq"].map("{:05d}".format)
    return df[["pid", "item", "seq", "text"]]


def item_summary(df: pd.DataFrame) -> pd.DataFrame:
    s = df.groupby("item").agg(paragraphs=("pid", "size"), chars=("text", lambda t: t.str.len().sum()))
    s = s.reindex(sorted(s.index, key=lambda k: (len(k), k)))
    s["in_label_scope"] = s.index.isin(LABEL_ITEMS)
    return s


# ---------------------------------------------------------------------------
# 키워드 적중 (읽기 보조)
# ---------------------------------------------------------------------------
def _compiled(theme: str):
    return [(p, re.compile(p, 0 if p in _CASE_SENSITIVE else re.IGNORECASE))
            for p in THEME_PATTERNS[theme]]


def keyword_hits(df: pd.DataFrame, theme: str, items=LABEL_ITEMS) -> pd.DataFrame:
    pats = _compiled(theme)
    rows = []
    for r in df[df["item"].isin(items)].itertuples(index=False):
        matched = sorted({p for p, rx in pats if rx.search(r.text)})
        if matched:
            rows.append({"pid": r.pid, "item": r.item, "n_terms": len(matched),
                         "terms": "; ".join(matched), "text": r.text})
    return pd.DataFrame(rows, columns=["pid", "item", "n_terms", "terms", "text"])


# ---------------------------------------------------------------------------
# 인용 검증 (labeling_guide.md 5절, 프로토콜 P2 '인용 원문 일치율 100%')
# ---------------------------------------------------------------------------
def _norm_quote(s: str) -> str:
    s = _clean(s or "")
    return s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')


def verify_quote(quote: str, df: pd.DataFrame, pid: str | None = None) -> dict:
    """인용문이 지정 문단에 그대로 있는지, 없다면 문서 다른 곳에라도 있는지 확인한다."""
    q = _norm_quote(quote)
    if not q:
        return {"status": "empty", "found_in": None}
    if pid and pid in set(df["pid"]):
        if q in _norm_quote(df.loc[df["pid"] == pid, "text"].iloc[0]):
            return {"status": "ok", "found_in": pid}
    for r in df.itertuples(index=False):
        if q in _norm_quote(r.text):
            return {"status": "wrong_pid", "found_in": r.pid}
    return {"status": "not_in_document", "found_in": None}


LABEL_COLUMNS = ["rank", "cik", "company", "theme", "label", "exposure_direction",
                 "evidence_text", "evidence_location", "searched", "note",
                 "added_by_rule", "labeler", "labeled_at"]
ALLOWED = {
    "theme": {"T1", "T2a", "T2b"},
    "label": {"confirmed", "possibly_related", "not_found"},
    "exposure_direction": {"positive", "negative", "mixed", "unknown", ""},
}


def label_template(sample: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    rows = []
    for r in sample.sort_values("rank").head(top_n).itertuples(index=False):
        for theme in ("T1", "T2a", "T2b"):
            rows.append({"rank": r.rank, "cik": r.cik, "company": r.edgar_name, "theme": theme,
                         "added_by_rule": "no"})
    return pd.DataFrame(rows).reindex(columns=LABEL_COLUMNS).fillna("")


def validate_labels(labels: pd.DataFrame, docs: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """라벨 값 범위, 필수 입력, 인용 일치를 한 행씩 점검한다."""
    out = []
    for r in labels.fillna("").itertuples(index=False):
        problems = []
        for col, allowed in ALLOWED.items():
            if str(getattr(r, col)) not in allowed:
                problems.append(f"{col} 값 '{getattr(r, col)}' 허용 안 됨")
        if r.label in ("confirmed", "possibly_related"):
            if not str(r.evidence_text).strip():
                problems.append("인용 없음")
            else:
                v = verify_quote(r.evidence_text, docs[int(r.cik)], str(r.evidence_location) or None)
                if v["status"] != "ok":
                    problems.append(f"인용 검증 {v['status']}" + (f" (실제 위치 {v['found_in']})" if v["found_in"] else ""))
        if r.label == "not_found":
            if str(r.evidence_text).strip():
                problems.append("not_found 인데 인용이 있음")
            if not str(r.searched).strip():
                problems.append("searched(탐색 범위) 미기재")
        out.append({"cik": r.cik, "company": r.company, "theme": r.theme, "label": r.label,
                    "ok": not problems, "problems": "; ".join(problems)})
    return pd.DataFrame(out)
