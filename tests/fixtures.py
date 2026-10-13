"""
오프라인 검증용 모의 SEC 응답.

실제 KIC 보유내역이 아니다. 회사명과 수치는 처리 규칙을 시험하기 위해 만든 가상값이며,
노트북의 USE_FIXTURES=True 스모크 테스트와 pytest 에서만 쓴다.
"""
from __future__ import annotations

import json
from pathlib import Path

from kic13f import SEC_DATA, SEC_WWW, SecClient, acc_nodash, cik10

FILER = 1441689
NS = "http://www.sec.gov/edgar/document/thirteenf/informationtable"

# (cik, 13F 발행사명, EDGAR 이름, 첫 10-K 접수일 또는 None, 현재 SIC, 2022년 당시 SIC)
COMPANIES = [
    (101, "ALPHA SEMICONDUCTOR CORPORATION", "Alpha Semiconductor Corp", "2010-02-20", "3674", "3674"),
    (102, "BETA DEVICES INC", "Beta Devices Inc.", "2009-11-01", "3571", "3571"),
    (103, "GAMMA SEARCH INC", "Gamma Search Inc.", "2005-03-01", "7370", "7370"),
    (104, "DELTA SOFTWARE CORP", "Delta Software Corp", "2001-09-01", "7372", "7372"),
    (105, "EPSILON RETAIL COM INC", "Epsilon Retail Com Inc", "2002-02-01", "5961", "5961"),
    (106, "ZETA PLATFORMS INC", "Zeta Platforms, Inc.", "2013-02-01", "7370", "7370"),
    (107, "ETA SILICON INC", "Eta Silicon Inc", "2011-12-01", "3674", "3674"),
    (108, "THETA MOTORS INC", "Theta Motors, Inc.", "2011-02-01", "3711", "3711"),
    (109, "IOTA BANCORP", "Iota Bancorp", "2000-03-01", "6021", "6021"),
    (110, "KAPPA PHARMA CO", "Kappa Pharma Co", "2000-03-01", "2834", "2834"),
    (111, "LAMBDA PAYMENTS INC", "Lambda Payments Inc.", "2008-11-01", "7389", "7389"),
    (112, "MU ENERGY CORP", "Mu Energy Corp", "2000-03-01", "2911", "2911"),
    (113, "NU POWER CO", "Nu Power Co", "2000-03-01", "4911", "4911"),
    (114, "XI DATACENTER REIT INC", "Xi Datacenter REIT Inc", "2023-02-15", "6798", None),  # 2022 사건 이후 첫 10-K
    (115, "OMICRON NETWORKS INC", "Omicron Networks Inc", "2003-03-01", "3576", "3576"),
    (201, "ISHARES TR", "iShares Trust", None, "", ""),                    # ETF: 10-K 없음
    (202, "PHI PHARMA PLC", "Phi Pharma PLC", None, "2834", "2834"),      # 20-F 제출 해외 발행사
]

# 2026Q2 정보표 행: (cusip, 13F 발행사명, 클래스, value(달러), putCall)
ROWS_2026 = [
    ("A00000101", "ALPHA SEMICONDUCTOR CORPORATION", "COM", 3_000_000_000, None),
    ("A00000101", "ALPHA SEMICONDUCTOR CORPORATION", "COM", 200_000_000, None),   # 운용주체 분할 행
    ("A00000102", "BETA DEVICES INC", "COM", 2_700_000_000, None),
    ("I00000201", "ISHARES TR", "CORE S&P500 ETF", 2_600_000_000, None),
    ("D00000104", "DELTA SOFTWARE CORP", "COM", 1_900_000_000, None),
    ("E00000105", "EPSILON RETAIL COM INC", "COM", 1_500_000_000, None),
    ("G0000103A", "GAMMA SEARCH INC", "CAP STK CL A", 1_200_000_000, None),
    ("G0000103C", "GAMMA SEARCH INC", "CAP STK CL C", 1_050_000_000, None),        # 같은 CIK 다른 클래스
    ("Z00000106", "ZETA PLATFORMS INC", "CL A", 1_000_000_000, None),
    ("H00000107", "ETA SILICON INC", "COM", 950_000_000, None),
    ("A00000101", "ALPHA SEMICONDUCTOR CORPORATION", "COM", 900_000_000, "Call"),  # 옵션 행
    ("T00000108", "THETA MOTORS INC", "COM", 800_000_000, None),
    ("P00000202", "PHI PHARMA PLC", "SPONSORED ADR", 700_000_000, None),
    ("J00000109", "IOTA BANCORP", "COM", 650_000_000, None),
    ("K00000110", "KAPPA PHARMA CO", "COM", 600_000_000, None),
    ("L00000111", "LAMBDA PAYMENTS INC", "COM CL A", 550_000_000, None),
    ("X00000114", "XI DATACENTER REIT INC", "COM", 500_000_000, None),
    ("M00000112", "MU ENERGY CORP", "COM", 450_000_000, None),
    ("N00000113", "NU POWER CO", "COM", 400_000_000, None),
    ("O00000115", "OMICRON NETWORKS INC", "COM", 350_000_000, None),
    ("Q00000999", "QQQ OBSCURE HOLDINGS LTD", "COM", 10_000_000, None),           # 매핑 실패(소액)
    ("R00000998", "NU POWERS CO", "COM", 5_000_000, None),                         # 표기 차이 → review 후보
]

# 2022Q2 정보표: value 는 천 달러 단위
ROWS_2022 = [
    ("A00000102", "BETA DEVICES INC", "COM", 2_100_000, None),
    ("D00000104", "DELTA SOFTWARE CORP", "COM", 1_800_000, None),
    ("E00000105", "EPSILON RETAIL COM INC", "COM", 1_000_000, None),
    ("G0000103A", "GAMMA SEARCH INC", "CAP STK CL A", 700_000, None),
    ("G0000103C", "GAMMA SEARCH INC", "CAP STK CL C", 650_000, None),
    ("X00000114", "XI DATACENTER REIT INC", "COM", 620_000, None),     # 2022-10-07 이전 10-K 없음 → 제외
    ("A00000101", "ALPHA SEMICONDUCTOR CORPORATION", "COM", 600_000, None),
    ("Z00000106", "ZETA PLATFORMS INC", "CL A", 550_000, None),
    ("T00000108", "THETA MOTORS INC", "COM", 500_000, None),
    ("J00000109", "IOTA BANCORP", "COM", 450_000, None),
    ("K00000110", "KAPPA PHARMA CO", "COM", 400_000, None),
    ("H00000107", "ETA SILICON INC", "COM", 380_000, None),
    ("L00000111", "LAMBDA PAYMENTS INC", "COM CL A", 360_000, None),
    ("M00000112", "MU ENERGY CORP", "COM", 340_000, None),
    ("N00000113", "NU POWER CO", "COM", 320_000, None),
]


def _info_table_xml(rows) -> bytes:
    parts = [f'<?xml version="1.0" encoding="UTF-8"?><informationTable xmlns="{NS}">']
    for cusip, name, cls, value, put_call in rows:
        pc = f"<putCall>{put_call}</putCall>" if put_call else ""
        parts.append(
            f"<infoTable><nameOfIssuer>{name}</nameOfIssuer><titleOfClass>{cls}</titleOfClass>"
            f"<cusip>{cusip}</cusip><value>{value}</value>"
            f"<shrsOrPrnAmt><sshPrnamt>1000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>"
            f"{pc}<investmentDiscretion>SOLE</investmentDiscretion></infoTable>")
    parts.append("</informationTable>")
    return "".join(parts).replace("&", "&amp;").encode()


def _submissions(cik, name, filings, sic="", tickers=()):
    keys = ["accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "primaryDocument"]
    recent = {k: [f.get(k, "") for f in filings] for k in keys}
    return {"cik": str(cik), "name": name, "sic": sic, "tickers": list(tickers),
            "filings": {"recent": recent, "files": []}}


def build_store() -> dict[str, bytes]:
    store: dict[str, bytes] = {}

    def put_json(url, obj):
        store[url] = json.dumps(obj).encode()

    # 제출 기관(KIC) 제출 이력
    f13 = [
        {"accessionNumber": "0001441689-26-000010", "filingDate": "2026-08-12", "reportDate": "2026-06-30",
         "acceptanceDateTime": "2026-08-12T16:05:00.000Z", "form": "13F-HR"},
        {"accessionNumber": "0001441689-22-000020", "filingDate": "2022-08-12", "reportDate": "2022-06-30",
         "acceptanceDateTime": "2022-08-12T15:00:00.000Z", "form": "13F-HR"},
        {"accessionNumber": "0001441689-22-000031", "filingDate": "2022-11-01", "reportDate": "2022-06-30",
         "acceptanceDateTime": "2022-11-01T10:00:00.000Z", "form": "13F-HR/A"},   # 사후 정정 → 사용 금지
    ]
    put_json(f"{SEC_DATA}/submissions/CIK{cik10(FILER)}.json",
             _submissions(FILER, "Korea Investment CORP", f13))
    for acc, rows in (("0001441689-26-000010", ROWS_2026), ("0001441689-22-000020", ROWS_2022)):
        base = f"{SEC_WWW}/Archives/edgar/data/{FILER}/{acc_nodash(acc)}"
        put_json(f"{base}/index.json", {"directory": {"item": [
            {"name": "primary_doc.xml"}, {"name": f"{acc}-index.html"}, {"name": "infotable_kic.xml"}]}})
        store[f"{base}/primary_doc.xml"] = b"<edgarSubmission/>"
        store[f"{base}/infotable_kic.xml"] = _info_table_xml(rows)

    # 발행사 제출 이력과 10-K 헤더
    tickers = {}
    for i, (cik, n13f, edgar, first_10k, sic_now, sic_2022) in enumerate(COMPANIES):
        filings = []
        if first_10k:
            y0 = int(first_10k[:4])
            for y in range(y0, 2027):
                acc = f"{cik:010d}-{str(y)[2:]}-000001"
                fdate = first_10k if y == y0 else f"{y}-02-20"
                filings.append({"accessionNumber": acc, "filingDate": fdate, "form": "10-K",
                                "reportDate": f"{y-1}-12-31", "acceptanceDateTime": f"{fdate}T09:00:00.000Z"})
                if sic_2022:
                    base = f"{SEC_WWW}/Archives/edgar/data/{cik}/{acc_nodash(acc)}"
                    store[f"{base}/{acc}-index-headers.html"] = (
                        f"<html><pre>&lt;SEC-HEADER&gt;\n&lt;ASSIGNED-SIC&gt;{sic_2022}\n</pre></html>").encode()
        else:
            filings.append({"accessionNumber": f"{cik:010d}-22-000009", "filingDate": "2022-04-01",
                            "form": "20-F" if cik == 202 else "N-CEN"})
        put_json(f"{SEC_DATA}/submissions/CIK{cik10(cik)}.json",
                 _submissions(cik, edgar, filings, sic=sic_now, tickers=[f"T{cik}"]))
        tickers[str(i)] = {"cik_str": cik, "ticker": f"T{cik}", "title": edgar}
    put_json(f"{SEC_WWW}/files/company_tickers.json", tickers)
    return store


class FakeClient(SecClient):
    """네트워크 대신 build_store() 의 고정 응답을 돌려주는 결정적 클라이언트."""

    def __init__(self, store: dict[str, bytes] | None = None):
        self.store = store if store is not None else build_store()
        self.log = []

    def get_bytes(self, url: str) -> bytes:
        import requests
        if url not in self.store:
            resp = requests.Response()
            resp.status_code = 404
            raise requests.HTTPError(f"404 (fixture 없음): {url}", response=resp)
        self.log.append({"url": url, "source": "fixture"})
        return self.store[url]


def fixture_dir_note() -> str:
    return str(Path(__file__).resolve())
