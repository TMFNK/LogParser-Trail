# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Local-model transport never leaves 127.0.0.1."""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse.lm import (  # noqa: E402
    LocalModelClient,
    LocalOnlyError,
    require_loopback_url,
)


class Handler(BaseHTTPRequestHandler):
    requests = []
    active = 0
    max_active = 0
    lock = threading.Lock()

    def do_POST(self):
        with self.lock:
            type(self).active += 1
            type(self).max_active = max(type(self).max_active, type(self).active)
        try:
            time.sleep(0.03)
            length = int(self.headers["Content-Length"])
            request = json.loads(self.rfile.read(length))
            type(self).requests.append(request)
            body = json.dumps(
                {
                    "model": "local-test",
                    "choices": [{"message": {"content": "SAME"}}],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        finally:
            with self.lock:
                type(self).active -= 1

    def log_message(self, *args):
        pass


class RedirectHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(302)
        self.send_header("Location", "http://example.com/v1/chat/completions")
        self.end_headers()

    def log_message(self, *args):
        pass


class OversizedHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Length", str(1024 * 1024 + 1))
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def local_server():
    Handler.requests = []
    Handler.active = 0
    Handler.max_active = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_client_uses_local_server_without_environment_proxy(local_server, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    client = LocalModelClient(local_server, "requested-model", timeout=2)

    result = client.complete("same event?")

    assert result["text"] == "SAME"
    assert result["model"] == "local-test"
    assert Handler.requests[0]["model"] == "requested-model"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8090/v1",
        "http://localhost:8090/v1",
        "http://127.0.0.2:8090/v1",
        "http://127.0.0.1.example.com:8090/v1",
        "http://user@127.0.0.1:8090/v1",
        "http://127.0.0.1:8090/v1?target=example.com",
        "http://example.com/v1",
    ],
)
def test_non_exact_loopback_destinations_are_rejected(url):
    with pytest.raises(LocalOnlyError):
        require_loopback_url(url)


def test_redirects_are_rejected():
    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        client = LocalModelClient(
            f"http://127.0.0.1:{server.server_port}/v1", timeout=2
        )
        with pytest.raises(LocalOnlyError, match="redirects are not allowed"):
            client.complete("same event?")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_client_serializes_concurrent_calls(local_server):
    clients = [LocalModelClient(local_server, timeout=2) for _ in range(3)]
    threads = [
        threading.Thread(target=client.complete, args=(f"request {i}",))
        for i, client in enumerate(clients)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(Handler.requests) == 3
    assert Handler.max_active == 1


def test_oversized_response_is_rejected():
    server = ThreadingHTTPServer(("127.0.0.1", 0), OversizedHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        client = LocalModelClient(
            f"http://127.0.0.1:{server.server_port}/v1", timeout=2
        )
        with pytest.raises(RuntimeError, match="exceeds 1 MiB"):
            client.complete("same event?")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
