# Testing & Verification Guide

AgriSignal includes 36 automated tests in `tests/test_agrisignal.py` validating every subsystem.

## Running the Test Suite

```bash
uv run --with pytest --with fastapi --with httpx --with pydantic pytest -v
```

## Test Coverage Matrix

1. **Parametrized Crop & Zone Advisory Rules**:
   - Tests all 6 crops (`maize`, `robusta_coffee`, `beans`, `cassava`, `matooke_banana`, `groundnuts`) and all 4 agro-ecological zones (`lake_victoria_crescent`, `western_highlands`, `northern_savannah`, `eastern_plains`).
   - Verifies drought delay, flowering critical stress, marginal moisture mulching, waterlogging drainage, acidic/alkaline soil pH amendments, and harvest aflatoxin moisture alerts.
2. **Uncertainty & Epistemic Bound Invariants**:
   - Verifies that missing optional sensors reduce `data_completeness_score`, populate `missing_sensor_warnings`, and widen `confidence_interval`.
3. **Pest & Disease IPM Matrix**:
   - Verifies Fall Armyworm, Coffee Berry Borer / Wilt, Cassava Mosaic / CBSD, Bean Anthracnose, and Banana Bacterial Wilt risk scoring and non-chemical IPM output.
4. **Offline Outbox & LWW-Element-Set Sync**:
   - Verifies Hybrid Logical Clock monotonicity under backward clock drift, idempotency replay suppression, SHA-256 payload tampering rejection, out-of-order LWW resolution, tombstone deletion, and the 20-record 3-tablet simulation.
5. **Multilingual SMS Bounds (`<= 160` chars)**:
   - Parametrized across all languages (`en`, `lg`, `sw`) and all 10 `action_code` values to guarantee every SMS output is `<= 160` characters.
6. **CLI & FastAPI Workbench**:
   - End-to-end verification of `agrisignal advise`, `agrisignal simulate-sync`, and all FastAPI HTML/JSON endpoints.
