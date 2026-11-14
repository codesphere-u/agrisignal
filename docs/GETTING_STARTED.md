# Getting Started with AgriSignal (`v1.1.0`)

AgriSignal is an offline-first smallholder agricultural decision support engine and CRDT sync platform for East Africa.

## 1. Install

```bash
git clone https://github.com/codesphere-u/agrisignal.git
cd agrisignal
uv sync --all-extras
```

## 2. Run the Offline-First Sync Simulation

```bash
agrisignal simulate-sync
```

Expected deterministic reconciliation across 3 rural tablets (`tablet-masaka-01`, `tablet-mbale-02`, `tablet-gulu-03`):
- `Total Envelopes Received: 20`
- `Accepted Unique Envelopes: 19`
- `Duplicate Retries Ignored: 1`
- `SHA-256 Integrity Failures: 0`
- `Deterministic LWW Conflicts: 4`
- `Live Reconciled Plot Records: 14`
- `Tombstoned (Deleted) Plots: 1`

## 3. Generate a Multilingual Crop Advisory & Pest-Risk Matrix

```bash
agrisignal advise --crop maize --zone lake_victoria_crescent --lang lg
agrisignal pest-risk --crop robusta_coffee --temp 26 --humidity 84 --rain 140
```

## 4. Launch the Low-Bandwidth Web Workbench

```bash
agrisignal serve --host 127.0.0.1 --port 8080
```
