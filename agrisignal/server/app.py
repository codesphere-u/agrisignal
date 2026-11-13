"""FastAPI Server & Low-Bandwidth AgriSignal Field & Extension Workbench."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from collections import Counter
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from agrisignal import __version__
from agrisignal.advisory.engine import (
    AGRO_ZONES,
    CROP_PROFILES,
    AdvisoryEngine,
    AdvisoryInput,
    AdvisoryResult,
)
from agrisignal.advisory.pest_risk import PestRiskEngine, PestRiskInput, PestRiskReport
from agrisignal.i18n.translator import SUPPORTED_LANGUAGES
from agrisignal.sync.engine import (
    CentralSyncHub,
    FieldObservationEnvelope,
    SyncReconciliationReport,
    simulate_rural_sync_scenario,
)

logger = logging.getLogger("agrisignal.server")
_SERVICE_NAME = "agrisignal"

_DEFAULT_MAX_BODY_BYTES = 1_048_576  # 1 MiB
_MAX_REQUEST_BODY_BYTES = _DEFAULT_MAX_BODY_BYTES
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class _JsonLogFormatter(logging.Formatter):
    """Emit structured JSON log lines for container stdout aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": _SERVICE_NAME,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for attr in ("request_id", "method", "path", "status_code", "latency_ms", "event"):
            value = getattr(record, attr, None)
            if value is not None:
                payload[attr] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def _configure_json_logging() -> None:
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonLogFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


def _resolve_max_body_bytes(explicit: int | None = None) -> int:
    if explicit is not None and explicit > 0:
        return explicit
    raw = os.getenv("AGRISIGNAL_MAX_BODY_BYTES", "").strip()
    if raw:
        try:
            parsed = int(raw)
        except ValueError:
            parsed = 0
        if parsed > 0:
            return parsed
    return _DEFAULT_MAX_BODY_BYTES


def _should_disable_cache(path: str) -> bool:
    return (
        path.startswith("/api/")
        or path == "/api"
        or path.startswith("/health")
        or path in {"/readyz", "/metrics"}
    )


def _security_headers_for_path(path: str) -> dict[str, str]:
    headers = dict(_SECURITY_HEADERS)
    if _should_disable_cache(path):
        headers["Cache-Control"] = "no-store"
    return headers


class _RuntimeMetrics:
    """Thread-safe in-memory HTTP metrics for /metrics monitoring."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_at = time.monotonic()
        self.requests_total = 0
        self.client_errors_4xx = 0
        self.server_errors_5xx = 0
        self.latency_ms_sum = 0.0
        self.status_code_counts: Counter[int] = Counter()

    def record(self, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self.requests_total += 1
            if 400 <= status_code < 500:
                self.client_errors_4xx += 1
            elif status_code >= 500:
                self.server_errors_5xx += 1
            self.latency_ms_sum += latency_ms
            self.status_code_counts[status_code] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "service": _SERVICE_NAME,
                "uptime_seconds": round(time.monotonic() - self.started_at, 3),
                "total_requests": self.requests_total,
                "requests_total": self.requests_total,
                "client_errors_4xx": self.client_errors_4xx,
                "server_errors_5xx": self.server_errors_5xx,
                "total_errors": self.client_errors_4xx + self.server_errors_5xx,
                "errors_total": self.server_errors_5xx,
                "latency_ms_sum": round(self.latency_ms_sum, 3),
                "status_code_counts": dict(sorted(self.status_code_counts.items())),
                "supported_crops": len(CROP_PROFILES),
                "supported_zones": len(AGRO_ZONES),
                "supported_languages": len(SUPPORTED_LANGUAGES),
            }


def _sanitize_request_id(raw: str | None) -> str:
    if raw:
        candidate = raw.strip()
        if _REQUEST_ID_PATTERN.fullmatch(candidate):
            return candidate
    return uuid.uuid4().hex[:16]


def _format_prometheus_metrics(snapshot: dict[str, Any]) -> str:
    lines = [
        "# HELP agrisignal_uptime_seconds Server uptime in seconds.",
        "# TYPE agrisignal_uptime_seconds gauge",
        f"agrisignal_uptime_seconds {snapshot['uptime_seconds']}",
        "# HELP agrisignal_http_requests_total Total HTTP requests handled.",
        "# TYPE agrisignal_http_requests_total counter",
        f"agrisignal_http_requests_total {snapshot['requests_total']}",
        "# HELP agrisignal_http_errors_total Total HTTP 5xx responses.",
        "# TYPE agrisignal_http_errors_total counter",
        f"agrisignal_http_errors_total {snapshot['errors_total']}",
        "# HELP agrisignal_http_request_duration_ms_sum Cumulative HTTP response latency in ms.",
        "# TYPE agrisignal_http_request_duration_ms_sum counter",
        f"agrisignal_http_request_duration_ms_sum {snapshot['latency_ms_sum']}",
        "# HELP agrisignal_supported_crops Number of agronomic crop profiles configured.",
        "# TYPE agrisignal_supported_crops gauge",
        f"agrisignal_supported_crops {snapshot['supported_crops']}",
        "# HELP agrisignal_supported_zones Number of agro-ecological zones configured.",
        "# TYPE agrisignal_supported_zones gauge",
        f"agrisignal_supported_zones {snapshot['supported_zones']}",
        "# HELP agrisignal_supported_languages Number of advisory languages supported.",
        "# TYPE agrisignal_supported_languages gauge",
        f"agrisignal_supported_languages {snapshot['supported_languages']}",
    ]
    for code, count in snapshot["status_code_counts"].items():
        lines.append(f'agrisignal_http_responses_total{{status="{code}"}} {count}')
    return "\n".join(lines) + "\n"


class _HardeningMiddleware:
    """ASGI middleware enforcing request-ID correlation, body caps, timing & security headers."""

    def __init__(
        self,
        app: Any,
        metrics: _RuntimeMetrics,
        max_body_bytes: int = _DEFAULT_MAX_BODY_BYTES,
    ) -> None:
        self.app = app
        self.metrics = metrics
        self.max_body_bytes = max_body_bytes

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        req_headers = {bytes(k).lower(): bytes(v) for k, v in scope.get("headers", [])}
        raw_req_id = req_headers.get(b"x-request-id")
        request_id = _sanitize_request_id(raw_req_id.decode("latin-1") if raw_req_id else None)
        scope.setdefault("state", {})["request_id"] = request_id
        path = str(scope.get("path", "/"))
        method = str(scope.get("method", "GET")).upper()
        started = time.perf_counter()
        status_code = 500
        sec_headers = _security_headers_for_path(path)

        async def _send_with_headers(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                headers = list(message.get("headers", []))
                existing = {bytes(k).lower() for k, _ in headers}
                for key, val in sec_headers.items():
                    if key.lower().encode("latin-1") not in existing:
                        headers.append((key.encode("latin-1"), val.encode("latin-1")))
                if b"x-request-id" not in existing:
                    headers.append((b"x-request-id", request_id.encode("latin-1")))
                if b"x-response-time-ms" not in existing:
                    headers.append((b"x-response-time-ms", f"{elapsed_ms:.2f}".encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        if method in {"POST", "PUT", "PATCH"} and b"content-length" in req_headers:
            try:
                content_length = int(req_headers[b"content-length"].decode("latin-1"))
            except ValueError:
                content_length = -1
            if content_length < 0 or content_length > self.max_body_bytes:
                resp = JSONResponse(
                    status_code=413,
                    content={
                        "error": "Payload too large",
                        "max_bytes": self.max_body_bytes,
                        "request_id": request_id,
                    },
                )
                await resp(scope, receive, _send_with_headers)
                self.metrics.record(413, (time.perf_counter() - started) * 1000.0)
                return

        buffered_chunks: list[MutableMapping[str, Any]] | None = None
        if method in {"POST", "PUT", "PATCH"}:
            total_bytes = 0
            chunks: list[MutableMapping[str, Any]] = []
            more_body = True
            while more_body:
                event = await receive()
                if event["type"] == "http.disconnect":
                    chunks.append(event)
                    break
                if event["type"] == "http.request":
                    body_part = event.get("body", b"")
                    total_bytes += len(body_part)
                    if total_bytes > self.max_body_bytes:
                        resp = JSONResponse(
                            status_code=413,
                            content={
                                "error": "Payload too large",
                                "max_bytes": self.max_body_bytes,
                                "request_id": request_id,
                            },
                        )
                        await resp(scope, receive, _send_with_headers)
                        self.metrics.record(413, (time.perf_counter() - started) * 1000.0)
                        return
                    chunks.append(event)
                    more_body = bool(event.get("more_body", False))
                else:
                    chunks.append(event)
            buffered_chunks = chunks

        chunk_iter = iter(buffered_chunks) if buffered_chunks is not None else None

        async def _bounded_receive() -> MutableMapping[str, Any]:
            if chunk_iter is None:
                return await receive()
            try:
                return next(chunk_iter)
            except StopIteration:
                return {"type": "http.disconnect"}

        try:
            await self.app(scope, _bounded_receive, _send_with_headers)
        except Exception:
            logger.exception("Unhandled exception in AgriSignal ASGI pipeline request_id=%s", request_id)
            resp = JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "request_id": request_id},
                headers={**sec_headers, "X-Request-ID": request_id},
            )
            await resp(scope, receive, _send_with_headers)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self.metrics.record(status_code, elapsed_ms)
            logger.info(
                "http_request",
                extra={
                    "event": "http_request",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "latency_ms": round(elapsed_ms, 2),
                },
            )


class BatchSyncRequest(BaseModel):
    envelopes: list[FieldObservationEnvelope]


WORKBENCH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AgriSignal v1.0 — Offline-First Smallholder Decision Support Workbench</title>
  <style>
    :root {
      --bg: #f6f8f5;
      --surface: #ffffff;
      --border: #d0ddd0;
      --primary: #1b5e20;
      --primary-light: #e8f5e9;
      --text: #1c251c;
      --muted: #4f5d4f;
      --warn: #e65100;
      --crit: #b71c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }
    header {
      background: var(--primary);
      color: #fff;
      padding: 1rem 1.5rem;
      border-bottom: 3px solid #0d3b10;
    }
    header h1 { margin: 0; font-size: 1.35rem; }
    header p { margin: 0.25rem 0 0; font-size: 0.9rem; opacity: 0.92; }
    main {
      max-width: 1180px;
      margin: 1.25rem auto;
      padding: 0 1rem;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 1.25rem;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 1.1rem;
      box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .card h2 {
      margin-top: 0;
      font-size: 1.1rem;
      color: var(--primary);
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.45rem;
    }
    label {
      display: block;
      font-size: 0.85rem;
      font-weight: 600;
      margin: 0.55rem 0 0.2rem;
    }
    select, input {
      width: 100%;
      padding: 0.45rem;
      border: 1px solid #b6c6b6;
      border-radius: 4px;
      font-size: 0.9rem;
    }
    button {
      margin-top: 0.8rem;
      width: 100%;
      padding: 0.6rem;
      background: var(--primary);
      color: #fff;
      font-weight: 600;
      border: none;
      border-radius: 4px;
      cursor: pointer;
    }
    button:hover { background: #144718; }
    .sms-box {
      background: #1e272e;
      color: #a3ffac;
      font-family: monospace;
      padding: 0.65rem;
      border-radius: 4px;
      font-size: 0.84rem;
      margin-top: 0.6rem;
      word-break: break-word;
    }
    .badge {
      display: inline-block;
      padding: 0.15rem 0.45rem;
      font-size: 0.78rem;
      font-weight: 700;
      border-radius: 3px;
      background: var(--primary-light);
      color: var(--primary);
    }
    pre {
      background: #f1f5f1;
      padding: 0.65rem;
      border-radius: 4px;
      font-size: 0.8rem;
      overflow-x: auto;
      max-height: 290px;
    }
    footer {
      text-align: center;
      font-size: 0.8rem;
      color: var(--muted);
      padding: 1.5rem;
    }
  </style>
</head>
<body>
  <header>
    <h1>AgriSignal Field &amp; Extension Workbench (v1.0)</h1>
    <p>Offline-First Smallholder Crop Advisory, Uncertainty Bounds, Non-Chemical IPM &amp; LWW-Element-Set Sync Inspector</p>
  </header>
  <main>
    <section class="card" aria-labelledby="advisory-heading">
      <h2 id="advisory-heading">1. Agro-Ecological Zone &amp; Crop Advisory Simulator</h2>
      <label for="crop">Crop</label>
      <select id="crop">
        <option value="maize">Maize (Zea mays)</option>
        <option value="robusta_coffee">Robusta Coffee (Coffea canephora)</option>
        <option value="beans">Common Beans (Phaseolus vulgaris)</option>
        <option value="cassava">Cassava (Manihot esculenta)</option>
        <option value="matooke_banana">Matooke Highland Banana</option>
        <option value="groundnuts">Groundnuts (Arachis hypogaea)</option>
      </select>
      <label for="zone">Agro-Ecological Zone</label>
      <select id="zone">
        <option value="lake_victoria_crescent">Lake Victoria Crescent</option>
        <option value="western_highlands">Western Highlands</option>
        <option value="northern_savannah">Northern Savannah</option>
        <option value="eastern_plains">Eastern Plains</option>
      </select>
      <label for="stage">Growth Stage</label>
      <select id="stage">
        <option value="planting">Planting / Sowing</option>
        <option value="vegetative">Vegetative</option>
        <option value="flowering">Flowering / Podding</option>
        <option value="harvest_drying">Harvest &amp; Post-Harvest Drying</option>
      </select>
      <label for="rain">14-Day Cumulative Rainfall (mm)</label>
      <input id="rain" type="number" value="85" min="0" max="600" />
      <label for="ph">Top-Soil pH (optional)</label>
      <input id="ph" type="number" step="0.1" value="6.2" min="3.5" max="9.0" />
      <label for="lang">Advisory &amp; SMS Language</label>
      <select id="lang">
        <option value="en">English (en)</option>
        <option value="lg">Oluganda / Luganda (lg)</option>
        <option value="sw">Kiswahili / Swahili (sw)</option>
      </select>
      <button type="button" onclick="runAdvisory()">Generate Explainable Advisory</button>
      <div id="sms-preview" class="sms-box">SMS 160-Char Preview will appear here...</div>
      <pre id="advisory-output">Click "Generate Explainable Advisory" to evaluate rules &amp; uncertainty bounds.</pre>
    </section>

    <section class="card" aria-labelledby="pest-heading">
      <h2 id="pest-heading">2. Pest &amp; Climate Risk Early-Warning Matrix</h2>
      <label for="pest-temp">14-Day Temperature Anomaly (&deg;C)</label>
      <input id="pest-temp" type="number" step="0.1" value="1.6" />
      <label for="pest-rh">Relative Humidity (%)</label>
      <input id="pest-rh" type="number" value="78" />
      <label for="pest-dry">Longest Consecutive Dry Spell (days)</label>
      <input id="pest-dry" type="number" value="6" />
      <button type="button" onclick="runPestRisk()">Evaluate Non-Chemical IPM Risk Matrix</button>
      <pre id="pest-output">Evaluates Fall Armyworm, Coffee Berry Borer / Wilt, Cassava Mosaic / CBSD, and Bean Anthracnose.</pre>
    </section>

    <section class="card" aria-labelledby="sync-heading">
      <h2 id="sync-heading">3. Offline Outbox &amp; Conflict-Resolution Sync Inspector</h2>
      <p style="font-size:0.85rem;color:var(--muted);">
        Simulates 20 offline field observations across 3 rural tablets (<code>tablet-masaka-01</code>,
        <code>tablet-mbale-02</code>, <code>tablet-gulu-03</code>) with network partitions, out-of-order
        delivery, duplicate retries, and deterministic LWW-Element-Set CRDT reconciliation.
      </p>
      <button type="button" onclick="runSyncSim()">Run 20-Record Multi-Tablet Sync Simulation</button>
      <pre id="sync-output">Click above to inspect HLC timestamps, SHA-256 content hashes, and LWW conflict resolution.</pre>
    </section>
  </main>
  <footer>
    AgriSignal v1.0 &bull; Designed for Intermittent 2G/3G Rural Connectivity &bull; Explainable Rules &amp; Explicit Uncertainty Bounds
  </footer>
  <script>
    async function runAdvisory() {
      const payload = {
        crop: document.getElementById('crop').value,
        zone: document.getElementById('zone').value,
        growth_stage: document.getElementById('stage').value,
        rain_14d_mm: parseFloat(document.getElementById('rain').value || '0'),
        soil_ph: parseFloat(document.getElementById('ph').value || '6.0'),
        lang: document.getElementById('lang').value
      };
      const res = await fetch('/api/advise', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      document.getElementById('sms-preview').textContent =
        `SMS (${data.sms_160.length}/160 chars): ${data.sms_160}`;
      document.getElementById('advisory-output').textContent = JSON.stringify(data, null, 2);
    }
    async function runPestRisk() {
      const payload = {
        crop: document.getElementById('crop').value,
        zone: document.getElementById('zone').value,
        rain_14d_mm: parseFloat(document.getElementById('rain').value || '0'),
        temp_anomaly_c: parseFloat(document.getElementById('pest-temp').value || '0'),
        relative_humidity_pct: parseFloat(document.getElementById('pest-rh').value || '70'),
        dry_spell_days: parseInt(document.getElementById('pest-dry').value || '3', 10)
      };
      const res = await fetch('/api/pest-risk', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      document.getElementById('pest-output').textContent = JSON.stringify(data, null, 2);
    }
    async function runSyncSim() {
      const res = await fetch('/api/sync/simulate', { method: 'POST' });
      const data = await res.json();
      document.getElementById('sync-output').textContent = JSON.stringify(data, null, 2);
    }
  </script>
</body>
</html>
"""


def create_app(*, max_body_bytes: int | None = None) -> FastAPI:
    """Create and configure the AgriSignal FastAPI application."""
    _configure_json_logging()
    resolved_max_body = _resolve_max_body_bytes(max_body_bytes)
    metrics = _RuntimeMetrics()
    advisory_engine = AdvisoryEngine()
    pest_engine = PestRiskEngine()

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        _app.state.ready = True
        logger.info("AgriSignal Workbench server started version=%s", __version__)
        yield
        _app.state.ready = False
        logger.info("AgriSignal Workbench server stopping")

    application = FastAPI(
        title="AgriSignal Field & Extension Workbench",
        description="Offline-First Smallholder Agricultural Decision Support Platform",
        version=__version__,
        lifespan=_lifespan,
    )
    application.state.ready = True
    application.add_middleware(_HardeningMiddleware, metrics=metrics, max_body_bytes=resolved_max_body)

    @application.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or _sanitize_request_id(
            request.headers.get("x-request-id")
        )
        logger.exception("Unhandled AgriSignal exception request_id=%s", request_id, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "request_id": request_id},
            headers={**_security_headers_for_path(request.url.path), "X-Request-ID": request_id},
        )

    @application.get("/", response_class=HTMLResponse)
    def workbench_index() -> HTMLResponse:
        return HTMLResponse(content=WORKBENCH_HTML, status_code=200)

    def _health_payload(*, ready: bool = True) -> dict[str, Any]:
        return {
            "status": "ok" if ready else "starting",
            "service": "agrisignal",
            "version": __version__,
            "ready": ready,
            "offline_sync_protocol": "HLC-LWW-Element-Set-v1",
        }

    @application.api_route("/health", methods=["GET", "HEAD"])
    @application.api_route("/healthz", methods=["GET", "HEAD"])
    @application.api_route("/api/health", methods=["GET", "HEAD"])
    def health_check(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(status_code=200)
        return JSONResponse(content=_health_payload(), status_code=200)

    @application.api_route("/readyz", methods=["GET", "HEAD"])
    def readiness_check(request: Request) -> Response:
        is_ready = bool(getattr(application.state, "ready", True))
        status = 200 if is_ready else 503
        if request.method == "HEAD":
            return Response(status_code=status)
        return JSONResponse(content=_health_payload(ready=is_ready), status_code=status)

    @application.get("/metrics")
    def runtime_metrics(request: Request, format: str | None = None) -> Response:
        snap = metrics.snapshot()
        accept = request.headers.get("accept", "")
        if format == "json" or "application/json" in accept:
            return JSONResponse(content=snap)
        return PlainTextResponse(
            content=_format_prometheus_metrics(snap),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @application.get("/api/metadata")
    def metadata() -> dict[str, Any]:
        return {
            "crops": CROP_PROFILES,
            "zones": AGRO_ZONES,
            "languages": SUPPORTED_LANGUAGES,
        }

    @application.post("/api/advise", response_model=AdvisoryResult)
    def evaluate_advisory(payload: AdvisoryInput) -> AdvisoryResult:
        return advisory_engine.evaluate(payload)

    @application.post("/api/pest-risk", response_model=PestRiskReport)
    def evaluate_pest_risk(payload: PestRiskInput) -> PestRiskReport:
        return pest_engine.evaluate(payload)

    @application.post("/api/sync/simulate", response_model=SyncReconciliationReport)
    def simulate_sync() -> SyncReconciliationReport:
        return simulate_rural_sync_scenario()

    @application.post("/api/sync/reconcile", response_model=SyncReconciliationReport)
    def reconcile_batch(batch: BatchSyncRequest) -> SyncReconciliationReport:
        hub = CentralSyncHub()
        return hub.ingest_batch(batch.envelopes)

    return application


app = create_app()
