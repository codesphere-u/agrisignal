from __future__ import annotations

import json

from fastapi.testclient import TestClient

from agrisignal.server.app import _MAX_REQUEST_BODY_BYTES, create_app


def test_health_probes_security_headers_and_request_id():
    app = create_app()
    with TestClient(app) as client:
        for path in ("/health", "/healthz", "/readyz", "/api/health"):
            res = client.get(path, headers={"X-Request-ID": "agri-trace-01"})
            assert res.status_code == 200
            assert res.headers["x-request-id"] == "agri-trace-01"
            assert res.headers["x-content-type-options"] == "nosniff"
            assert res.headers["x-frame-options"] == "DENY"
            assert res.headers["cache-control"] == "no-store"
            assert "x-response-time-ms" in res.headers

            head = client.head(path)
            assert head.status_code == 200

        bad_id = client.get("/healthz", headers={"X-Request-ID": "bad\nvalue"})
        assert bad_id.status_code == 200
        assert bad_id.headers["x-request-id"] != "bad\nvalue"


def test_metrics_prometheus_and_json():
    app = create_app()
    with TestClient(app) as client:
        client.get("/api/health")
        prom = client.get("/metrics")
        assert prom.status_code == 200
        assert "agrisignal_http_requests_total" in prom.text
        assert "agrisignal_supported_crops" in prom.text

        js = client.get("/metrics?format=json")
        assert js.status_code == 200
        body = js.json()
        assert body["requests_total"] >= 1
        assert body["supported_languages"] >= 3


def test_payload_limit_413_and_sanitized_500():
    app = create_app()

    @app.get("/_boom")
    def _boom():
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
