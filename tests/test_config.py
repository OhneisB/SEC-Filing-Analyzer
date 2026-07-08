import pytest

from sec_filing_analyzer.config import ConfigError, load_settings


def test_missing_user_agent_raises(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(ConfigError, match="SEC_USER_AGENT is not set"):
        load_settings()


def test_placeholder_user_agent_rejected(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "sec-filing-analyzer/0.1 (your.name@example.com)")
    with pytest.raises(ConfigError, match="placeholder"):
        load_settings()


def test_user_agent_without_email_rejected(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "just-a-name")
    with pytest.raises(ConfigError):
        load_settings()


def test_valid_user_agent(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "my-analyzer/1.0 (jane.doe@acme.org)")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = load_settings()
    assert settings.sec_user_agent.startswith("my-analyzer")
    assert settings.ai_enabled is False


def test_rate_limit_clamped_to_sec_cap(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "my-analyzer/1.0 (jane.doe@acme.org)")
    monkeypatch.setenv("SEC_MAX_REQUESTS_PER_SECOND", "50")
    settings = load_settings()
    assert settings.max_requests_per_second <= 10
