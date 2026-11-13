"""Offline-First Outbox & LWW-Element-Set Conflict-Free Sync Engine."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, cast

from pydantic import BaseModel, Field


class HybridLogicalClock(BaseModel):
    """Lamport + Physical Wall-Clock Hybrid Logical Timestamp for offline tablets."""

    wall_time_ms: int = Field(..., ge=0)
    lamport_counter: int = Field(default=0, ge=0)
    node_id: str

    def tick(self, current_wall_ms: int) -> HybridLogicalClock:
        if current_wall_ms > self.wall_time_ms:
            self.wall_time_ms = current_wall_ms
            self.lamport_counter = 0
        else:
            self.lamport_counter += 1
        return cast(HybridLogicalClock, self.model_copy())

    def receive(self, remote_wall_ms: int, remote_lamport: int, current_wall_ms: int) -> HybridLogicalClock:
        max_wall = max(self.wall_time_ms, remote_wall_ms, current_wall_ms)
        if max_wall == self.wall_time_ms == remote_wall_ms:
            self.lamport_counter = max(self.lamport_counter, remote_lamport) + 1
        elif max_wall == self.wall_time_ms:
            self.lamport_counter += 1
        elif max_wall == remote_wall_ms:
            self.wall_time_ms = remote_wall_ms
            self.lamport_counter = remote_lamport + 1
        else:
            self.wall_time_ms = current_wall_ms
            self.lamport_counter = 0
        return cast(HybridLogicalClock, self.model_copy())

    def format_hlc(self) -> str:
        return f"{self.wall_time_ms:013d}:{self.lamport_counter:04d}:{self.node_id}"


def compute_content_hash(record_id: str, operation: str, payload: dict[str, Any]) -> str:
    """Compute canonical SHA-256 content digest for payload integrity."""
    canonical = json.dumps(
        {"record_id": record_id, "operation": operation, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FieldObservationEnvelope(BaseModel):
    """Offline outbox envelope with HLC timestamp, idempotency key, and SHA-256 hash."""

    idempotency_key: str
    record_id: str
    node_id: str
    operation: Literal["UPSERT", "DELETE"] = "UPSERT"
    hlc_timestamp: str
    wall_time_ms: int
    lamport_counter: int
    payload: dict[str, Any]
    content_hash: str

    def comparison_tuple(self) -> tuple[int, int, str, str]:
        """Deterministic total ordering tuple for LWW-Element-Set tie-breaking."""
        return (self.wall_time_ms, self.lamport_counter, self.node_id, self.content_hash)

    def verify_integrity(self) -> bool:
        expected = compute_content_hash(self.record_id, self.operation, self.payload)
        return self.content_hash == expected


class OfflineOutbox:
    """Local store-and-forward queue on an intermittent 2G/3G field tablet."""

    def __init__(self, node_id: str, initial_wall_ms: int = 1730000000000) -> None:
        self.node_id = node_id
        self.clock = HybridLogicalClock(wall_time_ms=initial_wall_ms, lamport_counter=0, node_id=node_id)
        self._pending: list[FieldObservationEnvelope] = []
        self._acked_keys: set[str] = set()

    def enqueue(
        self,
        record_id: str,
        payload: dict[str, Any],
        operation: Literal["UPSERT", "DELETE"] = "UPSERT",
        wall_time_ms: int | None = None,
        idempotency_key: str | None = None,
    ) -> FieldObservationEnvelope:
        now_ms = wall_time_ms if wall_time_ms is not None else self.clock.wall_time_ms + 100
        hlc_state = self.clock.tick(now_ms)
        hlc_str = hlc_state.format_hlc()
        content_hash = compute_content_hash(record_id, operation, payload)
        idem_key = idempotency_key or f"{self.node_id}:{record_id}:{hlc_state.wall_time_ms}:{hlc_state.lamport_counter}"

        envelope = FieldObservationEnvelope(
            idempotency_key=idem_key,
            record_id=record_id,
            node_id=self.node_id,
            operation=operation,
            hlc_timestamp=hlc_str,
            wall_time_ms=hlc_state.wall_time_ms,
            lamport_counter=hlc_state.lamport_counter,
            payload=payload,
            content_hash=content_hash,
        )
        self._pending.append(envelope)
        return envelope

    def pending_batch(self) -> list[FieldObservationEnvelope]:
        return [env for env in self._pending if env.idempotency_key not in self._acked_keys]

    def mark_acknowledged(self, idempotency_keys: list[str]) -> int:
        before = len(self.pending_batch())
        self._acked_keys.update(idempotency_keys)
        after = len(self.pending_batch())
        return before - after


class ConflictResolutionEvent(BaseModel):
    record_id: str
    winner_node_id: str
    winner_hlc: str
    loser_node_id: str
    loser_hlc: str
    reason: str


class SyncReconciliationReport(BaseModel):
    total_envelopes_received: int
    accepted_new: int
    duplicate_idempotency_ignored: int
    integrity_failures: int
    conflicts_resolved: int
    active_records_count: int
    tombstoned_records_count: int
    conflict_log: list[ConflictResolutionEvent]
    active_state: dict[str, dict[str, Any]]
    acked_idempotency_keys: list[str]


class CentralSyncHub:
    """LWW-Element-Set CRDT Central Sync Hub for reconciling offline field tablets."""

    def __init__(self) -> None:
        self._add_set: dict[str, FieldObservationEnvelope] = {}
        self._remove_set: dict[str, FieldObservationEnvelope] = {}
        self._seen_idempotency_keys: set[str] = set()
        self._conflict_log: list[ConflictResolutionEvent] = []

    def ingest_batch(self, envelopes: list[FieldObservationEnvelope]) -> SyncReconciliationReport:
        accepted_new = 0
        duplicates = 0
        integrity_failures = 0
        conflicts_before = len(self._conflict_log)
        acked_keys: list[str] = []

        for env in envelopes:
            if not env.verify_integrity():
                integrity_failures += 1
                continue

            acked_keys.append(env.idempotency_key)
            if env.idempotency_key in self._seen_idempotency_keys:
                duplicates += 1
                continue

            self._seen_idempotency_keys.add(env.idempotency_key)
            accepted_new += 1
            self._apply_lww_element(env)

        active_state = self.materialized_view()
        tombstoned = self._count_tombstoned()

        return SyncReconciliationReport(
            total_envelopes_received=len(envelopes),
            accepted_new=accepted_new,
            duplicate_idempotency_ignored=duplicates,
            integrity_failures=integrity_failures,
            conflicts_resolved=len(self._conflict_log) - conflicts_before,
            active_records_count=len(active_state),
            tombstoned_records_count=tombstoned,
            conflict_log=list(self._conflict_log),
            active_state=active_state,
            acked_idempotency_keys=acked_keys,
        )

    def _apply_lww_element(self, incoming: FieldObservationEnvelope) -> None:
        rec_id = incoming.record_id
        target_set = self._add_set if incoming.operation == "UPSERT" else self._remove_set
        opposite_set = self._remove_set if incoming.operation == "UPSERT" else self._add_set

        existing_same = target_set.get(rec_id)
        existing_opp = opposite_set.get(rec_id)

        # Compare against existing record in the same set (add or remove)
        if existing_same is not None:
            if incoming.comparison_tuple() > existing_same.comparison_tuple():
                self._conflict_log.append(
                    ConflictResolutionEvent(
                        record_id=rec_id,
                        winner_node_id=incoming.node_id,
                        winner_hlc=incoming.hlc_timestamp,
                        loser_node_id=existing_same.node_id,
                        loser_hlc=existing_same.hlc_timestamp,
                        reason=f"LWW supersede on {incoming.operation}: higher (lamport, wall_ms, node_id) tuple",
                    )
                )
                target_set[rec_id] = incoming
            else:
                self._conflict_log.append(
                    ConflictResolutionEvent(
                        record_id=rec_id,
                        winner_node_id=existing_same.node_id,
                        winner_hlc=existing_same.hlc_timestamp,
                        loser_node_id=incoming.node_id,
                        loser_hlc=incoming.hlc_timestamp,
                        reason=f"Stale out-of-order {incoming.operation} rejected by LWW-Element-Set",
                    )
                )
        else:
            target_set[rec_id] = incoming
            if existing_opp is not None:
                if incoming.comparison_tuple() > existing_opp.comparison_tuple():
                    self._conflict_log.append(
                        ConflictResolutionEvent(
                            record_id=rec_id,
                            winner_node_id=incoming.node_id,
                            winner_hlc=incoming.hlc_timestamp,
                            loser_node_id=existing_opp.node_id,
                            loser_hlc=existing_opp.hlc_timestamp,
                            reason=f"Cross-set LWW resolution: {incoming.operation} overrode prior state",
                        )
                    )
                else:
                    self._conflict_log.append(
                        ConflictResolutionEvent(
                            record_id=rec_id,
                            winner_node_id=existing_opp.node_id,
                            winner_hlc=existing_opp.hlc_timestamp,
                            loser_node_id=incoming.node_id,
                            loser_hlc=incoming.hlc_timestamp,
                            reason=f"Cross-set LWW resolution: prior state retained over stale {incoming.operation}",
                        )
                    )

    def materialized_view(self) -> dict[str, dict[str, Any]]:
        """Return all live records where add_set timestamp > remove_set timestamp."""
        live: dict[str, dict[str, Any]] = {}
        for rec_id, add_env in sorted(self._add_set.items()):
            rem_env = self._remove_set.get(rec_id)
            if rem_env is None or add_env.comparison_tuple() >= rem_env.comparison_tuple():
                live[rec_id] = {
                    "record_id": rec_id,
                    "node_id": add_env.node_id,
                    "hlc_timestamp": add_env.hlc_timestamp,
                    "content_hash": add_env.content_hash[:16],
                    "payload": add_env.payload,
                }
        return live

    def _count_tombstoned(self) -> int:
        count = 0
        for rec_id, rem_env in self._remove_set.items():
            add_env = self._add_set.get(rec_id)
            if add_env is None or rem_env.comparison_tuple() > add_env.comparison_tuple():
                count += 1
        return count


def simulate_rural_sync_scenario() -> SyncReconciliationReport:
    """Simulate 20 offline field records across 3 rural devices with partitions & conflicts."""
    dev_masaka = OfflineOutbox("tablet-masaka-01", initial_wall_ms=1730010000000)
    dev_mbale = OfflineOutbox("tablet-mbale-02", initial_wall_ms=1730010000000)
    dev_gulu = OfflineOutbox("tablet-gulu-03", initial_wall_ms=1730010000000)

    envelopes: list[FieldObservationEnvelope] = []

    # 12 distinct plot observations across the 3 devices (4 each)
    for i in range(1, 5):
        envelopes.append(
            dev_masaka.enqueue(
                record_id=f"plot-lvc-{i:02d}",
                payload={"crop": "robusta_coffee", "soil_ph": 5.6 + (i * 0.1), "rain_14d_mm": 92 + i},
                wall_time_ms=1730010000000 + (i * 1000),
            )
        )
        envelopes.append(
            dev_mbale.enqueue(
                record_id=f"plot-wh-{i:02d}",
                payload={"crop": "matooke_banana", "soil_ph": 6.1, "rain_14d_mm": 105 + i},
                wall_time_ms=1730010000000 + (i * 1200),
            )
        )
        envelopes.append(
            dev_gulu.enqueue(
                record_id=f"plot-ns-{i:02d}",
                payload={"crop": "maize", "soil_ph": 5.9, "rain_14d_mm": 48 + (i * 5)},
                wall_time_ms=1730010000000 + (i * 1500),
            )
        )

    # Now create 8 conflicting / out-of-order / tombstone updates on shared co-op plots (total = 20 records)
    # Conflict 1: plot-shared-coop-01 updated by Masaka offline, then updated later by Mbale
    env_c1_early = dev_masaka.enqueue(
        record_id="plot-shared-coop-01",
        payload={"crop": "beans", "soil_ph": 5.4, "note": "Initial reading by Masaka agent"},
        wall_time_ms=1730020000000,
    )
    env_c1_late = dev_mbale.enqueue(
        record_id="plot-shared-coop-01",
        payload={"crop": "beans", "soil_ph": 6.0, "note": "Post-liming verified reading by Mbale agent"},
        wall_time_ms=1730050000000,
    )
    # Deliver out of order (late arrives before early!)
    envelopes.append(env_c1_late)
    envelopes.append(env_c1_early)

    # Conflict 2: plot-shared-coop-02 concurrent edit with identical wall clock & lamport, broken deterministically by node_id
    dev_masaka_tie = OfflineOutbox("tablet-masaka-01", initial_wall_ms=1730060000000)
    dev_gulu_tie = OfflineOutbox("tablet-gulu-03", initial_wall_ms=1730060000000)
    envelopes.append(
        dev_masaka_tie.enqueue(
            record_id="plot-shared-coop-02",
            payload={"crop": "cassava", "cmd_incidence_pct": 12},
            wall_time_ms=1730060000000,
        )
    )
    envelopes.append(
        dev_gulu_tie.enqueue(
            record_id="plot-shared-coop-02",
            payload={"crop": "cassava", "cmd_incidence_pct": 8},
            wall_time_ms=1730060000000,
        )
    )

    # Conflict 3: plot-shared-coop-03 created, then deleted (tombstoned) after duplicate plot merge
    envelopes.append(
        dev_gulu.enqueue(
            record_id="plot-shared-coop-03",
            payload={"crop": "groundnuts", "rain_14d_mm": 64},
            wall_time_ms=1730070000000,
        )
    )
    envelopes.append(
        dev_masaka.enqueue(
            record_id="plot-shared-coop-03",
            payload={"reason": "Merged duplicate plot registration"},
            operation="DELETE",
            wall_time_ms=1730080000000,
        )
    )

    # Conflict 4: plot-lvc-01 updated again by Masaka tablet after 48h offline
    envelopes.append(
        dev_masaka.enqueue(
            record_id="plot-lvc-01",
            payload={"crop": "robusta_coffee", "soil_ph": 6.2, "rain_14d_mm": 112, "mulched": True},
            wall_time_ms=1730090000000,
        )
    )

    # Record 20: Duplicate packet retry over flaky 2G connection (same idempotency key as env_c1_late)
    envelopes.append(env_c1_late)

    hub = CentralSyncHub()
    return hub.ingest_batch(envelopes)
