# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Loopback-only OpenAI-compatible client. No cloud, no proxies, no redirects."""

from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from ipaddress import ip_address
from urllib.parse import urlparse

PROMPT_VERSION = "trail-lm-v1"
DEFAULT_BASE_URL = "http://127.0.0.1:8090/v1"
DEFAULT_MODEL = "qwen3.8-2b-q6k"


class LocalOnlyError(ValueError):
    """A request would leave 127.0.0.1, use a proxy, or follow a redirect."""


def require_loopback_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "http":
        raise LocalOnlyError(f"only http is allowed, got {parsed.scheme!r}")
    if parsed.username or parsed.password:
        raise LocalOnlyError("URL userinfo is not allowed")
    if parsed.query or parsed.fragment:
        raise LocalOnlyError("URL query strings and fragments are not allowed")
    host = parsed.hostname
    if host != "127.0.0.1":
        raise LocalOnlyError(f"destination must be 127.0.0.1, got {host!r}")
    if not ip_address(host).is_loopback:
        raise LocalOnlyError(f"destination is not loopback: {host}")


class LocalModelClient:
    """Serialized chat completions against a local OpenAI-compatible server."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
    ) -> None:
        require_loopback_url(base_url)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._lock = threading.Lock()

    def complete(self, prompt: str) -> dict:
        with self._lock:
            return self._complete(prompt)

    def _complete(self, prompt: str) -> dict:
        url = f"{self.base_url}/chat/completions"
        require_loopback_url(url)
        parsed = urlparse(url)
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        ).encode()
        # HTTPConnection talks directly to the literal loopback address. It
        # never reads proxy environment variables and never follows redirects.
        connection = HTTPConnection(
            parsed.hostname, parsed.port, timeout=self.timeout
        )
        try:
            connection.request(
                "POST",
                parsed.path,
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer sk-local",
                },
            )
            response = connection.getresponse()
            if 300 <= response.status < 400:
                raise LocalOnlyError(
                    f"redirects are not allowed ({response.status} -> "
                    f"{response.getheader('Location')})"
                )
            response_body = response.read()
        finally:
            connection.close()
        if not 200 <= response.status < 300:
            raise RuntimeError(
                f"local model returned HTTP {response.status}: "
                f"{response_body.decode(errors='replace')}"
            )
        raw = json.loads(response_body.decode())
        text = raw["choices"][0]["message"]["content"]
        return {
            "text": text,
            "model": raw.get("model") or self.model,
            "raw": raw,
        }
