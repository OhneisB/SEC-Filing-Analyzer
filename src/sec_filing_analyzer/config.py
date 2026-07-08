"""Runtime configuration loaded from environment variables / .env.

The SEC requires every EDGAR client to send a User-Agent header that
identifies the caller with a contact e-mail address. That value must come
from the environment (SEC_USER_AGENT) and is never hardcoded.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_PLACEHOLDER_MARKERS = ("example.com", "your.name", "your-email", "<", ">")


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _looks_like_contact(value: str) -> bool:
    return bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", value))


@dataclass
class Settings:
    sec_user_agent: str
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    max_requests_per_second: float = 5.0
    data_dir: Path = field(default_factory=lambda: Path("data"))
    reports_dir: Path = field(default_factory=lambda: Path("reports"))
    # Data source backend: "edgar" (direct SEC APIs) or "n8n" (optional
    # self-hosted proxy). The n8n endpoint + token are read from the
    # environment only and are never stored in the repository.
    backend: str = "edgar"
    n8n_webhook_url: str | None = None
    n8n_auth_token: str | None = None

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


def load_settings(require_contact: bool = True) -> Settings:
    """Build Settings from the environment (reading .env if present)."""
    load_dotenv()

    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if require_contact:
        if not user_agent:
            raise ConfigError(
                "SEC_USER_AGENT is not set. The SEC requires a User-Agent with a "
                "contact e-mail for all EDGAR requests. Copy .env.example to .env "
                "and set SEC_USER_AGENT accordingly."
            )
        lowered = user_agent.lower()
        if not _looks_like_contact(user_agent) or any(m in lowered for m in _PLACEHOLDER_MARKERS):
            raise ConfigError(
                f"SEC_USER_AGENT ({user_agent!r}) must contain a real contact "
                "e-mail address (not a placeholder), e.g. "
                '"sec-filing-analyzer/0.1 (jane.doe@acme.org)".'
            )

    rps = float(os.environ.get("SEC_MAX_REQUESTS_PER_SECOND", "5"))
    # The SEC allows at most 10 requests per second; clamp defensively.
    rps = min(max(rps, 0.1), 10.0)

    backend = os.environ.get("SEC_BACKEND", "edgar").strip().lower()
    if backend not in ("edgar", "n8n"):
        raise ConfigError(f"SEC_BACKEND must be 'edgar' or 'n8n', got {backend!r}")

    n8n_url = os.environ.get("N8N_WEBHOOK_URL") or None
    n8n_token = os.environ.get("N8N_AUTH_TOKEN") or None
    if backend == "n8n" and not (n8n_url and n8n_token):
        raise ConfigError(
            "SEC_BACKEND=n8n requires N8N_WEBHOOK_URL and N8N_AUTH_TOKEN. These point "
            "at your own self-hosted n8n proxy and must be supplied via the environment "
            "(never committed). See examples/n8n/README.md."
        )

    return Settings(
        sec_user_agent=user_agent,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
        max_requests_per_second=rps,
        data_dir=Path(os.environ.get("SEC_DATA_DIR", "data")),
        reports_dir=Path(os.environ.get("SEC_REPORTS_DIR", "reports")),
        backend=backend,
        n8n_webhook_url=n8n_url,
        n8n_auth_token=n8n_token,
    )
