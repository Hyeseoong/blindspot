"""
P1 파일럿: KIC 13F 기반 표본(S1, S3) 구성.

experiment_protocol.md v1.0 의 2절(표본 구성 규칙)과 1절(시점 규칙)만 구현한다.
규칙을 바꿀 때는 이 코드가 아니라 프로토콜을 먼저 v1.x 로 개정한다.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from lxml import etree

SEC_WWW = "https://www.sec.gov"
SEC_DATA = "https://data.sec.gov"

# 2023-01-03 이후 접수된 13F 는 value 를 달러 단위로, 그 이전은 천 달러 단위로 보고한다.
VALUE_IN_DOLLARS_FROM = date(2023, 1, 3)

TEN_K_FORMS = {"10-K", "10-K405", "10-KT"}  # 정정 공시(/A)는 적격성 판단에 쓰지 않는다


# ---------------------------------------------------------------------------
# HTTP 클라이언트 (캐시 + 속도 제한)
# ---------------------------------------------------------------------------
class SecClient:
    """SEC EDGAR 접근용 클라이언트. SEC 정책상 연락처가 담긴 User-Agent 가 필요하다."""

    def __init__(self, user_agent: str, cache_dir: Path, min_interval: float = 0.12):
        if "@" not in user_agent or "example.com" in user_agent:
            raise ValueError("USER_AGENT 에 본인 이름과 실제 이메일을 넣어야 합니다 (SEC 접근 정책).")
        if not user_agent.isascii():
            raise ValueError("USER_AGENT 는 ASCII 문자만 사용할 수 있습니다.")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self._last = 0.0
        self.log: list[dict] = []

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / hashlib.sha1(url.encode()).hexdigest()

    def get_bytes(self, url: str) -> bytes:
        path = self._cache_path(url)
        if path.exists():
            self.log.append({"url": url, "source": "cache"})
            return path.read_bytes()
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        resp = self.session.get(url, timeout=30)
        self._last = time.monotonic()
        resp.raise_for_status()
        path.write_bytes(resp.content)
        path.with_suffix(".url").write_text(url)
        self.log.append({"url": url, "source": "network",
                         "fetched_at": datetime.now(timezone.utc).isoformat()})
        return resp.content

    def get_json(self, url: str):
        return json.loads(self.get_bytes(url))

    def get_text(self, url: str) -> str:
        return self.get_bytes(url).decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# 제출 이력
# ---------------------------------------------------------------------------
def cik10(cik: int | str) -> str:
    return str(int(cik)).zfill(10)


def _filings_frame(block: dict) -> pd.DataFrame:
    keys = ["accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "primaryDocument"]
    return pd.DataFrame({k: block.get(k, []) for k in keys})


def load_submissions(client: SecClient, cik) -> tuple[dict, pd.DataFrame]:
    """기업 메타데이터와 전체 제출 이력(최근 + 과거 분할 파일)을 반환한다."""
    meta = client.get_json(f"{SEC_DATA}/submissions/CIK{cik10(cik)}.json")
    frames = [_filings_frame(meta["filings"]["recent"])]
    for f in meta["filings"].get("files", []):
        frames.append(_filings_frame(client.get_json(f"{SEC_DATA}/submissions/{f['name']}")))
    filings = pd.concat(frames, ignore_index=True)
    filings["filingDate"] = pd.to_datetime(filings["filingDate"]).dt.date
    return meta, filings


def find_13f(filings: pd.DataFrame, report_date: str) -> tuple[pd.Series, pd.DataFrame]:
    """기준일의 원본 13F-HR 과, 같은 기준일의 정정 공시 목록을 반환한다 (정정 공시는 사용하지 않음)."""
    same = filings[filings["reportDate"] == report_date]
    originals = same[same["form"] == "13F-HR"].sort_values("filingDate")
    if originals.empty:
        raise LookupError(f"기준일 {report_date} 의 13F-HR 원본을 찾지 못했습니다.")
    amendments = same[same["form"] == "13F-HR/A"]
    return originals.iloc[0], amendments


def acc_nodash(accession: str) -> str:
    return accession.replace("-", "")


def find_info_table(client: SecClient, filer_cik, accession: str) -> tuple[str, bytes]:
    """공시 폴더에서 informationTable XML 을 찾는다 (파일명은 공시마다 다르다)."""
    base = f"{SEC_WWW}/Archives/edgar/data/{int(filer_cik)}/{acc_nodash(accession)}"
    items = client.get_json(f"{base}/index.json")["directory"]["item"]
    for name in [i["name"] for i in items if i["name"].lower().endswith(".xml")]:
        if name.lower() == "primary_doc.xml":
            continue
        url = f"{base}/{name}"
        content = client.get_bytes(url)
        root = etree.fromstring(content)
        if etree.QName(root).localname == "informationTable":
            return url, content
    raise LookupError(f"{accession}: informationTable XML 을 찾지 못했습니다.")


# ---------------------------------------------------------------------------
# 정보표 파싱과 공통 필터
# ---------------------------------------------------------------------------
def _child_text(el, name: str):
    found = el.xpath(f".//*[local-name()='{name}']")
    return found[0].text.strip() if found and found[0].text else None


def parse_info_table(xml_bytes: bytes) -> pd.DataFrame:
    root = etree.fromstring(xml_bytes)
    rows = []
    for t in root.xpath("//*[local-name()='infoTable']"):
        rows.append({
            "nameOfIssuer": _child_text(t, "nameOfIssuer"),
            "titleOfClass": _child_text(t, "titleOfClass"),
            "cusip": (_child_text(t, "cusip") or "").upper(),
            "value_raw": float(_child_text(t, "value") or 0),
            "sshPrnamt": float(_child_text(t, "sshPrnamt") or 0),
            "sshPrnamtType": _child_text(t, "sshPrnamtType"),
            "putCall": _child_text(t, "putCall"),
        })
    return pd.DataFrame(rows)


def value_multiplier(filing_date: date) -> int:
    return 1 if filing_date >= VALUE_IN_DOLLARS_FROM else 1000


def prepare_holdings(raw: pd.DataFrame, multiplier: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """규칙 2.1-1: 풋·콜 행 제외. 이후 같은 CUSIP 의 여러 행(운용 주체별 분할)을 합산한다."""
    df = raw.copy()
    df["value_usd"] = df["value_raw"] * multiplier
    is_option = df["putCall"].notna() & (df["putCall"].astype(str).str.len() > 0)
    excluded = df[is_option].assign(reason="put/call 옵션 행 (규칙 2.1-1)")
    kept = df[~is_option]
    by_cusip = (kept.groupby("cusip", as_index=False)
                .agg(nameOfIssuer=("nameOfIssuer", "first"),
                     titleOfClass=("titleOfClass", "first"),
                     value_usd=("value_usd", "sum"),
                     shares=("sshPrnamt", "sum"),
                     n_rows=("cusip", "size"))
                .sort_values("value_usd", ascending=False, ignore_index=True))
    return by_cusip, excluded


# ---------------------------------------------------------------------------
# CUSIP → CIK 매핑 (규칙 2.1-2)
# ---------------------------------------------------------------------------
_SUFFIX = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED",
           "PLC", "LLC", "LP", "NV", "SA", "AG", "DEL", "NEW", "COM"}


def normalize_name(name: str) -> str:
    s = (name or "").upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\b(CL|CLASS)\s+[A-Z]\b", " ", s)  # 'CL A', 'CLASS B' 같은 클래스 표기만 제거
    tokens = s.split()
    if tokens and tokens[0] == "THE":
        tokens = tokens[1:]
    while len(tokens) > 1 and tokens[-1] in _SUFFIX:
        tokens = tokens[:-1]
    return " ".join(tokens)


def load_ticker_table(client: SecClient) -> pd.DataFrame:
    raw = client.get_json(f"{SEC_WWW}/files/company_tickers.json")
    df = pd.DataFrame(raw.values()).rename(columns={"cik_str": "cik"})
    df["norm"] = df["title"].map(normalize_name)
    return df


def map_cusips(holdings: pd.DataFrame, tickers: pd.DataFrame, manual: pd.DataFrame | None,
               fuzzy_cutoff: float = 0.92) -> pd.DataFrame:
    """
    매핑 상태:
      manual  - 수작업 대응표(cusip_cik_manual.csv)로 확정
      exact   - 정규화한 발행사명이 EDGAR 기업 목록과 정확히 하나의 CIK 로 일치
      review  - 유사 일치 후보만 있음 → 수작업 확인 전까지 미확정(실패로 집계)
      failed  - 후보 없음 또는 동명이인(복수 CIK)
    """
    manual_map = {} if manual is None or manual.empty else dict(
        zip(manual["cusip"].str.upper(), manual["cik"].astype(int)))
    norm_to_ciks = tickers.groupby("norm")["cik"].agg(lambda s: sorted(set(int(c) for c in s)))
    norms = list(norm_to_ciks.index)

    out = []
    for row in holdings.itertuples(index=False):
        rec = {"cusip": row.cusip, "nameOfIssuer": row.nameOfIssuer, "value_usd": row.value_usd,
               "cik": None, "status": "failed", "candidate": None}
        norm = normalize_name(row.nameOfIssuer)
        if row.cusip in manual_map:
            rec.update(cik=manual_map[row.cusip], status="manual")
        elif norm in norm_to_ciks.index and len(norm_to_ciks[norm]) == 1:
            rec.update(cik=norm_to_ciks[norm][0], status="exact")
        else:
            close = difflib.get_close_matches(norm, norms, n=1, cutoff=fuzzy_cutoff)
            if close:
                rec.update(status="review",
                           candidate=f"{close[0]} -> CIK {norm_to_ciks[close[0]]}")
        out.append(rec)
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# 적격성(규칙 2.1-4)과 SIC(1절 업종 분류 규칙)
# ---------------------------------------------------------------------------
def tenk_before(filings: pd.DataFrame, cutoff: date) -> pd.DataFrame:
    """cutoff 일자 '이전'(당일 제외)에 접수된 원본 10-K 목록."""
    mask = filings["form"].isin(TEN_K_FORMS) & (filings["filingDate"] < cutoff)
    return filings[mask].sort_values("filingDate")


_SIC_PATTERNS = [
    re.compile(r"ASSIGNED-SIC(?:>|&gt;|:)\s*(\d{3,4})"),
    re.compile(r"STANDARD INDUSTRIAL CLASSIFICATION:[^\[]*\[(\d{3,4})\]"),
]


def historical_sic(client: SecClient, cik, accession: str) -> str | None:
    """해당 공시 헤더에 기록된 당시의 SIC. 찾지 못하면 None (현재 SIC 로 대체하지 않는다)."""
    base = f"{SEC_WWW}/Archives/edgar/data/{int(cik)}/{acc_nodash(accession)}"
    for url in (f"{base}/{accession}-index-headers.html", f"{base}/{accession}.hdr.sgml"):
        try:
            text = client.get_text(url)
        except requests.HTTPError:
            continue
        for pat in _SIC_PATTERNS:
            m = pat.search(text)
            if m:
                return m.group(1).zfill(4)
    return None


# ---------------------------------------------------------------------------
# 표본 구성
# ---------------------------------------------------------------------------
@dataclass
class SampleSpec:
    name: str              # "S1" / "S3"
    report_date: str       # 13F 기준일, 예: "2026-06-30"
    cutoff: date | None    # 10-K 적격성 판단 기준일. None 이면 13F 접수일을 사용
    use_historical_sic: bool
    size: int = 12


@dataclass
class SampleResult:
    spec: SampleSpec
    sample: pd.DataFrame
    excluded: pd.DataFrame
    mapping: pd.DataFrame
    mapping_failures: pd.DataFrame
    p1: dict
    metadata: dict = field(default_factory=dict)


def build_sample(client: SecClient, filer_cik, spec: SampleSpec, tickers: pd.DataFrame,
                 manual: pd.DataFrame | None = None) -> SampleResult:
    _, filer_filings = load_submissions(client, filer_cik)
    f13, amendments = find_13f(filer_filings, spec.report_date)
    info_url, xml = find_info_table(client, filer_cik, f13["accessionNumber"])
    mult = value_multiplier(f13["filingDate"])
    raw = parse_info_table(xml)
    holdings, excl_options = prepare_holdings(raw, mult)
    cutoff = spec.cutoff or f13["filingDate"]

    mapping = map_cusips(holdings, tickers, manual)
    mapped = mapping[mapping["status"].isin(["manual", "exact"])].copy()
    mapped["cik"] = mapped["cik"].astype(int)

    # 규칙 2.1-3: 같은 CIK 의 여러 클래스 합산 (클래스별 가치는 수익률 가중용으로 보존)
    issuers = (mapped.groupby("cik")
               .apply(lambda g: pd.Series({
                   "issuer_name_13f": g.sort_values("value_usd", ascending=False)["nameOfIssuer"].iloc[0],
                   "cusips": ";".join(g["cusip"]),
                   "class_values_usd": json.dumps(dict(zip(g["cusip"], g["value_usd"]))),
                   "value_usd": g["value_usd"].sum()}), include_groups=False)
               .reset_index()
               .sort_values("value_usd", ascending=False, ignore_index=True))

    selected, excluded = [], [excl_options.assign(cik=None)[["cusip", "nameOfIssuer", "value_usd", "reason"]]]
    for row in issuers.itertuples(index=False):
        if len(selected) == spec.size:
            break
        meta, filings = load_submissions(client, row.cik)
        tenks = tenk_before(filings, cutoff)
        if tenks.empty:
            excluded.append(pd.DataFrame([{
                "cusip": row.cusips, "nameOfIssuer": row.issuer_name_13f, "value_usd": row.value_usd,
                "cik": row.cik, "reason": f"{cutoff} 이전 10-K 없음 (규칙 2.1-4)"}]))
            continue
        last_tenk = tenks.iloc[-1]
        if spec.use_historical_sic:
            sic = historical_sic(client, row.cik, last_tenk["accessionNumber"])
            sic_source = f"ASSIGNED-SIC @ {last_tenk['accessionNumber']}" if sic else "분류 확인 불가"
        else:
            sic = str(meta.get("sic") or "").zfill(4) or None
            sic_source = "submissions API (현재)" if sic else "분류 확인 불가"
        selected.append({
            "cik": row.cik, "edgar_name": meta.get("name"), "issuer_name_13f": row.issuer_name_13f,
            "tickers": ",".join(meta.get("tickers", [])), "cusips": row.cusips,
            "class_values_usd": row.class_values_usd, "value_usd": row.value_usd,
            "sic": sic, "sic_source": sic_source,
            "latest_10k_before_cutoff": last_tenk["accessionNumber"],
            "latest_10k_filing_date": str(last_tenk["filingDate"]),
        })

    sample = pd.DataFrame(selected)
    if not sample.empty:
        sample.insert(0, "rank", range(1, len(sample) + 1))
        sample["weight"] = sample["value_usd"] / sample["value_usd"].sum()
    excluded_df = pd.concat(excluded, ignore_index=True)

    unmapped = mapping[~mapping["status"].isin(["manual", "exact"])]
    boundary = float(sample["value_usd"].min()) if len(sample) == spec.size else float("nan")
    above = unmapped[unmapped["value_usd"] >= boundary] if len(sample) == spec.size else unmapped.iloc[0:0]
    p1 = {
        "sample": spec.name,
        "selected_issuers": int(len(sample)),
        "target": spec.size,
        "boundary_value_usd": boundary,
        "unmapped_at_or_above_boundary": int(len(above)),
        "pass": bool(len(sample) == spec.size and len(above) == 0),
    }
    metadata = {
        "sample": spec.name,
        "filer_cik": int(filer_cik),
        "accession": f13["accessionNumber"],
        "report_date": spec.report_date,
        "filing_date": str(f13["filingDate"]),
        "acceptance_datetime": f13["acceptanceDateTime"],
        "amendments_ignored": amendments["accessionNumber"].tolist(),
        "info_table_url": info_url,
        "value_multiplier": mult,
        "tenk_cutoff_exclusive": str(cutoff),
        "sic_rule": "historical ASSIGNED-SIC" if spec.use_historical_sic else "current SIC",
        "rows_raw": int(len(raw)), "cusips_after_filter": int(len(holdings)),
        "mapping_status_counts": mapping["status"].value_counts().to_dict(),
        "protocol": "experiment_protocol.md v1.0",
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return SampleResult(spec, sample, excluded_df, mapping, unmapped.sort_values("value_usd", ascending=False),
                        p1, metadata)


def save_result(res: SampleResult, out_dir: Path) -> Path:
    d = Path(out_dir) / res.spec.name
    d.mkdir(parents=True, exist_ok=True)
    res.sample.to_csv(d / "sample.csv", index=False)
    res.excluded.to_csv(d / "excluded.csv", index=False)
    res.mapping_failures.to_csv(d / "mapping_failures.csv", index=False)
    res.mapping.to_csv(d / "mapping_all.csv", index=False)
    (d / "metadata.json").write_text(json.dumps({**res.metadata, "p1": res.p1}, ensure_ascii=False, indent=2))
    return d
