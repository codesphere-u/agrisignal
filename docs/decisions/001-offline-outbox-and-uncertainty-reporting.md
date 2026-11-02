# ADR-001: Offline Outbox CRDT & Epistemic Uncertainty Reporting

- **Status**: Accepted
- **Date**: 2026-11-02

## Context

Agricultural decision-support systems deployed in smallholder contexts frequently fail in two ways:
1. **Overconfident Point Predictions**: Presenting a single recommendation without disclosing missing soil sensors or confidence intervals leads farmers to sow during false rainfall onsets.
2. **Last-Write-Loss on Clock Skew**: Naive HTTP REST sync endpoints using server arrival time or uncalibrated device wall clocks overwrite newer field observations when rural tablets reconnect out-of-order.

## Decision

1. **Explicit Uncertainty Bounds on Every Advisory**:
   - Every `AdvisoryResult` includes an `UncertaintyBounds` object containing `point_confidence`, `confidence_interval`, `data_completeness_score`, `missing_sensor_warnings`, and an explicit `epistemic_disclaimer` stating that agro-climatic heuristics never guarantee crop yield.
   - Even compact 160-character SMS messages embed the confidence interval (e.g., `Conf:57-87% (No yield guarantee)`).

2. **LWW-Element-Set with Hybrid Logical Clocks & SHA-256 Envelopes**:
   - Every offline field mutation is wrapped in a `FieldObservationEnvelope` signed with a canonical SHA-256 `content_hash` and stamped with a `HybridLogicalClock` (`wall_time_ms`, `lamport_counter`, `node_id`).
   - Reconciling nodes use a deterministic total order `(lamport_counter, wall_time_ms, node_id, content_hash)` across an add-set and remove-set (`LWW-Element-Set`), guaranteeing convergence regardless of network partition duration or packet arrival order.

## Consequences

- **Positive**: Complete auditability of both agronomic rules and multi-device data synchronization; zero silent data corruption from duplicate 2G packet retries.
- **Trade-offs**: Field tablets must store envelope metadata (`hlc_timestamp`, `idempotency_key`, `content_hash`), adding ~180 bytes per JSON record—well within 2G/GPRS batch payload budgets.
