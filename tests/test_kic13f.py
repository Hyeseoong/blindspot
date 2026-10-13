"""P1 처리 규칙 오프라인 검증 (모의 응답 사용). 실행: uv run pytest -q"""
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import kic13f as k  # noqa: E402
from fixtures import FILER, FakeClient  # noqa: E402

S1 = k.SampleSpec("S1", "2026-06-30", cutoff=None, use_historical_sic=False)
S3 = k.SampleSpec("S3", "2022-06-30", cutoff=date(2022, 10, 7), use_historical_sic=True)
MANUAL = pd.DataFrame({"cusip": ["I00000201"], "cik": [201]})


@pytest.fixture
def client():
    return FakeClient()


@pytest.fixture
def tickers(client):
    return k.load_ticker_table(client)


def test_normalize_name():
    assert k.normalize_name("Zeta Platforms, Inc.") == k.normalize_name("ZETA PLATFORMS INC")
    assert k.normalize_name("EPSILON RETAIL COM INC") == "EPSILON RETAIL"
    assert k.normalize_name("The AB&C Co") == "AB AND C"


def test_value_multiplier_boundary():
    assert k.value_multiplier(date(2023, 1, 2)) == 1000
    assert k.value_multiplier(date(2023, 1, 3)) == 1


def test_options_excluded_and_split_rows_summed(client):
    raw = k.parse_info_table(k.find_info_table(client, FILER, "0001441689-26-000010")[1])
    holdings, excluded = k.prepare_holdings(raw, 1)
    assert len(excluded) == 1 and excluded["putCall"].iloc[0] == "Call"
    alpha = holdings.set_index("cusip").loc["A00000101"]
    assert alpha["value_usd"] == 3_200_000_000 and alpha["n_rows"] == 2


def test_s1_without_manual_mapping_fails_p1(client, tickers):
    res = k.build_sample(client, FILER, S1, tickers, manual=None)
    # ETF 'ISHARES TR' 는 이름 대조로 연결되지 않고, 보유가치가 경계 이상이므로 P1 실패여야 한다
    assert res.p1["pass"] is False
    assert "I00000201" in res.mapping_failures["cusip"].tolist()


def test_s1_with_manual_mapping(client, tickers):
    res = k.build_sample(client, FILER, S1, tickers, manual=MANUAL)
    s = res.sample
    assert res.p1["pass"] is True and len(s) == 12
    assert abs(s["weight"].sum() - 1) < 1e-12
    # 같은 CIK 의 두 클래스 합산
    gamma = s.set_index("cik").loc[103]
    assert gamma["value_usd"] == 2_250_000_000
    assert set(json.loads(gamma["class_values_usd"])) == {"G0000103A", "G0000103C"}
    # 10-K 미제출(ETF, 20-F) 제외 및 사유 기록
    reasons = res.excluded.set_index("cik")["reason"].dropna()
    assert 201 in reasons.index and 202 in reasons.index
    assert 201 not in s["cik"].tolist() and 202 not in s["cik"].tolist()
    # S1 시점에는 2023년 첫 10-K 를 낸 발행사도 적격
    assert 114 in s["cik"].tolist()
    # 표기 차이는 자동 확정하지 않고 review 로 남긴다
    assert res.mapping.set_index("cusip").loc["R00000998", "status"] == "review"
    assert s["sic_source"].str.contains("현재").all()


def test_s3_point_in_time_rules(client, tickers):
    res = k.build_sample(client, FILER, S3, tickers, manual=MANUAL)
    s = res.sample
    assert res.p1["pass"] is True and len(s) == 12
    assert res.metadata["value_multiplier"] == 1000
    assert res.metadata["amendments_ignored"] == ["0001441689-22-000031"]
    # 사건 이전 10-K 가 없는 발행사(2023년 첫 10-K)는 제외
    assert 114 not in s["cik"].tolist()
    assert "2022-10-07 이전 10-K 없음" in res.excluded.set_index("cik").loc[114, "reason"]
    # 당시 SIC 는 공시 헤더에서, 10-K 는 사건일 이전 것만
    assert s["sic_source"].str.startswith("ASSIGNED-SIC").all()
    assert (pd.to_datetime(s["latest_10k_filing_date"]) < "2022-10-07").all()
    assert s.set_index("cik").loc[103, "value_usd"] == 1_350_000_000


def test_historical_sic_missing_is_not_replaced(client):
    assert k.historical_sic(client, 999, "0000000999-22-000001") is None


def test_client_rejects_placeholder_user_agent(tmp_path):
    with pytest.raises(ValueError):
        k.SecClient("Blind Spot your_email@example.com", tmp_path)
    with pytest.raises(ValueError):
        k.SecClient("홍길동 me@uni.ac.kr", tmp_path)


class _ErrorClient(FakeClient):
    """특정 상태 코드로 실패하는 클라이언트 (API 장애 모사)."""

    def __init__(self, status):
        super().__init__()
        self.status = status

    def get_bytes(self, url):
        import requests
        resp = requests.Response()
        resp.status_code = self.status
        raise requests.HTTPError(f"{self.status}", response=resp)


def test_historical_sic_api_failure_is_not_hidden():
    import requests
    # 404 는 데이터 부재 → None
    assert k.historical_sic(_ErrorClient(404), 101, "0000000101-22-000001") is None
    # 429·403 은 '분류 확인 불가'로 숨기지 않고 예외로 올라와야 한다
    for status in (429, 403):
        with pytest.raises(requests.HTTPError):
            k.historical_sic(_ErrorClient(status), 101, "0000000101-22-000001")


def test_client_retries_transient_status(tmp_path, monkeypatch):
    import requests
    monkeypatch.setattr(k.time, "sleep", lambda s: None)
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        r = requests.Response()
        r.status_code = 429 if len(calls) < 3 else 200
        r._content = b'{"ok": true}'
        return r

    c = k.SecClient("Test User test@uni.ac.kr", tmp_path)
    monkeypatch.setattr(c.session, "get", fake_get)
    assert c.get_json("https://data.sec.gov/x.json") == {"ok": True}
    assert len(calls) == 3
    assert [e.get("status") for e in c.log if e["source"] == "error"] == [429, 429]


def test_client_gives_up_after_max_retries(tmp_path, monkeypatch):
    import requests
    monkeypatch.setattr(k.time, "sleep", lambda s: None)

    def always_503(url, timeout):
        r = requests.Response()
        r.status_code = 503
        return r

    c = k.SecClient("Test User test@uni.ac.kr", tmp_path, max_retries=2)
    monkeypatch.setattr(c.session, "get", always_503)
    with pytest.raises(requests.HTTPError):
        c.get_bytes("https://data.sec.gov/y.json")
    assert not any(tmp_path.iterdir())  # 실패 응답은 캐시에 남기지 않는다


def test_parse_edgar_dates_fixed_format():
    s = pd.Series(["2026-09-23", "2004-03-01", "", None])
    out = k.parse_edgar_dates(s)
    assert out.iloc[0] == date(2026, 9, 23) and out.iloc[1] == date(2004, 3, 1)
    assert out.iloc[2] is None and out.iloc[3] is None
    with pytest.raises(ValueError):
        k.parse_edgar_dates(pd.Series(["2026-Sep-23"]))
