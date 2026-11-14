# Advisory Engine, IPM Matrix & LWW-Element-Set Sync

## Agro-Ecological Zones & Crops
AgriSignal models 6 East African staple and cash crops across 4 zones:
- **Crops**: `maize`, `robusta_coffee`, `beans`, `cassava`, `matooke_banana`, `groundnuts`
- **Zones**: `lake_victoria_crescent`, `western_highlands`, `northern_savannah`, `eastern_plains`

## Epistemic Confidence & Uncertainty Bounds
Every advisory output computes:
- `point_confidence` and explicit `confidence_interval`
- `data_completeness_score`
- `missing_sensor_warnings`
- `epistemic_disclaimer` stating model assumptions and soil/rainfall gaps

## Multilingual SMS Delivery (`<= 160` chars)
`agrisignal.i18n.translator` formats advisories in English (`en`), Luganda (`lg`), and Swahili (`sw`), enforcing strict `160`-character GSM-7 SMS length limits for rural feature-phone delivery.

## Hybrid Logical Clock + LWW-Element-Set CRDT
`agrisignal.sync.engine` orders concurrent field edits using `(lamport, wall_time_ms, node_id)` tuples, validates SHA-256 content hashes, drops duplicate retries idempotently, and resolves `UPSERT` vs `DELETE` tombstones deterministically.
