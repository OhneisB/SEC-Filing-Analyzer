"""Optional n8n proxy backend for EDGAR requests.

This is an *illustrative, opt-in* alternative to hitting SEC EDGAR directly.
In environments where outbound access to sec.gov is blocked, requests can be
routed through a self-hosted n8n webhook that fetches the target URL
server-side and returns the body.

Design goals (security):

- The webhook URL and auth token come exclusively from the environment
  (``N8N_WEBHOOK_URL`` / ``N8N_AUTH_TOKEN``); nothing is hardcoded and no
  hosted endpoint ships in this repository.
- Every request carries a Bearer token so the proxy is not an open relay —
  a caller without the token gets rejected by n8n.
- This class deliberately mimics the small ``requests.Session`` surface
  (``headers`` + ``get``) that :class:`EdgarClient` relies on, so the exact
  same client logic (caching, rate limiting, parsing) works unchanged with
  either backend.

An example n8n workflow that implements the proxy is provided (sanitized,
without any URL or token) under ``examples/n8n/``.
"""

from __future__ import annotations

import requests


class N8nBackendSession:
    """A drop-in ``session`` for :class:`EdgarClient` that proxies via n8n."""

    def __init__(self, webhook_url: str, auth_token: str, http: requests.Session | None = None):
        if not webhook_url or not auth_token:
            raise ValueError("n8n backend requires both a webhook URL and an auth token")
        self.webhook_url = webhook_url
        self.auth_token = auth_token
        self.headers: dict[str, str] = {}
        self._http = http or requests.Session()

    def get(self, url: str, timeout: int | float = 30) -> requests.Response:
        """Fetch ``url`` through the n8n proxy.

        The proxy receives the target SEC URL as a query parameter and returns
        the upstream body verbatim. The SEC-mandated User-Agent is configured
        inside the n8n workflow, so the contact e-mail never leaves the server.
        """
        return self._http.get(
            self.webhook_url,
            params={"url": url},
            headers={"Authorization": f"Bearer {self.auth_token}", **self.headers},
            timeout=timeout,
        )
