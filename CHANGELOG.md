# Changelog

All notable changes to **AgriSignal** are documented in this file.

## [1.0.0] - 2026-11-02

### Added
- **Explainable Crop & Planting Advisory Engine (`agrisignal/advisory/engine.py`)**: Rule-based agro-climatic evaluation for `maize`, `robusta_coffee`, `beans`, `cassava`, `matooke_banana`, and `groundnuts` across 4 East African agro-ecological zones (`lake_victoria_crescent`, `western_highlands`, `northern_savannah`, `eastern_plains`).
- **Explicit Uncertainty & Confidence Bounds**: Every advisory reports `point_confidence`, `confidence_interval`, `data_completeness_score`, `missing_sensor_warnings`, and an `epistemic_disclaimer`.
- **Pest & Disease Early-Warning Risk Matrix (`agrisignal/advisory/pest_risk.py`)**: Precondition models and non-chemical IPM guidance for Fall Armyworm, Coffee Berry Borer & Coffee Wilt, Cassava Mosaic & Brown Streak, Bean Anthracnose, and Banana Bacterial Wilt.
- **Offline-First Outbox & LWW-Element-Set Sync Engine (`agrisignal/sync/engine.py`)**: Hybrid Logical Clocks (`HybridLogicalClock`), SHA-256 content hashes, idempotency replay protection, and 20-record 3-tablet simulation.
- **Multilingual Localization (`agrisignal/i18n/translator.py`)**: Built-in English (`en`), Luganda (`lg`), and Swahili (`sw`) summaries and strict `<= 160` character SMS formatter.
- **CLI & FastAPI Workbench (`agrisignal/cli.py`, `agrisignal/server/app.py`)**: Full CLI (`advise`, `simulate-sync`, `pest-risk`, `serve`) and low-bandwidth responsive web workbench.
