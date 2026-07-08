import json
from pathlib import Path

import pytest

from sec_filing_analyzer.config import Settings
from sec_filing_analyzer.models import Company, FilingRef

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        sec_user_agent="sec-filing-analyzer-tests (test@invalid.test)",
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
    )


@pytest.fixture
def company() -> Company:
    return Company(ticker="EXCO", cik=999999, name="ExampleCo Inc.")


@pytest.fixture
def filing_10k_2023(company) -> FilingRef:
    return FilingRef(
        company=company,
        form="10-K",
        accession_number="0000999999-23-000106",
        filing_date="2023-11-03",
        report_date="2023-09-30",
        primary_document="exco-10k_20230930.htm",
    )


@pytest.fixture
def sample_10k_2023() -> str:
    return (FIXTURES / "sample_10k_2023.html").read_text()


@pytest.fixture
def sample_10k_2022() -> str:
    return (FIXTURES / "sample_10k_2022.html").read_text()


@pytest.fixture
def sample_8k() -> str:
    return (FIXTURES / "sample_8k_auditor.html").read_text()


@pytest.fixture
def companyfacts() -> dict:
    return json.loads((FIXTURES / "companyfacts_CIK0000999999.json").read_text())


class StubResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class StubSession:
    """Maps URL substrings to fixture files; records every request."""

    def __init__(self, routes: dict[str, Path]):
        self.routes = routes
        self.requests: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, timeout=None):
        self.requests.append(url)
        for fragment, path in self.routes.items():
            if fragment in url:
                return StubResponse(path.read_bytes())
        return StubResponse(b"not found", status_code=404)


@pytest.fixture
def stub_session() -> StubSession:
    return StubSession(
        {
            "company_tickers.json": FIXTURES / "company_tickers.json",
            "submissions/CIK0000999999.json": FIXTURES / "submissions_CIK0000999999.json",
            "companyfacts/CIK0000999999.json": FIXTURES / "companyfacts_CIK0000999999.json",
            "exco-10k_20230930.htm": FIXTURES / "sample_10k_2023.html",
            "exco-10k_20220924.htm": FIXTURES / "sample_10k_2022.html",
            "exco-8k_20230315.htm": FIXTURES / "sample_8k_auditor.html",
        }
    )
