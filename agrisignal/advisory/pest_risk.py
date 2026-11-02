"""Pest & Disease Early-Warning Risk Matrix with Non-Chemical IPM Guidance."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agrisignal.advisory.engine import AgroEcologicalZone, CropType


class PestRiskInput(BaseModel):
    crop: CropType
    zone: AgroEcologicalZone
    rain_14d_mm: float = Field(..., ge=0.0, le=600.0)
    temp_anomaly_c: float = Field(default=0.0, ge=-8.0, le=10.0)
    relative_humidity_pct: float = Field(default=72.0, ge=10.0, le=100.0)
    dry_spell_days: int = Field(default=3, ge=0, le=60)


class PestThreatAssessment(BaseModel):
    threat_id: str
    common_name: str
    scientific_name: str
    risk_level: Literal["LOW", "MODERATE", "HIGH", "SEVERE"]
    risk_score: float = Field(..., ge=0.0, le=1.0)
    environmental_triggers: list[str]
    scouting_indicators: list[str]
    ipm_non_chemical_actions: list[str]
    extension_escalation_threshold: str


class PestRiskReport(BaseModel):
    crop: str
    zone: str
    overall_risk_level: Literal["LOW", "MODERATE", "HIGH", "SEVERE"]
    threats: list[PestThreatAssessment]
    biosafety_note: str


class PestRiskEngine:
    """Evaluates agro-climatic preconditions for major East African crop pests and diseases."""

    BIOSAFETY_NOTE = (
        "AgriSignal prioritizes cultural, mechanical, and biological Integrated Pest Management (IPM). "
        "Never apply synthetic pesticides without diagnostic confirmation from a certified District "
        "Agricultural Extension Officer."
    )

    def evaluate(self, payload: PestRiskInput) -> PestRiskReport:
        threats: list[PestThreatAssessment] = []

        # 1. Fall Armyworm (Spodoptera frugiperda) - Primarily Maize, also Sorghum/intercrops
        if payload.crop in (CropType.MAIZE, CropType.BEANS, CropType.GROUNDNUTS):
            faw_score = 0.25
            triggers: list[str] = []
            if payload.dry_spell_days >= 5 and payload.temp_anomaly_c >= 1.0:
                faw_score += 0.45
                triggers.append(
                    f"Warm dry spell ({payload.dry_spell_days}d dry, +{payload.temp_anomaly_c:.1f}C anomaly) accelerates moth oviposition and larval survival."
                )
            elif payload.temp_anomaly_c >= 0.5:
                faw_score += 0.25
                triggers.append(f"Mild warm anomaly (+{payload.temp_anomaly_c:.1f}C) favors larval feeding.")

            if 30.0 <= payload.rain_14d_mm <= 90.0:
                faw_score += 0.15
                triggers.append("Intermittent showers fail to wash early-instar larvae from maize whorls.")
            elif payload.rain_14d_mm > 130.0:
                faw_score = max(0.15, faw_score - 0.15)
                triggers.append("Heavy rainfall (>130mm) naturally drowns young larvae inside funnel whorls.")

            if not triggers:
                triggers.append("Baseline endemic monitoring condition.")

            faw_score = round(min(0.95, faw_score), 2)
            threats.append(
                PestThreatAssessment(
                    threat_id="fall_armyworm",
                    common_name="Fall Armyworm (FAW)",
                    scientific_name="Spodoptera frugiperda",
                    risk_level=self._score_to_level(faw_score),
                    risk_score=faw_score,
                    environmental_triggers=triggers,
                    scouting_indicators=[
                        "Inspect 20 consecutive plants in a W-pattern twice weekly during vegetative stages.",
                        "Look for papery 'windowpane' leaf feeding, moist sawdust-like frass in the funnel, and inverted Y-mark on larval head capsule.",
                    ],
                    ipm_non_chemical_actions=[
                        "Establish Desmodium-Brachiaria 'Push-Pull' companion intercropping.",
                        "Hand-crush egg masses and apply wood ash or fine dry soil into infested maize whorls at early instar stages.",
                        "Conserve natural parasitoids (Telenomus remus, Cotesia icipe) by avoiding broad-spectrum sprays.",
                    ],
                    extension_escalation_threshold=(
                        "Escalate to Sub-County Extension Officer if >20% of early whorl plants (or >40% late whorl) show fresh windowpane damage."
                    ),
                )
            )

        # 2. Coffee Berry Borer & Coffee Wilt Complex
        if payload.crop == CropType.ROBUSTA_COFFEE:
            cbb_score = 0.30
            triggers = []
            if payload.temp_anomaly_c >= 1.2:
                cbb_score += 0.35
                triggers.append(
                    f"Elevated temperature anomaly (+{payload.temp_anomaly_c:.1f}C) shortens Coffee Berry Borer reproductive cycle."
                )
            if payload.relative_humidity_pct >= 75.0:
                cbb_score += 0.20
                triggers.append(
                    f"High relative humidity ({payload.relative_humidity_pct:.0f}%) facilitates fungal spore dispersal (Fusarium/Gibberella xylarioides) and borer emergence."
                )
            if not triggers:
                triggers.append("Standard perennial plantation sanitation vigilance required.")

            cbb_score = round(min(0.95, cbb_score), 2)
            threats.append(
                PestThreatAssessment(
                    threat_id="coffee_wilt_and_berry_borer",
                    common_name="Coffee Berry Borer & Coffee Wilt Disease (CWD)",
                    scientific_name="Hypothenemus hampei / Gibberella xylarioides",
                    risk_level=self._score_to_level(cbb_score),
                    risk_score=cbb_score,
                    environmental_triggers=triggers,
                    scouting_indicators=[
                        "Pin-sized entry holes at the tip (disc) of green and ripening coffee cherries.",
                        "Unilateral yellowing, wilting, and blue-black staining under the bark (Coffee Wilt indicator).",
                    ],
                    ipm_non_chemical_actions=[
                        "Practice strict phytosanitary strip-picking (remove all residual over-ripe/fallen berries on ground mats after harvest).",
                        "Sterilize pruning secateurs and machetes with methylated spirit or fire between trees to prevent CWD transmission.",
                        "Deploy alcohol-baited (methanol:ethanol 1:1) bottle traps during post-rain flight peaks.",
                    ],
                    extension_escalation_threshold=(
                        "Escalate to UCDA / District Coffee Officer if >5% of sampled cherries show borer perforation or if any tree exhibits vascular bark staining."
                    ),
                )
            )

        # 3. Cassava Mosaic (CMD) & Cassava Brown Streak Disease (CBSD) Vector Risk
        if payload.crop == CropType.CASSAVA:
            cmd_score = 0.25
            triggers = []
            if payload.temp_anomaly_c >= 1.0 and payload.dry_spell_days >= 4:
                cmd_score += 0.45
                triggers.append(
                    f"Warm dry spells (+{payload.temp_anomaly_c:.1f}C, {payload.dry_spell_days}d dry) trigger rapid silverleaf whitefly (Bemisia tabaci) vector proliferation."
                )
            elif payload.rain_14d_mm < 50.0:
                cmd_score += 0.25
                triggers.append("Low rainfall favors whitefly colonization on young apical cassava shoots.")
            else:
                triggers.append("Vegetative propagation pathway remains primary viral risk vector.")

            cmd_score = round(min(0.95, cmd_score), 2)
            threats.append(
                PestThreatAssessment(
                    threat_id="cassava_mosaic_brown_streak",
                    common_name="Cassava Mosaic (CMD) & Brown Streak (CBSD)",
                    scientific_name="Begomovirus / Ipomovirus (Vector: Bemisia tabaci)",
                    risk_level=self._score_to_level(cmd_score),
                    risk_score=cmd_score,
                    environmental_triggers=triggers,
                    scouting_indicators=[
                        "Chlorotic yellow-green mosaic leaf distortion and stunted leaflet curling on young shoots (CMD).",
                        "Feathery yellow vein banding on lower mature leaves and brown corky necrosis in storage roots (CBSD).",
                    ],
                    ipm_non_chemical_actions=[
                        "Plant only certified clean stem cuttings from NARO/district-inspected disease-free multiplication blocks (e.g., NAROCASS varieties).",
                        "Rogue (uproot and bury/destroy) visibly symptomatic plants within the first 4-8 weeks after sprouting.",
                        "Maintain 100m isolation buffer from older infected cassava plots when establishing new fields.",
                    ],
                    extension_escalation_threshold=(
                        "Escalate to Extension Officer if >10% of young plants show mosaic distortion or if root necrosis is found at harvest."
                    ),
                )
            )

        # 4. Bean Anthracnose (Colletotrichum lindemuthianum) - Beans & Legume Intercrops
        if payload.crop in (CropType.BEANS, CropType.MAIZE, CropType.GROUNDNUTS):
            anth_score = 0.20
            triggers = []
            if payload.rain_14d_mm >= 95.0 and payload.relative_humidity_pct >= 78.0:
                anth_score += 0.55
                triggers.append(
                    f"Cool/wet splash conditions (rain_14d={payload.rain_14d_mm}mm, RH={payload.relative_humidity_pct:.0f}%) strongly promote fungal conidia splash dispersal."
                )
            elif payload.rain_14d_mm >= 70.0:
                anth_score += 0.30
                triggers.append("Frequent rain splash increases foliar fungal transmission risk.")
            else:
                triggers.append("Low rain-splash pressure; seed-borne inoculum remains primary baseline risk.")

            anth_score = round(min(0.95, anth_score), 2)
            threats.append(
                PestThreatAssessment(
                    threat_id="bean_anthracnose",
                    common_name="Bean Anthracnose & Fungal Leaf Spot",
                    scientific_name="Colletotrichum lindemuthianum",
                    risk_level=self._score_to_level(anth_score),
                    risk_score=anth_score,
                    environmental_triggers=triggers,
                    scouting_indicators=[
                        "Dark brick-red to black sunken lesions along undersides of leaf veins and stems.",
                        "Circular sunken cankers with pink-orange spore masses on developing bean pods.",
                    ],
                    ipm_non_chemical_actions=[
                        "Never walk through or weed bean plots while foliage is wet with morning dew or rain (prevents mechanical spore spread).",
                        "Practice 2-to-3 season crop rotation with non-host cereals (maize, sorghum) or tubers.",
                        "Select clean, unblemished seed from healthy mother pods and incorporate crop residue deeply after harvest.",
                    ],
                    extension_escalation_threshold=(
                        "Escalate to Extension Officer if sunken pod lesions appear across >15% of flowering/podding stands."
                    ),
                )
            )

        # 5. Matooke Banana Bacterial Wilt (BXW) & Weevil Complex
        if payload.crop == CropType.MATOOKE_BANANA:
            bxw_score = 0.30
            triggers = []
            if payload.rain_14d_mm >= 85.0 and payload.relative_humidity_pct >= 75.0:
                bxw_score += 0.40
                triggers.append(
                    "Humid flowering conditions increase insect-vectored bacterial ooze transmission via male buds."
                )
            else:
                triggers.append("Continuous tool-mediated and insect-floral transmission vigilance required.")

            bxw_score = round(min(0.95, bxw_score), 2)
            threats.append(
                PestThreatAssessment(
                    threat_id="banana_bacterial_wilt",
                    common_name="Banana Xanthomonas Wilt (BXW)",
                    scientific_name="Xanthomonas campestris pv. musacearum",
                    risk_level=self._score_to_level(bxw_score),
                    risk_score=bxw_score,
                    environmental_triggers=triggers,
                    scouting_indicators=[
                        "Progressive yellowing and wilting of leaves; premature ripening and internal rusty-brown staining of fingers.",
                        "Yellow bacterial ooze exuding within 15 minutes of cutting the pseudostem.",
                    ],
                    ipm_non_chemical_actions=[
                        "Break off the male bud using a forked wooden stick (not a knife) immediately after the last female hand forms.",
                        "Flame-sterilize or JIK-disinfect cutting knives between every single mat.",
                    ],
                    extension_escalation_threshold=(
                        "Report immediately to Community BXW Taskforce or Extension Officer upon observing a single oozing pseudostem."
                    ),
                )
            )

        highest_score = max((t.risk_score for t in threats), default=0.2)
        overall_level = self._score_to_level(highest_score)

        return PestRiskReport(
            crop=payload.crop.value,
            zone=payload.zone.value,
            overall_risk_level=overall_level,
            threats=threats,
            biosafety_note=self.BIOSAFETY_NOTE,
        )

    @staticmethod
    def _score_to_level(score: float) -> Literal["LOW", "MODERATE", "HIGH", "SEVERE"]:
        if score >= 0.75:
            return "SEVERE"
        if score >= 0.55:
            return "HIGH"
        if score >= 0.35:
            return "MODERATE"
        return "LOW"
