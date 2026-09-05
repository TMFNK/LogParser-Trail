# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Loopback-only OpenAI-compatible client. No cloud, no proxies, no redirects."""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from http.client import HTTPConnection
from ipaddress import ip_address
from pathlib import Path
from tempfile import gettempdir
from urllib.parse import urlparse

try:
    from fcntl import LOCK_EX, LOCK_UN, flock
except ImportError:  # Windows still gets the process-wide thread lock.
    LOCK_EX = LOCK_UN = flock = None

PROMPT_VERSION = "trail-lm-v2"
DEFAULT_BASE_URL = "http://127.0.0.1:8090/v1"
DEFAULT_MODEL = "qwen3.8-2b-q6k"
MAX_RESPONSE_BYTES = 1024 * 1024
_REQUEST_LOCK = threading.Lock()
_LOCK_PATH = Path(gettempdir()) / f"logparser-trail-lm-{os.getuid()}.lock"


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


@contextmanager
def _request_lock():
    with _REQUEST_LOCK:
        if flock is None:
            yield
            return
        flags = os.O_CREAT | os.O_RDWR | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(_LOCK_PATH, flags, 0o600)
        try:
            flock(fd, LOCK_EX)
            yield
        finally:
            flock(fd, LOCK_UN)
            os.close(fd)


def _read_response(response, connection, timeout: float) -> bytes:
    declared = response.getheader("Content-Length")
    if declared is not None and int(declared) > MAX_RESPONSE_BYTES:
        raise RuntimeError("local model response exceeds 1 MiB")
    deadline = time.monotonic() + timeout
    chunks = []
    total = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("local model response exceeded overall timeout")
        if connection.sock is not None:
            connection.sock.settimeout(remaining)
        chunk = response.read(min(65536, MAX_RESPONSE_BYTES + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise RuntimeError("local model response exceeds 1 MiB")


class LocalModelClient:
    """Serialized chat completions against a local OpenAI-compatible server."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
    ) -> None:
        require_loopback_url(base_url)
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str) -> dict:
        with _request_lock():
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
            response_body = _read_response(response, connection, self.timeout)
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
