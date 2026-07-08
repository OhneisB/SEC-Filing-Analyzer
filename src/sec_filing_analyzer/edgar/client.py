"""Client for the official, free SEC EDGAR APIs.

Endpoints used (no API key required):

- ``https://www.sec.gov/files/company_tickers.json``      ticker -> CIK mapping
- ``https://data.sec.gov/submissions/CIK##########.json`` filing index per company
- ``https://www.sec.gov/Archives/edgar/data/...``         filing documents
- ``https://data.sec.gov/api/xbrl/companyfacts/...``      structured XBRL facts

All requests carry the SEC-mandated User-Agent (with contact e-mail) from
``SEC_USER_AGENT`` and are rate limited (SEC cap: 10 req/s).
Responses are cached on disk under the data directory so repeated runs and
tests do not hammer EDGAR.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import requests

from ..config import Settings
from ..models import Company, FilingRef
from .rate_limiter import RateLimiter

log = logging.getLogger(__name__)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{document}"


class EdgarError(RuntimeError):
    pass


def build_edgar_client(settings: Settings) -> "EdgarClient":
    """Construct an EdgarClient for the configured backend.

    ``backend="edgar"`` (default) talks to SEC EDGAR directly. ``backend="n8n"``
    routes every request through a self-hosted n8n proxy whose URL and token
    come from the environment — useful when outbound access to sec.gov is
    blocked. Either way the same client logic (cache, rate limit, parse) runs.
    """
    if settings.backend == "n8n":
        from .n8n_backend import N8nBackendSession

        session = N8nBackendSession(settings.n8n_webhook_url, settings.n8n_auth_token)
        return EdgarClient(settings, session=session)
    return EdgarClient(settings)


class EdgarClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": settings.sec_user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
        )
        self.rate_limiter = RateLimiter(settings.max_requests_per_second)
        self.cache_dir = settings.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ http

    def _get(self, url: str, cache_key: str | None = None, binary: bool = False) -> bytes:
        if cache_key:
            cached = self.cache_dir / cache_key
            if cached.exists():
                log.debug("cache hit: %s", cache_key)
                return cached.read_bytes()

        self.rate_limiter.acquire()
        log.info("GET %s", url)
        resp = self.session.get(url, timeout=30)
        if resp.status_code == 403:
            raise EdgarError(
                f"EDGAR rejected the request ({url}). Check that SEC_USER_AGENT "
                "contains a valid contact e-mail and that you respect the rate limit."
            )
        resp.raise_for_status()
        data = resp.content

        if cache_key:
            cached = self.cache_dir / cache_key
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(data)
        return data

    def _get_json(self, url: str, cache_key: str | None = None) -> Any:
        return json.loads(self._get(url, cache_key=cache_key))

    # --------------------------------------------------------------- lookups

    def lookup_company(self, ticker: str) -> Company:
        """Resolve a ticker symbol to a Company via the official mapping file."""
        ticker = ticker.upper().strip()
        mapping = self._get_json(TICKERS_URL, cache_key="company_tickers.json")
        for entry in mapping.values():
            if entry.get("ticker", "").upper() == ticker:
                return Company(ticker=ticker, cik=int(entry["cik_str"]), name=entry["title"])
        raise EdgarError(f"Ticker {ticker!r} not found in SEC company_tickers.json")

    def get_submissions(self, company: Company) -> dict[str, Any]:
        return self._get_json(
            SUBMISSIONS_URL.format(cik=company.cik),
            cache_key=f"submissions_CIK{company.cik_padded}.json",
        )

    def list_filings(self, company: Company, form: str, last: int = 1) -> list[FilingRef]:
        """Return the most recent ``last`` filings of ``form`` (newest first)."""
        subs = self.get_submissions(company)
        recent = subs.get("filings", {}).get("recent", {})
        refs: list[FilingRef] = []
        forms = recent.get("form", [])
        for i, f in enumerate(forms):
            if f.upper() != form.upper():
                continue
            refs.append(
                FilingRef(
                    company=company,
                    form=f,
                    accession_number=recent["accessionNumber"][i],
                    filing_date=recent["filingDate"][i],
                    report_date=recent.get("reportDate", [""] * len(forms))[i],
                    primary_document=recent["primaryDocument"][i],
                    primary_doc_description=recent.get(
                        "primaryDocDescription", [""] * len(forms)
                    )[i],
                )
            )
            if len(refs) >= last:
                break
        if not refs:
            raise EdgarError(f"No {form} filings found for {company.ticker} (CIK {company.cik})")
        return refs

    # ------------------------------------------------------------- downloads

    def download_filing_html(self, ref: FilingRef) -> str:
        """Download the primary document of a filing (HTML) and cache it."""
        url = ARCHIVES_URL.format(
            cik=ref.company.cik,
            accession_nodash=ref.accession_nodash,
            document=ref.primary_document,
        )
        cache_key = f"filings/{ref.company.cik}/{ref.accession_nodash}/{Path(ref.primary_document).name}"
        return self._get(url, cache_key=cache_key).decode("utf-8", errors="replace")

    def get_company_facts(self, company: Company) -> dict[str, Any]:
        """Fetch the structured XBRL company facts (all reported concepts)."""
        return self._get_json(
            COMPANYFACTS_URL.format(cik=company.cik),
            cache_key=f"companyfacts_CIK{company.cik_padded}.json",
        )
