"""Command-Line Interface for AgriSignal Decision Support & Offline Sync."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

import uvicorn

from agrisignal.advisory.engine import (
    AdvisoryEngine,
    AdvisoryInput,
    AgroEcologicalZone,
    CropType,
    GrowthStage,
)
from agrisignal.advisory.pest_risk import PestRiskEngine, PestRiskInput
from agrisignal.sync.engine import simulate_rural_sync_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agrisignal",
        description="AgriSignal: Offline-First Smallholder Agricultural Decision Support CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # 1. advise subcommand
    adv = sub.add_parser("advise", help="Generate explainable crop & planting advisory")
    adv.add_argument(
        "--crop",
        type=str,
        default="maize",
        choices=[c.value for c in CropType],
        help="Target staple or cash crop",
    )
    adv.add_argument(
        "--zone",
        type=str,
        default="lake_victoria_crescent",
        choices=[z.value for z in AgroEcologicalZone],
        help="Agro-ecological zone",
    )
    adv.add_argument(
        "--stage",
        type=str,
        default="planting",
        choices=[s.value for s in GrowthStage],
        help="Crop phenological stage",
    )
    adv.add_argument(
        "--rain-14d",
        type=float,
        required=True,
        help="14-day cumulative rainfall in mm",
    )
    adv.add_argument("--soil-ph", type=float, default=None, help="Measured top-soil pH")
    adv.add_argument(
        "--moisture",
        type=float,
        default=None,
        help="Normalized volumetric soil moisture index (0.0-1.0)",
    )
    adv.add_argument(
        "--temp-anomaly",
        type=float,
        default=None,
        help="Temperature anomaly relative to seasonal baseline (deg C)",
    )
    adv.add_argument(
        "--lang",
        type=str,
        default="en",
        choices=["en", "lg", "sw"],
        help="Advisory language: English (en), Luganda (lg), or Swahili (sw)",
    )
    adv.add_argument("--json", action="store_true", help="Output raw JSON")

    # 2. simulate-sync subcommand
    sim = sub.add_parser(
        "simulate-sync",
        help="Simulate 20 offline field records across 3 rural tablets with LWW conflict resolution",
    )
    sim.add_argument("--json", action="store_true", help="Output raw JSON")

    # 3. pest-risk subcommand
    pest = sub.add_parser("pest-risk", help="Evaluate pest & disease early-warning risk matrix")
    pest.add_argument("--crop", type=str, default="maize", choices=[c.value for c in CropType])
    pest.add_argument(
        "--zone",
        type=str,
        default="lake_victoria_crescent",
        choices=[z.value for z in AgroEcologicalZone],
    )
    pest.add_argument("--rain-14d", type=float, default=75.0)
    pest.add_argument("--temp-anomaly", type=float, default=1.5)
    pest.add_argument("--rh", type=float, default=76.0)
    pest.add_argument("--dry-days", type=int, default=5)
    pest.add_argument("--json", action="store_true", help="Output raw JSON")

    # 4. serve subcommand
    srv = sub.add_parser("serve", help="Start FastAPI server and low-bandwidth web workbench")
    srv.add_argument("--host", type=str, default="127.0.0.1", help="Bind host")
    srv.add_argument("--port", type=int, default=8099, help="Bind port (default 8099)")

    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "advise":
        engine = AdvisoryEngine()
        res = engine.evaluate(
            AdvisoryInput(
                crop=CropType(args.crop),
                zone=AgroEcologicalZone(args.zone),
                growth_stage=GrowthStage(args.stage),
                rain_14d_mm=args.rain_14d,
                soil_ph=args.soil_ph,
                soil_moisture_index=args.moisture,
                temp_anomaly_c=args.temp_anomaly,
                lang=args.lang,
            )
        )
        if args.json:
            print(json.dumps(res.model_dump(), indent=2))
        else:
            print("=" * 74)
            print(f"AGRISIGNAL EXPLAINABLE ADVISORY: {res.headline}")
            print("=" * 74)
            print(f"Localized Summary ({args.lang}): {res.localized_summary}")
            print(f"SMS 160-Char ({len(res.sms_160)}/160): {res.sms_160}")
            print("-" * 74)
            print("Recommendations:")
            for rec in res.recommendations:
                print(f"  * {rec}")
            print("Uncertainty & Confidence Bounds:")
            print(
                f"  * Point Confidence: {res.uncertainty.point_confidence:.2f} "
                f"(90% Interval: {res.uncertainty.confidence_interval[0]:.2f} - {res.uncertainty.confidence_interval[1]:.2f})"
            )
            print(f"  * Data Completeness Score: {res.uncertainty.data_completeness_score:.2f}")
            for warn in res.uncertainty.missing_sensor_warnings:
                print(f"  ! Warning: {warn}")
            print(f"  * Epistemic Disclaimer: {res.uncertainty.epistemic_disclaimer}")
        return 0

    if args.command == "simulate-sync":
        report = simulate_rural_sync_scenario()
        if args.json:
            print(json.dumps(report.model_dump(), indent=2))
        else:
            print("=" * 74)
            print("AGRISIGNAL OFFLINE-FIRST LWW-ELEMENT-SET SYNC SIMULATION (3 TABLETS)")
            print("=" * 74)
            print(f"Total Envelopes Received      : {report.total_envelopes_received}")
            print(f"Accepted Unique Envelopes     : {report.accepted_new}")
            print(f"Duplicate Retries Ignored     : {report.duplicate_idempotency_ignored}")
            print(f"SHA-256 Integrity Failures    : {report.integrity_failures}")
            print(f"Deterministic LWW Conflicts   : {report.conflicts_resolved}")
            print(f"Live Reconciled Plot Records  : {report.active_records_count}")
            print(f"Tombstoned (Deleted) Plots    : {report.tombstoned_records_count}")
            print("-" * 74)
            print("Conflict Resolution Log:")
            for evt in report.conflict_log:
                print(
                    f"  * [{evt.record_id}] WINNER={evt.winner_node_id} ({evt.winner_hlc}) "
                    f"over LOSER={evt.loser_node_id} ({evt.loser_hlc}) -> {evt.reason}"
                )
        return 0

    if args.command == "pest-risk":
        pest_engine = PestRiskEngine()
        report = pest_engine.evaluate(
            PestRiskInput(
                crop=CropType(args.crop),
                zone=AgroEcologicalZone(args.zone),
                rain_14d_mm=args.rain_14d,
                temp_anomaly_c=args.temp_anomaly,
                relative_humidity_pct=args.rh,
                dry_spell_days=args.dry_days,
            )
        )
        if args.json:
            print(json.dumps(report.model_dump(), indent=2))
        else:
            print(f"OVERALL PEST RISK [{report.crop} @ {report.zone}]: {report.overall_risk_level}")
            for t in report.threats:
                print(f"  - {t.common_name} ({t.scientific_name}): {t.risk_level} (score={t.risk_score})")
                print(f"    Escalation: {t.extension_escalation_threshold}")
        return 0

    if args.command == "serve":
        uvicorn.run("agrisignal.server.app:app", host=args.host, port=args.port, reload=False)
        return 0

    return 1


def main() -> None:
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
