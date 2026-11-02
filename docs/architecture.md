# AgriSignal System Architecture

## 1. Design Philosophy

Rural smallholder agricultural extension in East Africa operates under two hard constraints:
1. **Incomplete Field Sensing**: Most plots have access to 14-day satellite/rain-gauge rainfall estimates, while top-soil pH probes and volumetric soil moisture sensors are only intermittently available via visiting extension officers.
2. **Intermittent 2G/3G Connectivity**: Field tablets used by cooperative agents in Masaka, Mbale, or Gulu frequently remain offline for 48–96 hours before reaching a sub-county town with cellular coverage.

AgriSignal is architected as a modular, zero-external-database Python core with four subsystems:

### 1.1 Explainable Advisory Engine (`agrisignal/advisory/engine.py`)
- Evaluates crop-specific phenological thresholds (`planting`, `vegetative`, `flowering`, `harvest_drying`) scaled by the agro-ecological zone's `evaporation_factor`.
- Records every triggered heuristic in `rule_trace` so extension officers can audit *why* an action code (e.g., `DELAY_PLANTING_DRY`, `MULCH_AND_CONSERVE`, `DRAINAGE_AND_RIDGING`, `AFLATOXIN_DRYING_ALERT`) was selected.
- Computes `UncertaintyBounds` dynamically based on `data_completeness_score`.

### 1.2 Pest & Disease Early-Warning Matrix (`agrisignal/advisory/pest_risk.py`)
- Evaluates agro-climatic preconditions for Fall Armyworm, Coffee Berry Borer & Coffee Wilt, Cassava Mosaic & Brown Streak, Bean Anthracnose, and Banana Bacterial Wilt.
- Enforces biosafety by restricting automated outputs to cultural, mechanical, and biological IPM practices and providing explicit quantitative thresholds for escalating to a District Extension Officer.

### 1.3 Offline-First Outbox & LWW-Element-Set Sync Engine (`agrisignal/sync/engine.py`)
- **`HybridLogicalClock`**: Combines physical millisecond wall time with a monotonic Lamport counter and `node_id` so causality is preserved even when a field tablet's battery resets or its NTP clock drifts.
- **`OfflineOutbox`**: Queues `FieldObservationEnvelope` payloads locally with an `idempotency_key` and canonical SHA-256 `content_hash`.
- **`CentralSyncHub`**: Maintains an `LWW-Element-Set` CRDT (`_add_set` and `_remove_set`) that deterministically resolves out-of-order updates and tombstones using the total ordering tuple `(lamport_counter, wall_time_ms, node_id, content_hash)`.

### 1.4 Multilingual & 160-Char SMS Layer (`agrisignal/i18n/translator.py`)
- Translates advisories into English (`en`), Luganda (`lg`), and Swahili (`sw`).
- Guarantees `<= 160` character GSM-7 compatible SMS strings with embedded confidence intervals.
