from datetime import date

import pandas as pd
import pytest

from edge_ai.config import load_config
from edge_ai.fetch import _parse_curl, _request_date_str, _validate_response_date


def test_request_date_format():
    d = date(2025, 3, 4)
    assert _request_date_str(d) == "04/03/2025"


def test_validate_response_date_match():
    df = pd.DataFrame({"Date": ["03/04/2025"]})
    assert _validate_response_date(df, date(2025, 3, 4)) is True


def test_validate_response_date_mismatch():
    df = pd.DataFrame({"Date": ["03/05/2025"]})
    assert _validate_response_date(df, date(2025, 3, 4)) is False


def test_parse_curl_basic(tmp_path):
    curl_file = tmp_path / "test.curl"
    curl_file.write_text(
        "curl 'https://www.mcxindia.com/api/bhavcopy' "
        "-H 'Content-Type: application/x-www-form-urlencoded' "
        "-d 'date=04/03/2025&type=D'"
    )
    url, headers, form_data = _parse_curl(curl_file)
    assert url == "https://www.mcxindia.com/api/bhavcopy"
    assert "Content-Type" in headers
    assert "date" in form_data


def test_missing_curl_raises(tmp_path):
    from edge_ai.fetch import FetcherError, fetch_range
    cfg = load_config()
    with pytest.raises(FetcherError, match="cURL file not found"):
        fetch_range(date(2025, 1, 2), date(2025, 1, 3), cfg, curl_path=tmp_path / "missing.curl")


def test_fetch_skips_cached(tmp_path):
    from edge_ai.fetch import fetch_range
    cfg = load_config()
    d = date(2025, 1, 2)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "2025-01-02.parquet").write_bytes(b"PAR1")
    curl_file = tmp_path / "bhavcopy_request.curl"
    curl_file.write_text("curl 'https://example.com/api' -d 'date=02/01/2025'")
    cfg.data.raw_dir = str(raw_dir)
    results = fetch_range(d, d, cfg, curl_path=curl_file)
    assert results["2025-01-02"] == "cached"
