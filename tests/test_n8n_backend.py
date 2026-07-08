"""The optional n8n backend must work offline and expose no secrets in code."""

import pytest

from sec_filing_analyzer.config import ConfigError, load_settings
from sec_filing_analyzer.edgar.client import EdgarClient, build_edgar_client
from sec_filing_analyzer.edgar.n8n_backend import N8nBackendSession


class RecordingHttp:
    """Stub that captures the proxied request and returns a canned body."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return self.response


class Resp:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_requires_url_and_token():
    with pytest.raises(ValueError):
        N8nBackendSession("", "token")
    with pytest.raises(ValueError):
        N8nBackendSession("https://n8n/webhook", "")


def test_forwards_target_url_and_bearer_token(fixtures_dir):
    body = (fixtures_dir / "company_tickers.json").read_bytes()
    http = RecordingHttp(Resp(body))
    session = N8nBackendSession("https://n8n.example/webhook/edgar-proxy", "s3cret", http=http)

    resp = session.get("https://www.sec.gov/files/company_tickers.json")

    assert resp.content == body
    call = http.calls[0]
    assert call["url"] == "https://n8n.example/webhook/edgar-proxy"
    assert call["params"] == {"url": "https://www.sec.gov/files/company_tickers.json"}
    assert call["headers"]["Authorization"] == "Bearer s3cret"


def test_edgar_client_works_through_n8n_session(settings, fixtures_dir):
    """The same client logic (lookup + cache) runs over the n8n backend."""
    http = RecordingHttp(Resp((fixtures_dir / "company_tickers.json").read_bytes()))
    session = N8nBackendSession("https://n8n.example/webhook", "tok", http=http)
    client = EdgarClient(settings, session=session)
    client.rate_limiter.min_interval = 0

    company = client.lookup_company("EXCO")
    assert company.cik == 999999


def test_config_rejects_n8n_without_credentials(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "my-analyzer/1.0 (jane.doe@acme.org)")
    monkeypatch.setenv("SEC_BACKEND", "n8n")
    monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("N8N_AUTH_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="N8N_WEBHOOK_URL"):
        load_settings()


def test_build_client_selects_backend(monkeypatch, settings):
    settings.backend = "n8n"
    settings.n8n_webhook_url = "https://n8n.example/webhook"
    settings.n8n_auth_token = "tok"
    client = build_edgar_client(settings)
    assert isinstance(client.session, N8nBackendSession)
