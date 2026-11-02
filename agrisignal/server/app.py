"""FastAPI Server & Low-Bandwidth AgriSignal Field & Extension Workbench."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
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


def create_app() -> FastAPI:
    application = FastAPI(
        title="AgriSignal Field & Extension Workbench",
        description="Offline-First Smallholder Agricultural Decision Support Platform",
        version=__version__,
    )
    advisory_engine = AdvisoryEngine()
    pest_engine = PestRiskEngine()

    @application.get("/", response_class=HTMLResponse)
    def workbench_index() -> HTMLResponse:
        return HTMLResponse(content=WORKBENCH_HTML, status_code=200)

    @application.get("/api/health")
    def health_check() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "agrisignal",
            "version": __version__,
            "offline_sync_protocol": "HLC-LWW-Element-Set-v1",
        }

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
