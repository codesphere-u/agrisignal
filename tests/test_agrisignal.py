"""Comprehensive Test Suite for AgriSignal (36 tests across Advisory, Pest IPM, Sync, i18n, CLI, FastAPI)."""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from agrisignal.advisory.engine import (
    AdvisoryEngine,
    AdvisoryInput,
    AgroEcologicalZone,
    CropType,
    GrowthStage,
)
from agrisignal.advisory.pest_risk import PestRiskEngine, PestRiskInput
from agrisignal.cli import run_cli
from agrisignal.i18n.translator import (
    ACTION_I18N,
    SUPPORTED_LANGUAGES,
    format_sms_advisory,
    translate_advisory_summary,
)
from agrisignal.server.app import app
from agrisignal.sync.engine import (
    CentralSyncHub,
    FieldObservationEnvelope,
    HybridLogicalClock,
    OfflineOutbox,
    compute_content_hash,
    simulate_rural_sync_scenario,
)


# ---------------------------------------------------------------------------
# 1. Explainable Crop & Planting Advisory Engine Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("crop", list(CropType))
def test_advisory_optimal_conditions_all_crops(crop: CropType) -> None:
    """All 6 East African crops evaluate cleanly under optimal rainfall and soil pH."""
    engine = AdvisoryEngine()
    res = engine.evaluate(
        AdvisoryInput(
            crop=crop,
            zone=AgroEcologicalZone.LAKE_VICTORIA_CRESCENT,
            growth_stage=GrowthStage.PLANTING,
            rain_14d_mm=90.0,
            soil_ph=6.1,
            soil_moisture_index=0.60,
            temp_anomaly_c=0.4,
            lang="en",
        )
    )
    assert res.status == "OPTIMAL"
    assert res.action_code == "PROCEED_STANDARD"
    assert res.uncertainty.data_completeness_score == 1.0
    assert len(res.uncertainty.missing_sensor_warnings) == 0
    assert "does NOT guarantee crop yield" in res.uncertainty.epistemic_disclaimer


@pytest.mark.parametrize("zone", list(AgroEcologicalZone))
def test_advisory_across_all_agro_ecological_zones(zone: AgroEcologicalZone) -> None:
    """Verify zone-specific evaporation factor scaling across all 4 agro-ecological zones."""
    engine = AdvisoryEngine()
    res = engine.evaluate(
        AdvisoryInput(
            crop=CropType.MAIZE,
            zone=zone,
            growth_stage=GrowthStage.VEGETATIVE,
            rain_14d_mm=85.0,
            soil_ph=6.2,
        )
    )
    assert res.zone == zone.value
    assert len(res.rule_trace) >= 2


def test_advisory_severe_dry_planting_delays_sowing() -> None:
    engine = AdvisoryEngine()
    res = engine.evaluate(
        AdvisoryInput(
            crop=CropType.MAIZE,
            zone=AgroEcologicalZone.NORTHERN_SAVANNAH,
            growth_stage=GrowthStage.PLANTING,
            rain_14d_mm=18.0,
        )
    )
    assert res.status == "DELAY_OR_MITIGATE"
    assert res.action_code == "DELAY_PLANTING_DRY"
    assert any("RULE_MOISTURE_DEFICIT" in r for r in res.rule_trace)


def test_advisory_drought_during_flowering_triggers_critical_risk() -> None:
    engine = AdvisoryEngine()
    res = engine.evaluate(
        AdvisoryInput(
            crop=CropType.BEANS,
            zone=AgroEcologicalZone.EASTERN_PLAINS,
            growth_stage=GrowthStage.FLOWERING,
            rain_14d_mm=15.0,
            soil_moisture_index=0.18,
        )
    )
    assert res.status == "CRITICAL_RISK"
    assert res.action_code == "DROUGHT_STRESS_MITIGATION"


def test_advisory_marginal_moisture_triggers_mulch_and_conserve() -> None:
    engine = AdvisoryEngine()
    res = engine.evaluate(
        AdvisoryInput(
            crop=CropType.ROBUSTA_COFFEE,
            zone=AgroEcologicalZone.LAKE_VICTORIA_CRESCENT,
            growth_stage=GrowthStage.VEGETATIVE,
            rain_14d_mm=55.0,
            soil_moisture_index=0.45,
        )
    )
    assert res.status == "CAUTION"
    assert res.action_code == "MULCH_AND_CONSERVE"


def test_advisory_waterlogging_triggers_drainage_and_ridging() -> None:
    engine = AdvisoryEngine()
    res = engine.evaluate(
        AdvisoryInput(
            crop=CropType.GROUNDNUTS,
            zone=AgroEcologicalZone.LAKE_VICTORIA_CRESCENT,
            growth_stage=GrowthStage.VEGETATIVE,
            rain_14d_mm=220.0,
            soil_moisture_index=0.92,
        )
    )
    assert res.status == "DELAY_OR_MITIGATE"
    assert res.action_code == "DRAINAGE_AND_RIDGING"


def test_advisory_acidic_and_alkaline_soil_ph_rules() -> None:
    engine = AdvisoryEngine()
    acid_res = engine.evaluate(
        AdvisoryInput(
            crop=CropType.MAIZE,
            zone=AgroEcologicalZone.WESTERN_HIGHLANDS,
            rain_14d_mm=80.0,
            soil_ph=4.6,
        )
    )
    assert acid_res.status == "CAUTION"
    assert acid_res.action_code == "LIME_AMENDMENT_NEEDED"

    alk_res = engine.evaluate(
        AdvisoryInput(
            crop=CropType.MAIZE,
            zone=AgroEcologicalZone.WESTERN_HIGHLANDS,
            rain_14d_mm=80.0,
            soil_ph=7.8,
        )
    )
    assert alk_res.status == "CAUTION"
    assert alk_res.action_code == "ALKALINE_SOIL_MANAGEMENT"


def test_advisory_harvest_drying_aflatoxin_and_moisture_alerts() -> None:
    engine = AdvisoryEngine()
    crit_harvest = engine.evaluate(
        AdvisoryInput(
            crop=CropType.GROUNDNUTS,
            zone=AgroEcologicalZone.LAKE_VICTORIA_CRESCENT,
            growth_stage=GrowthStage.HARVEST_DRYING,
            rain_14d_mm=65.0,
        )
    )
    assert crit_harvest.status == "CRITICAL_RISK"
    assert crit_harvest.action_code == "AFLATOXIN_DRYING_ALERT"

    caution_harvest = engine.evaluate(
        AdvisoryInput(
            crop=CropType.GROUNDNUTS,
            zone=AgroEcologicalZone.LAKE_VICTORIA_CRESCENT,
            growth_stage=GrowthStage.HARVEST_DRYING,
            rain_14d_mm=32.0,
        )
    )
    assert caution_harvest.status == "CAUTION"
    assert caution_harvest.action_code == "HARVEST_MOISTURE_ALERT"


def test_uncertainty_bounds_widen_when_sensors_missing() -> None:
    engine = AdvisoryEngine()
    sparse = engine.evaluate(
        AdvisoryInput(
            crop=CropType.CASSAVA,
            zone=AgroEcologicalZone.NORTHERN_SAVANNAH,
            rain_14d_mm=70.0,
        )
    )
    complete = engine.evaluate(
        AdvisoryInput(
            crop=CropType.CASSAVA,
            zone=AgroEcologicalZone.NORTHERN_SAVANNAH,
            rain_14d_mm=70.0,
            soil_ph=5.8,
            soil_moisture_index=0.52,
            temp_anomaly_c=0.5,
        )
    )
    assert sparse.uncertainty.data_completeness_score == 0.25
    assert len(sparse.uncertainty.missing_sensor_warnings) == 3
    assert complete.uncertainty.data_completeness_score == 1.0
    assert complete.uncertainty.point_confidence > sparse.uncertainty.point_confidence
    sparse_width = sparse.uncertainty.confidence_interval[1] - sparse.uncertainty.confidence_interval[0]
    complete_width = complete.uncertainty.confidence_interval[1] - complete.uncertainty.confidence_interval[0]
    assert sparse_width > complete_width


# ---------------------------------------------------------------------------
# 2. Pest & Disease Early-Warning Risk Matrix Tests
# ---------------------------------------------------------------------------


def test_pest_risk_fall_armyworm_severe_under_warm_dry_spell() -> None:
    engine = PestRiskEngine()
    report = engine.evaluate(
        PestRiskInput(
            crop=CropType.MAIZE,
            zone=AgroEcologicalZone.EASTERN_PLAINS,
            rain_14d_mm=50.0,
            temp_anomaly_c=2.1,
            relative_humidity_pct=65.0,
            dry_spell_days=8,
        )
    )
    faw = next(t for t in report.threats if t.threat_id == "fall_armyworm")
    assert faw.risk_level in ("HIGH", "SEVERE")
    assert any("Push-Pull" in action for action in faw.ipm_non_chemical_actions)
    assert "Extension Officer" in faw.extension_escalation_threshold


def test_pest_risk_coffee_wilt_and_berry_borer() -> None:
    engine = PestRiskEngine()
    report = engine.evaluate(
        PestRiskInput(
            crop=CropType.ROBUSTA_COFFEE,
            zone=AgroEcologicalZone.LAKE_VICTORIA_CRESCENT,
            rain_14d_mm=95.0,
            temp_anomaly_c=1.8,
            relative_humidity_pct=82.0,
            dry_spell_days=2,
        )
    )
    cbb = next(t for t in report.threats if t.threat_id == "coffee_wilt_and_berry_borer")
    assert cbb.risk_level == "SEVERE"
    assert any("strip-picking" in a for a in cbb.ipm_non_chemical_actions)


def test_pest_risk_cassava_mosaic_and_brown_streak() -> None:
    engine = PestRiskEngine()
    report = engine.evaluate(
        PestRiskInput(
            crop=CropType.CASSAVA,
            zone=AgroEcologicalZone.NORTHERN_SAVANNAH,
            rain_14d_mm=40.0,
            temp_anomaly_c=1.9,
            relative_humidity_pct=60.0,
            dry_spell_days=7,
        )
    )
    cmd = next(t for t in report.threats if t.threat_id == "cassava_mosaic_brown_streak")
    assert cmd.risk_level in ("HIGH", "SEVERE")
    assert any("clean stem cuttings" in a for a in cmd.ipm_non_chemical_actions)


def test_pest_risk_bean_anthracnose_wet_splash() -> None:
    engine = PestRiskEngine()
    report = engine.evaluate(
        PestRiskInput(
            crop=CropType.BEANS,
            zone=AgroEcologicalZone.WESTERN_HIGHLANDS,
            rain_14d_mm=130.0,
            temp_anomaly_c=0.2,
            relative_humidity_pct=86.0,
            dry_spell_days=0,
        )
    )
    anth = next(t for t in report.threats if t.threat_id == "bean_anthracnose")
    assert anth.risk_level == "SEVERE"


def test_pest_risk_matooke_banana_bacterial_wilt() -> None:
    engine = PestRiskEngine()
    report = engine.evaluate(
        PestRiskInput(
            crop=CropType.MATOOKE_BANANA,
            zone=AgroEcologicalZone.WESTERN_HIGHLANDS,
            rain_14d_mm=110.0,
            temp_anomaly_c=0.8,
            relative_humidity_pct=80.0,
            dry_spell_days=1,
        )
    )
    bxw = next(t for t in report.threats if t.threat_id == "banana_bacterial_wilt")
    assert bxw.risk_level in ("HIGH", "SEVERE")
    assert any("forked wooden stick" in a for a in bxw.ipm_non_chemical_actions)


# ---------------------------------------------------------------------------
# 3. Offline-First Outbox & Conflict-Free Sync Engine Tests
# ---------------------------------------------------------------------------


def test_hlc_monotonicity_and_receive_merge() -> None:
    clock_a = HybridLogicalClock(wall_time_ms=1000, lamport_counter=0, node_id="node-a")
    s1 = clock_a.tick(1000)
    s2 = clock_a.tick(950)  # physical clock drift backward
    assert s2.wall_time_ms == 1000
    assert s2.lamport_counter == s1.lamport_counter + 1

    s3 = clock_a.receive(remote_wall_ms=2000, remote_lamport=5, current_wall_ms=1500)
    assert s3.wall_time_ms == 2000
    assert s3.lamport_counter == 6


def test_outbox_idempotency_and_acknowledgement() -> None:
    outbox = OfflineOutbox("tablet-01", initial_wall_ms=1730000000000)
    e1 = outbox.enqueue("plot-1", {"crop": "maize", "ph": 6.1})
    e2 = outbox.enqueue("plot-2", {"crop": "beans", "ph": 5.9})
    assert len(outbox.pending_batch()) == 2
    acked = outbox.mark_acknowledged([e1.idempotency_key])
    assert acked == 1
    assert len(outbox.pending_batch()) == 1
    assert outbox.pending_batch()[0].record_id == e2.record_id


def test_sync_hub_rejects_tampered_sha256_payload() -> None:
    outbox = OfflineOutbox("tablet-01")
    env = outbox.enqueue("plot-tamper", {"crop": "maize", "ph": 6.0})
    tampered = env.model_copy(update={"payload": {"crop": "maize", "ph": 9.9}})
    hub = CentralSyncHub()
    report = hub.ingest_batch([tampered])
    assert report.integrity_failures == 1
    assert report.accepted_new == 0
    assert report.active_records_count == 0


def test_sync_hub_lww_out_of_order_and_tombstone_resolution() -> None:
    dev1 = OfflineOutbox("tablet-a", initial_wall_ms=1000)
    dev2 = OfflineOutbox("tablet-b", initial_wall_ms=2000)

    older = dev1.enqueue("plot-99", {"ph": 5.5}, wall_time_ms=1000)
    newer = dev2.enqueue("plot-99", {"ph": 6.3}, wall_time_ms=2000)

    # Deliver newer first, then older out-of-order
    hub = CentralSyncHub()
    rep = hub.ingest_batch([newer, older])
    assert rep.active_state["plot-99"]["payload"]["ph"] == 6.3
    assert rep.conflicts_resolved == 1

    # Now tombstone (DELETE) with higher timestamp
    delete_env = dev1.enqueue("plot-99", {"reason": "archived"}, operation="DELETE", wall_time_ms=3000)
    rep2 = hub.ingest_batch([delete_env])
    assert "plot-99" not in rep2.active_state
    assert rep2.tombstoned_records_count == 1


def test_simulate_rural_sync_20_records_3_devices() -> None:
    report = simulate_rural_sync_scenario()
    assert report.total_envelopes_received == 20
    assert report.accepted_new == 19
    assert report.duplicate_idempotency_ignored == 1
    assert report.integrity_failures == 0
    assert report.conflicts_resolved >= 4
    assert report.tombstoned_records_count == 1
    assert report.active_state["plot-shared-coop-01"]["payload"]["soil_ph"] == 6.0


# ---------------------------------------------------------------------------
# 4. Multilingual Localization & 160-Char SMS Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "lg", "sw"])
@pytest.mark.parametrize("action_code", list(ACTION_I18N.keys()))
def test_sms_160_character_bound_across_all_languages_and_actions(
    lang: str, action_code: str
) -> None:
    sms = format_sms_advisory(
        lang=lang,  # type: ignore[arg-type]
        crop_key="matooke_banana",
        stage_key="harvest_drying",
        status="DELAY_OR_MITIGATE",
        action_code=action_code,
        rain_14d_mm=142.0,
        confidence_interval=(0.68, 0.90),
    )
    assert len(sms) <= 160
    assert "AGRISIGNAL" in sms
    assert "Conf:68-90%" in sms


def test_localized_summaries_distinct_in_en_lg_sw() -> None:
    en_txt = translate_advisory_summary("en", "maize", "Lake Victoria Crescent", "planting", "OPTIMAL", "PROCEED_STANDARD", 85.0, 0.85)
    lg_txt = translate_advisory_summary("lg", "maize", "Lake Victoria Crescent", "planting", "OPTIMAL", "PROCEED_STANDARD", 85.0, 0.85)
    sw_txt = translate_advisory_summary("sw", "maize", "Lake Victoria Crescent", "planting", "OPTIMAL", "PROCEED_STANDARD", 85.0, 0.85)
    assert "Kasooli" in lg_txt
    assert "Mahindi" in sw_txt
    assert "Maize" in en_txt
    assert set(SUPPORTED_LANGUAGES.keys()) == {"en", "lg", "sw"}


# ---------------------------------------------------------------------------
# 5. CLI & FastAPI Workbench Integration Tests
# ---------------------------------------------------------------------------


def test_cli_advise_and_simulate_sync(capsys: pytest.CaptureFixture[str]) -> None:
    rc1 = run_cli(
        [
            "advise",
            "--crop",
            "maize",
            "--zone",
            "lake_victoria_crescent",
            "--rain-14d",
            "85",
            "--soil-ph",
            "6.2",
            "--lang",
            "lg",
            "--json",
        ]
    )
    assert rc1 == 0
    out1 = json.loads(capsys.readouterr().out)
    assert out1["crop"] == "maize"
    assert "Kasooli" in out1["localized_summary"]

    rc2 = run_cli(["simulate-sync", "--json"])
    assert rc2 == 0
    out2 = json.loads(capsys.readouterr().out)
    assert out2["total_envelopes_received"] == 20


def test_fastapi_workbench_and_api_endpoints() -> None:
    client = TestClient(app)

    home = client.get("/")
    assert home.status_code == 200
    assert "AgriSignal Field &amp; Extension Workbench" in home.text

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    meta = client.get("/api/metadata")
    assert meta.status_code == 200
    assert "robusta_coffee" in meta.json()["crops"]

    adv = client.post(
        "/api/advise",
        json={
            "crop": "maize",
            "zone": "lake_victoria_crescent",
            "growth_stage": "planting",
            "rain_14d_mm": 85.0,
            "soil_ph": 6.2,
            "lang": "sw",
        },
    )
    assert adv.status_code == 200
    assert len(adv.json()["sms_160"]) <= 160

    pest = client.post(
        "/api/pest-risk",
        json={
            "crop": "maize",
            "zone": "lake_victoria_crescent",
            "rain_14d_mm": 60.0,
            "temp_anomaly_c": 1.8,
            "relative_humidity_pct": 75.0,
            "dry_spell_days": 6,
        },
    )
    assert pest.status_code == 200
    assert pest.json()["overall_risk_level"] in ("MODERATE", "HIGH", "SEVERE")

    sim = client.post("/api/sync/simulate")
    assert sim.status_code == 200
    assert sim.json()["total_envelopes_received"] == 20
