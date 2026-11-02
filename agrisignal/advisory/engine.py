"""Explainable Crop & Planting Advisory Engine with Uncertainty Bounds."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from agrisignal.i18n.translator import format_sms_advisory, translate_advisory_summary


class CropType(str, Enum):
    MAIZE = "maize"
    ROBUSTA_COFFEE = "robusta_coffee"
    BEANS = "beans"
    CASSAVA = "cassava"
    MATOOKE_BANANA = "matooke_banana"
    GROUNDNUTS = "groundnuts"


class AgroEcologicalZone(str, Enum):
    LAKE_VICTORIA_CRESCENT = "lake_victoria_crescent"
    WESTERN_HIGHLANDS = "western_highlands"
    NORTHERN_SAVANNAH = "northern_savannah"
    EASTERN_PLAINS = "eastern_plains"


class GrowthStage(str, Enum):
    PLANTING = "planting"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    HARVEST_DRYING = "harvest_drying"


AGRO_ZONES: dict[str, dict[str, Any]] = {
    AgroEcologicalZone.LAKE_VICTORIA_CRESCENT.value: {
        "name": "Lake Victoria Crescent",
        "rainfall_pattern": "Bimodal (Mar-May, Sep-Nov)",
        "baseline_temp_c": 24.5,
        "evaporation_factor": 1.0,
        "typical_soil": "Ferralsols / clay-loam",
    },
    AgroEcologicalZone.WESTERN_HIGHLANDS.value: {
        "name": "Western Highlands",
        "rainfall_pattern": "Bimodal sub-humid montane",
        "baseline_temp_c": 20.0,
        "evaporation_factor": 0.85,
        "typical_soil": "Volcanic Andosols / Nitisols",
    },
    AgroEcologicalZone.NORTHERN_SAVANNAH.value: {
        "name": "Northern Savannah",
        "rainfall_pattern": "Unimodal / transitional continental",
        "baseline_temp_c": 27.5,
        "evaporation_factor": 1.25,
        "typical_soil": "Sandy-loam / Lixisols",
    },
    AgroEcologicalZone.EASTERN_PLAINS.value: {
        "name": "Eastern Plains",
        "rainfall_pattern": "Bimodal warm plains",
        "baseline_temp_c": 26.0,
        "evaporation_factor": 1.15,
        "typical_soil": "Loamy-sand / Plinthosols",
    },
}

CROP_PROFILES: dict[str, dict[str, Any]] = {
    CropType.MAIZE.value: {
        "display_name": "Maize (Zea mays)",
        "rain_14d_min_mm": 55.0,
        "rain_14d_opt_max_mm": 135.0,
        "harvest_max_rain_14d_mm": 35.0,
        "ph_min": 5.5,
        "ph_max": 7.0,
        "moisture_min": 0.42,
        "moisture_max": 0.82,
        "heat_stress_anomaly_c": 2.5,
    },
    CropType.ROBUSTA_COFFEE.value: {
        "display_name": "Robusta Coffee (Coffea canephora)",
        "rain_14d_min_mm": 65.0,
        "rain_14d_opt_max_mm": 150.0,
        "harvest_max_rain_14d_mm": 45.0,
        "ph_min": 5.0,
        "ph_max": 6.5,
        "moisture_min": 0.48,
        "moisture_max": 0.85,
        "heat_stress_anomaly_c": 2.0,
    },
    CropType.BEANS.value: {
        "display_name": "Common Beans (Phaseolus vulgaris)",
        "rain_14d_min_mm": 45.0,
        "rain_14d_opt_max_mm": 110.0,
        "harvest_max_rain_14d_mm": 30.0,
        "ph_min": 5.8,
        "ph_max": 7.0,
        "moisture_min": 0.40,
        "moisture_max": 0.75,
        "heat_stress_anomaly_c": 2.2,
    },
    CropType.CASSAVA.value: {
        "display_name": "Cassava (Manihot esculenta)",
        "rain_14d_min_mm": 35.0,
        "rain_14d_opt_max_mm": 125.0,
        "harvest_max_rain_14d_mm": 60.0,
        "ph_min": 4.8,
        "ph_max": 6.8,
        "moisture_min": 0.30,
        "moisture_max": 0.78,
        "heat_stress_anomaly_c": 3.2,
    },
    CropType.MATOOKE_BANANA.value: {
        "display_name": "Matooke Highland Banana (Musa acuminata)",
        "rain_14d_min_mm": 60.0,
        "rain_14d_opt_max_mm": 145.0,
        "harvest_max_rain_14d_mm": 90.0,
        "ph_min": 5.5,
        "ph_max": 7.0,
        "moisture_min": 0.50,
        "moisture_max": 0.85,
        "heat_stress_anomaly_c": 2.5,
    },
    CropType.GROUNDNUTS.value: {
        "display_name": "Groundnuts (Arachis hypogaea)",
        "rain_14d_min_mm": 40.0,
        "rain_14d_opt_max_mm": 105.0,
        "harvest_max_rain_14d_mm": 25.0,
        "ph_min": 5.3,
        "ph_max": 6.7,
        "moisture_min": 0.35,
        "moisture_max": 0.74,
        "heat_stress_anomaly_c": 2.8,
    },
}


class AdvisoryInput(BaseModel):
    crop: CropType = Field(..., description="Target East African staple or cash crop")
    zone: AgroEcologicalZone = Field(..., description="Agro-ecological zone")
    growth_stage: GrowthStage = Field(
        default=GrowthStage.PLANTING, description="Current phenological stage"
    )
    rain_14d_mm: float = Field(
        ..., ge=0.0, le=600.0, description="14-day cumulative rainfall in millimeters"
    )
    soil_ph: float | None = Field(
        default=None, ge=3.0, le=9.5, description="Measured top-soil pH (0-20cm) if available"
    )
    soil_moisture_index: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Normalized volumetric soil moisture index (0.0=bone dry, 1.0=saturated)",
    )
    temp_anomaly_c: float | None = Field(
        default=None,
        ge=-8.0,
        le=10.0,
        description="14-day temperature anomaly relative to zonal seasonal mean (deg C)",
    )
    lang: Literal["en", "lg", "sw"] = Field(
        default="en", description="Language code: English (en), Luganda (lg), or Swahili (sw)"
    )


class UncertaintyBounds(BaseModel):
    point_confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_interval: tuple[float, float]
    data_completeness_score: float = Field(..., ge=0.0, le=1.0)
    missing_sensor_warnings: list[str]
    epistemic_disclaimer: str


class AdvisoryResult(BaseModel):
    crop: str
    crop_display_name: str
    zone: str
    zone_display_name: str
    growth_stage: str
    status: Literal["OPTIMAL", "CAUTION", "DELAY_OR_MITIGATE", "CRITICAL_RISK"]
    action_code: str
    headline: str
    recommendations: list[str]
    rule_trace: list[str]
    uncertainty: UncertaintyBounds
    localized_summary: str
    sms_160: str


class AdvisoryEngine:
    """Deterministic, explainable rule-based crop advisory engine with uncertainty tracking."""

    EPISTEMIC_DISCLAIMER = (
        "Advisory reflects agro-climatic heuristics for smallholder decision support and does NOT "
        "guarantee crop yield. Local micro-topography, seed viability, and field drainage must be "
        "verified on-plot before acting."
    )

    def evaluate(self, payload: AdvisoryInput) -> AdvisoryResult:
        crop_key = payload.crop.value
        zone_key = payload.zone.value
        stage_key = payload.growth_stage.value

        profile = CROP_PROFILES[crop_key]
        zone_info = AGRO_ZONES[zone_key]

        evap_factor: float = zone_info["evaporation_factor"]
        effective_rain_min = round(profile["rain_14d_min_mm"] * evap_factor, 1)
        effective_rain_max = round(profile["rain_14d_opt_max_mm"] * evap_factor, 1)

        rule_trace: list[str] = []
        recommendations: list[str] = []
        missing_warnings: list[str] = []

        # Track data completeness and uncertainty
        available_signals = 1  # rain_14d_mm is always required
        total_signals = 4  # rain_14d_mm, soil_ph, soil_moisture_index, temp_anomaly_c

        if payload.soil_ph is not None:
            available_signals += 1
        else:
            missing_warnings.append(
                "Soil pH not provided; nutrient lock-up or acidity stress cannot be ruled out."
            )

        if payload.soil_moisture_index is not None:
            available_signals += 1
        else:
            missing_warnings.append(
                "Direct soil moisture index missing; estimating root-zone moisture from 14d rainfall and zonal evapotranspiration."
            )

        if payload.temp_anomaly_c is not None:
            available_signals += 1
        else:
            missing_warnings.append(
                "Temperature anomaly sensor absent; assuming baseline seasonal evapotranspiration."
            )

        data_completeness = round(available_signals / total_signals, 2)

        # Estimate moisture if not directly measured
        inferred_moisture = payload.soil_moisture_index
        if inferred_moisture is None:
            inferred_moisture = min(1.0, max(0.1, payload.rain_14d_mm / (effective_rain_max * 1.25)))
            rule_trace.append(
                f"RULE_MOISTURE_PROXY: Inferred soil_moisture_index={inferred_moisture:.2f} from rain_14d_mm={payload.rain_14d_mm}mm and zone_evap_factor={evap_factor}."
            )
        else:
            rule_trace.append(
                f"RULE_MOISTURE_DIRECT: Observed soil_moisture_index={inferred_moisture:.2f} (crop optimal window {profile['moisture_min']:.2f}-{profile['moisture_max']:.2f})."
            )

        # Primary status and action evaluation
        status: Literal["OPTIMAL", "CAUTION", "DELAY_OR_MITIGATE", "CRITICAL_RISK"] = "OPTIMAL"
        action_code = "PROCEED_STANDARD"

        if stage_key == GrowthStage.HARVEST_DRYING.value:
            harvest_limit = profile["harvest_max_rain_14d_mm"]
            if payload.rain_14d_mm > harvest_limit * 1.6:
                status = "CRITICAL_RISK"
                action_code = "AFLATOXIN_DRYING_ALERT"
                rule_trace.append(
                    f"RULE_HARVEST_WET_CRITICAL: rain_14d_mm={payload.rain_14d_mm}mm exceeds 1.6x safe harvest drying limit ({harvest_limit}mm)."
                )
                recommendations.append(
                    "High post-harvest spoilage/aflatoxin risk: dry harvest on raised tarpaulins or ventilated cribs off bare soil."
                )
                recommendations.append(
                    "Verify grain moisture below 13.5% before hermetic storage (PICS bags or silos)."
                )
            elif payload.rain_14d_mm > harvest_limit:
                status = "CAUTION"
                action_code = "HARVEST_MOISTURE_ALERT"
                rule_trace.append(
                    f"RULE_HARVEST_WET_CAUTION: rain_14d_mm={payload.rain_14d_mm}mm exceeds harvest drying threshold ({harvest_limit}mm)."
                )
                recommendations.append(
                    "Intermittent showers during harvest: harvest during morning dry windows and protect drying mats with waterproof covers."
                )
            else:
                rule_trace.append(
                    f"RULE_HARVEST_DRY_OPTIMAL: rain_14d_mm={payload.rain_14d_mm}mm is within safe drying limit ({harvest_limit}mm)."
                )
                recommendations.append(
                    "Favorable dry conditions for harvest curing and clean post-harvest sorting."
                )
        else:
            # Planting, Vegetative, or Flowering stages
            if payload.rain_14d_mm < effective_rain_min * 0.65 or inferred_moisture < profile["moisture_min"] * 0.75:
                status = "CRITICAL_RISK" if stage_key == GrowthStage.FLOWERING.value else "DELAY_OR_MITIGATE"
                action_code = "DELAY_PLANTING_DRY" if stage_key == GrowthStage.PLANTING.value else "DROUGHT_STRESS_MITIGATION"
                rule_trace.append(
                    f"RULE_MOISTURE_DEFICIT: rain_14d_mm={payload.rain_14d_mm}mm < adjusted min {effective_rain_min}mm (or moisture {inferred_moisture:.2f} < {profile['moisture_min']})."
                )
                if stage_key == GrowthStage.PLANTING.value:
                    recommendations.append(
                        f"Delay dry-sowing of {profile['display_name']} until at least {effective_rain_min:.0f}mm cumulative 14-day rainfall is established."
                    )
                    recommendations.append(
                        "Prepare planting basins / rip lines and apply organic surface mulch to trap early showers."
                    )
                else:
                    recommendations.append(
                        "Severe moisture deficit during active growth: apply 5-8cm organic mulch around root zones and avoid disturbance weeding."
                    )
            elif payload.rain_14d_mm < effective_rain_min or inferred_moisture < profile["moisture_min"]:
                status = "CAUTION"
                action_code = "MULCH_AND_CONSERVE"
                rule_trace.append(
                    f"RULE_MARGINAL_MOISTURE: rain_14d_mm={payload.rain_14d_mm}mm is marginally below zonal target {effective_rain_min}mm."
                )
                recommendations.append(
                    "Sub-optimal moisture onset: conserve soil water using contour tied-ridges and grass mulching."
                )
            elif payload.rain_14d_mm > effective_rain_max * 1.35 or inferred_moisture > profile["moisture_max"]:
                status = "DELAY_OR_MITIGATE"
                action_code = "DRAINAGE_AND_RIDGING"
                rule_trace.append(
                    f"RULE_WATERLOGGING_RISK: rain_14d_mm={payload.rain_14d_mm}mm exceeds upper threshold ({effective_rain_max}mm) or moisture {inferred_moisture:.2f} > {profile['moisture_max']}."
                )
                recommendations.append(
                    "Waterlogging and root asphyxiation risk: clear perimeter diversion trenches and plant on raised ridges."
                )
                recommendations.append(
                    "Postpone top-dressing soluble nitrogen fertilizer during heavy downpours to prevent leaching."
                )
            else:
                rule_trace.append(
                    f"RULE_MOISTURE_OPTIMAL: rain_14d_mm={payload.rain_14d_mm}mm within zonal target [{effective_rain_min}, {effective_rain_max}]mm."
                )
                recommendations.append(
                    f"Moisture regime is well-suited for {profile['display_name']} ({stage_key} stage) in {zone_info['name']}."
                )

        # Evaluate Soil pH if available
        if payload.soil_ph is not None:
            if payload.soil_ph < profile["ph_min"]:
                if status == "OPTIMAL":
                    status = "CAUTION"
                    action_code = "LIME_AMENDMENT_NEEDED"
                rule_trace.append(
                    f"RULE_SOIL_ACIDIC: soil_ph={payload.soil_ph} is below optimal range [{profile['ph_min']}, {profile['ph_max']}]."
                )
                recommendations.append(
                    f"Acidic soil detected (pH {payload.soil_ph:.1f} < {profile['ph_min']:.1f}): incorporate agricultural lime or well-decomposed farmyard manure to improve phosphorus availability."
                )
            elif payload.soil_ph > profile["ph_max"]:
                if status == "OPTIMAL":
                    status = "CAUTION"
                    action_code = "ALKALINE_SOIL_MANAGEMENT"
                rule_trace.append(
                    f"RULE_SOIL_ALKALINE: soil_ph={payload.soil_ph} exceeds optimal range [{profile['ph_min']}, {profile['ph_max']}]."
                )
                recommendations.append(
                    f"Elevated soil pH ({payload.soil_ph:.1f} > {profile['ph_max']:.1f}): band organic compost to buffer micronutrient (zinc/iron) availability."
                )
            else:
                rule_trace.append(
                    f"RULE_SOIL_PH_OPTIMAL: soil_ph={payload.soil_ph} is within [{profile['ph_min']}, {profile['ph_max']}]."
                )

        # Evaluate Temperature Anomaly if available
        if payload.temp_anomaly_c is not None:
            heat_limit = profile["heat_stress_anomaly_c"]
            if payload.temp_anomaly_c >= heat_limit:
                if status == "OPTIMAL":
                    status = "CAUTION"
                    action_code = "HEAT_SHADE_MULCH"
                elif status == "DELAY_OR_MITIGATE" and stage_key == GrowthStage.FLOWERING.value:
                    status = "CRITICAL_RISK"
                rule_trace.append(
                    f"RULE_THERMAL_ANOMALY: temp_anomaly_c=+{payload.temp_anomaly_c}C >= crop heat stress limit (+{heat_limit}C)."
                )
                recommendations.append(
                    f"Thermal anomaly (+{payload.temp_anomaly_c:.1f}C above zonal mean): maintain shade trees (e.g., Albizia/Cordia for coffee/matooke) and thick mulch to cool root zones."
                )
            else:
                rule_trace.append(
                    f"RULE_THERMAL_NORMAL: temp_anomaly_c={payload.temp_anomaly_c:+.1f}C within safe thermal tolerance (<+{heat_limit}C)."
                )

        # Compute Uncertainty Bounds
        # Point confidence scales with sensor completeness and proximity to extreme boundaries
        base_confidence = 0.55 + (0.35 * data_completeness)
        half_width = round(0.22 - (0.14 * data_completeness), 2)
        point_confidence = round(min(0.94, max(0.45, base_confidence)), 2)
        lower_bound = round(max(0.20, point_confidence - half_width), 2)
        upper_bound = round(min(0.98, point_confidence + half_width), 2)

        uncertainty = UncertaintyBounds(
            point_confidence=point_confidence,
            confidence_interval=(lower_bound, upper_bound),
            data_completeness_score=data_completeness,
            missing_sensor_warnings=missing_warnings,
            epistemic_disclaimer=self.EPISTEMIC_DISCLAIMER,
        )

        headline = (
            f"{profile['display_name']} [{stage_key.upper()}] in {zone_info['name']}: "
            f"{status} ({action_code})"
        )

        localized_summary = translate_advisory_summary(
            lang=payload.lang,
            crop_key=crop_key,
            zone_name=zone_info["name"],
            stage_key=stage_key,
            status=status,
            action_code=action_code,
            rain_14d_mm=payload.rain_14d_mm,
            point_confidence=point_confidence,
        )

        sms_160 = format_sms_advisory(
            lang=payload.lang,
            crop_key=crop_key,
            stage_key=stage_key,
            status=status,
            action_code=action_code,
            rain_14d_mm=payload.rain_14d_mm,
            confidence_interval=uncertainty.confidence_interval,
        )

        return AdvisoryResult(
            crop=crop_key,
            crop_display_name=profile["display_name"],
            zone=zone_key,
            zone_display_name=zone_info["name"],
            growth_stage=stage_key,
            status=status,
            action_code=action_code,
            headline=headline,
            recommendations=recommendations,
            rule_trace=rule_trace,
            uncertainty=uncertainty,
            localized_summary=localized_summary,
            sms_160=sms_160,
        )
