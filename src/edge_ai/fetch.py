"""fetch.py: MCX Bhavcopy fetcher.

Parses the captured cURL from docs/bhavcopy_request.curl, substitutes the
request date (DD/MM/YYYY), validates the response Date (MM/DD/YYYY), caches
raw parquet files, writes skip markers, and throttles between calls.

HARD RULE: never guess the MCX endpoint. Requires docs/bhavcopy_request.curl.
"""
from __future__ import annotations

import io
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from edge_ai.config import Config

_DATE_REQ_FMT = "%d/%m/%Y"   # format used in the request body
_DATE_RESP_FMT = "%m/%d/%Y"  # format in the MCX response Date column


class FetcherError(RuntimeError):
    """Raised when the fetcher cannot proceed."""


def _parse_curl(curl_path: Path) -> tuple[str, dict[str, str], dict[str, str]]:
    """Parse a cURL command file into (url, headers, form_data).

    Supports: -H 'Key: Value', -d 'key=val&...' or --data-urlencode.
    Lines starting with # are ignored.
    """
    text = curl_path.read_text(encoding="utf-8")
    # Strip comment lines
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    text = " ".join(lines)

    # Extract URL
    url_m = re.search(r"curl\s+['\"]?(https?://[^\s'\"]+)['\"]?", text)
    if not url_m:
        raise FetcherError(
            f"Cannot parse URL from {curl_path}. "
            "Make sure the file contains a valid cURL command."
        )
    url = url_m.group(1)

    # Extract headers
    headers: dict[str, str] = {}
    for m in re.finditer(r"-H\s+['\"]([^'\"]+)['\"]", text):
        hdr = m.group(1)
        if ":" in hdr:
            k, _, v = hdr.partition(":")
            headers[k.strip()] = v.strip()

    # Extract form data
    form_data: dict[str, str] = {}
    data_m = re.search(r"(?:--data|-d)\s+['\"]([^'\"]+)['\"]", text)
    if data_m:
        for pair in data_m.group(1).split("&"):
            if "=" in pair:
                k, _, v = pair.partition("=")
                form_data[k.strip()] = v.strip()

    return url, headers, form_data


def _request_date_str(d: date) -> str:
    """Format a date as DD/MM/YYYY for the MCX request."""
    return d.strftime(_DATE_REQ_FMT)


def _validate_response_date(df: pd.DataFrame, requested: date) -> bool:
    """Return True if the response Date matches the requested date."""
    if df.empty or "Date" not in df.columns:
        return False
    resp_date_str = df["Date"].iloc[0]
    try:
        resp_date = pd.to_datetime(resp_date_str, format=_DATE_RESP_FMT).date()
    except Exception:
        return False
    return resp_date == requested


def _date_range(start: date, end: date) -> list[date]:
    """Return business days from start to end (inclusive), newest first."""
    days = []
    current = end
    while current >= start:
        if current.weekday() < 5:  # Mon-Fri
            days.append(current)
        current -= timedelta(days=1)
    return days


def fetch_range(
    start: date,
    end: date,
    cfg: Config,
    curl_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, str]:
    """Fetch Bhavcopy for each business day in [start, end].

    Returns a dict of {YYYY-MM-DD: status} where status is one of:
    'cached', 'fetched', 'skipped', 'mismatch', 'error'.
    """
    if curl_path is None:
        curl_path = Path("docs/bhavcopy_request.curl")

    if not curl_path.exists():
        raise FetcherError(
            f"cURL file not found: {curl_path}\n"
            "Please capture the MCX Bhavcopy network request in DevTools "
            "and paste it into docs/bhavcopy_request.curl."
        )

    url, headers, form_template = _parse_curl(curl_path)
    raw_dir = Path(cfg.data.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, str] = {}
    days = _date_range(start, end)

    for day in days:
        day_str = day.isoformat()
        parquet_path = raw_dir / f"{day_str}.parquet"
        skip_path = raw_dir / f"{day_str}.skip"

        # Already cached
        if parquet_path.exists():
            results[day_str] = "cached"
            continue
        if skip_path.exists():
            results[day_str] = "skipped"
            continue

        if dry_run:
            results[day_str] = "dry_run"
            continue

        # Build request
        form_data = dict(form_template)
        # Substitute the date placeholder — replace any existing date-like value
        # or add a 'date' key
        req_date = _request_date_str(day)
        for k in list(form_data.keys()):
            # Replace any key that looks like a date field
            if "date" in k.lower() or re.match(r"\d{2}/\d{2}/\d{4}", form_data[k]):
                form_data[k] = req_date
        if not form_data:
            form_data["date"] = req_date

        try:
            resp = requests.post(url, headers=headers, data=form_data, timeout=30)
            resp.raise_for_status()
            # Parse response — try JSON first, then CSV
            try:
                payload: Any = resp.json()
                if isinstance(payload, list):
                    df = pd.DataFrame(payload)
                elif isinstance(payload, dict) and "data" in payload:
                    df = pd.DataFrame(payload["data"])
                else:
                    df = pd.DataFrame([payload])
            except Exception:
                try:
                    df = pd.read_csv(io.StringIO(resp.text))
                except Exception:
                    skip_path.write_text("parse_error")
                    results[day_str] = "error"
                    time.sleep(cfg.data.throttle_seconds)
                    continue

            if not _validate_response_date(df, day):
                skip_path.write_text("date_mismatch")
                results[day_str] = "mismatch"
            else:
                df.to_parquet(parquet_path, index=False)
                results[day_str] = "fetched"

        except requests.RequestException as exc:
            skip_path.write_text(f"network_error: {exc}")
            results[day_str] = "error"

        time.sleep(cfg.data.throttle_seconds)

    return results
