from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
from fastapi.testclient import TestClient

from agrisignal.cli import run_cli
from agrisignal.server.app import _MAX_REQUEST_BODY_BYTES, create_app


def test_health_probes_security_headers_and_request_id() -> None:
    app = create_app()
    with TestClient(app) as client:
        for path in ("/health", "/healthz", "/readyz", "/api/health"):
            res = client.get(path, headers={"X-Request-ID": "agri-trace-01"})
            assert res.status_code == 200
            assert res.headers["x-request-id"] == "agri-trace-01"
            assert res.headers["x-content-type-options"] == "nosniff"
            assert res.headers["x-frame-options"] == "SAMEORIGIN"
            assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
            assert res.headers["cache-control"] == "no-store"
            assert "x-response-time-ms" in res.headers

            head = client.head(path)
            assert head.status_code == 200
            assert head.headers["x-content-type-options"] == "nosniff"

        bad_id = client.get("/healthz", headers={"X-Request-ID": "bad\nvalue"})
        assert bad_id.status_code == 200
        assert bad_id.headers["x-request-id"] != "bad\nvalue"

        dash = client.get("/")
        assert dash.status_code == 200
        assert dash.headers["x-frame-options"] == "SAMEORIGIN"
        assert "cache-control" not in dash.headers


def test_metrics_prometheus_and_json() -> None:
    app = create_app()
    with TestClient(app) as client:
        client.get("/api/health")
        prom = client.get("/metrics")
        assert prom.status_code == 200
        assert "text/plain" in prom.headers["content-type"]
        assert "agrisignal_http_requests_total" in prom.text
        assert "agrisignal_supported_crops" in prom.text
        assert "agrisignal_supported_zones" in prom.text
        assert "agrisignal_supported_languages" in prom.text

        js = client.get("/metrics", headers={"Accept": "application/json"})
        assert js.status_code == 200
        body = js.json()
        assert body["requests_total"] >= 1
        assert body["supported_languages"] >= 3
        assert body["supported_crops"] >= 1
        assert body["supported_zones"] >= 1


def test_payload_limit_413_validation_and_sanitized_500(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    @app.get("/_boom")
    def _boom() -> dict[str, str]:
        raise RuntimeError("sensitive-internal-secret")

    oversized = json.dumps({"envelopes": [], "pad": "x" * (_MAX_REQUEST_BODY_BYTES + 64)})
    with TestClient(app, raise_server_exceptions=False) as client:
        too_big = client.post(
            "/api/sync/reconcile",
            content=oversized,
            headers={"Content-Type": "application/json"},
        )
        assert too_big.status_code == 413

        boom = client.get("/_boom", headers={"X-Request-ID": "agri-500"})
        assert boom.status_code == 500
        assert boom.json() == {"error": "Internal server error", "request_id": "agri-500"}
        assert "sensitive-internal-secret" not in boom.text
        assert boom.headers["x-content-type-options"] == "nosniff"
        assert boom.headers["x-request-id"] == "agri-500"

        bad_validation = client.post("/api/advise", json={"crop": "unknown_crop"})
        assert bad_validation.status_code == 422

        reconcile = client.post("/api/sync/reconcile", json={"envelopes": []})
        assert reconcile.status_code == 200
        assert reconcile.headers["cache-control"] == "no-store"

    monkeypatch.setenv("AGRISIGNAL_MAX_BODY_BYTES", "128")
    capped = create_app()
    with TestClient(capped) as capped_client:
        res = capped_client.post(
            "/api/sync/reconcile",
            content=json.dumps({"envelopes": [], "pad": "y" * 256}),
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 413


def test_cli_commands_and_live_serve(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        run_cli(
            [
                "advise",
                "--crop",
                "maize",
                "--zone",
                "lake_victoria_crescent",
                "--rain-14d",
                "85",
                "--soil-ph",
                "6.2",
                "--lang",
                "en",
            ]
        )
        == 0
    )
    assert run_cli(["simulate-sync", "--json"]) == 0
    assert run_cli(["simulate-sync"]) == 0
    assert run_cli(["pest-risk", "--crop", "maize", "--zone", "lake_victoria_crescent"]) == 0
    assert run_cli(["pest-risk", "--crop", "maize", "--zone", "lake_victoria_crescent", "--json"]) == 0
    captured = capsys.readouterr().out
    assert "OVERALL PEST RISK" in captured

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    proc = subprocess.Popen(
        [sys.executable, "-m", "agrisignal.cli", "serve", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/readyz", timeout=1) as resp:
                    assert resp.status == 200
                req = urllib.request.Request(f"http://127.0.0.1:{port}/health", method="HEAD")
                with urllib.request.urlopen(req, timeout=1) as resp:
                    assert resp.status == 200
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("agrisignal CLI server failed to become ready")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
