"""Multilingual Localization Layer for English (en), Luganda (lg), and Swahili (sw)."""

from __future__ import annotations

from typing import Literal

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "lg": "Oluganda (Luganda)",
    "sw": "Kiswahili (Swahili)",
}

CROP_NAMES_I18N: dict[str, dict[str, str]] = {
    "maize": {"en": "Maize", "lg": "Kasooli", "sw": "Mahindi"},
    "robusta_coffee": {"en": "Coffee", "lg": "Emwanyi", "sw": "Kahawa"},
    "beans": {"en": "Beans", "lg": "Ebijanjaalo", "sw": "Maharagwe"},
    "cassava": {"en": "Cassava", "lg": "Muwogo", "sw": "Muhogo"},
    "matooke_banana": {"en": "Matooke", "lg": "Matooke", "sw": "Ndizi"},
    "groundnuts": {"en": "G-nuts", "lg": "Ebinyebwa", "sw": "Karanga"},
}

STAGE_NAMES_I18N: dict[str, dict[str, str]] = {
    "planting": {"en": "Planting", "lg": "Okusiga", "sw": "Kupanda"},
    "vegetative": {"en": "Growth", "lg": "Okukula", "sw": "Ukuaji"},
    "flowering": {"en": "Flowering", "lg": "Okumulisa", "sw": "Kuchanua"},
    "harvest_drying": {"en": "Harvest", "lg": "Okukungula", "sw": "Kuvuna"},
}

ACTION_I18N: dict[str, dict[str, str]] = {
    "PROCEED_STANDARD": {
        "en": "Conditions favorable. Proceed with recommended spacing & weeding.",
        "lg": "Embeera nnungi. Siga oba lima mu mabanga agalagirwa.",
        "sw": "Hali ni nzuri. Endelea kupanda na kupalilia kwa nafasi sahihi.",
    },
    "MULCH_AND_CONSERVE": {
        "en": "Marginal moisture. Apply grass mulch & contour ridges to conserve water.",
        "lg": "Amazzi matono mu ttaka. Bikka ebisubi ku ttaka okukuuma amazzi.",
        "sw": "Unyevu mdogo. Weka matandazo ya nyasi kuhifadhi maji ardhini.",
    },
    "DELAY_PLANTING_DRY": {
        "en": "Dry spell alert. Delay sowing until steady rains establish; prepare basins.",
        "lg": "omusana mungi. Lindako okusiga okutuusa enkuba lwe eneetonnya obulungi.",
        "sw": "Ukame bado. Subiri kupanda hadi mvua za kutosha zianze; andaa mashimo.",
    },
    "DROUGHT_STRESS_MITIGATION": {
        "en": "Severe moisture deficit. Mulch heavily (5-8cm) and avoid deep soil disturbance.",
        "lg": "Ettaka kkalu nnyo. Bikka ebisubi bingi era tewettaniraokukabala ettaka.",
        "sw": "Upungufu mkubwa wa unyevu. Tandaza nyasi nyingi na epuka kuchimbua udongo.",
    },
    "DRAINAGE_AND_RIDGING": {
        "en": "Excess rain risk. Open drainage channels, ridge rows & hold soluble fertilizer.",
        "lg": "Enkuba nyungi nnyo. Gogola emikutu gy'amazzi era oyimirize ebigimusa.",
        "sw": "Mvua nyingi mno. Fungua mifereji ya maji na usitishe mbolea ya chumvi.",
    },
    "LIME_AMENDMENT_NEEDED": {
        "en": "Soil acidic. Apply agricultural lime or compost manure before next planting.",
        "lg": "Ettaka lirimu asidi. Teekamu laayimu w'ebyobulimi oba nnakavundira.",
        "sw": "Udongo una tindikali. Weka chokaa ya kilimo au mboji kabla ya kupanda.",
    },
    "ALKALINE_SOIL_MANAGEMENT": {
        "en": "Soil pH high. Band well-decomposed organic manure to aid root nutrient uptake.",
        "lg": "pH y'ettaka waggulu. Kozesa nnakavundira okuyamba ebimera okufuna ebiriisa.",
        "sw": "pH ya udongo ipo juu. Tumia mboji iliyoiva kusaidia mizizi kupata virutubisho.",
    },
    "HEAT_SHADE_MULCH": {
        "en": "High heat anomaly. Maintain shade trees and root-zone mulch.",
        "lg": "Ebbugumu lingi. Kuuma emiti egy'ekisiikirize era obikke ettaka.",
        "sw": "Joto limezidi. Tunza miti ya kivuli na weka matandazo shambani.",
    },
    "HARVEST_MOISTURE_ALERT": {
        "en": "Wet harvest caution. Dry crop on tarpaulins and cover before afternoon showers.",
        "lg": "Enkuba mu makungula. Yanika ku matundubaali era obikke enkuba tennatonnya.",
        "sw": "Mvua wakati wa mavuno. Kausha mazao kwenye turubai na funika mapema.",
    },
    "AFLATOXIN_DRYING_ALERT": {
        "en": "High spoilage/aflatoxin risk! Dry off-ground to <13.5% moisture before storage.",
        "lg": "Obulabe bw'obukuku! Yanika waggulu ku katimba okutuuka bwe bikala obulungi.",
        "sw": "Hatari ya sumukuvu! Kausha juu ya chaga hadi unyevu <13.5% kabla ya kuhifadhi.",
    },
}

SMS_SHORT_ACTION: dict[str, dict[str, str]] = {
    "PROCEED_STANDARD": {
        "en": "Good moisture. Plant/weed on time.",
        "lg": "Embeera nnungi. Siga/lima mu budde.",
        "sw": "Unyevu mzuri. Panda/palilia kwa wakati.",
    },
    "MULCH_AND_CONSERVE": {
        "en": "Low rain. Mulch & ridge to save water.",
        "lg": "Amazzi matono. Bikka ebisubi mu nnimiro.",
        "sw": "Mvua haba. Weka matandazo kuhifadhi maji.",
    },
    "DELAY_PLANTING_DRY": {
        "en": "Too dry! Delay sowing; prep basins.",
        "lg": "Kkalu! Lindako okusiga; tegeka ettaka.",
        "sw": "Pakavu! Subiri kupanda; andaa mashimo.",
    },
    "DROUGHT_STRESS_MITIGATION": {
        "en": "Drought stress! Mulch 5-8cm deep.",
        "lg": "Ettaka kkalu! Bikka ebisubi bingi.",
        "sw": "Ukame! Tandaza nyasi 5-8cm shambani.",
    },
    "DRAINAGE_AND_RIDGING": {
        "en": "Heavy rain! Clear drains & ridge.",
        "lg": "Enkuba nnyingi! Gogola emifulejje.",
        "sw": "Mvua nyingi! Zibua mifereji ya maji.",
    },
    "LIME_AMENDMENT_NEEDED": {
        "en": "Acid soil. Add agri-lime & compost.",
        "lg": "Asidi mu ttaka. Teekamu laayimu.",
        "sw": "Tindikali ardhini. Weka chokaa/mboji.",
    },
    "ALKALINE_SOIL_MANAGEMENT": {
        "en": "High pH. Apply organic compost.",
        "lg": "pH waggulu. Kozesa nnakavundira.",
        "sw": "pH ipo juu. Weka mboji shambani.",
    },
    "HEAT_SHADE_MULCH": {
        "en": "Heat alert! Mulch & keep shade.",
        "lg": "Ebbugumu! Bikka ettaka n'ekisiikirize.",
        "sw": "Joto kali! Weka matandazo na kivuli.",
    },
    "HARVEST_MOISTURE_ALERT": {
        "en": "Wet harvest. Dry on tarpaulins.",
        "lg": "Enkuba! Yanika ku matundubaali.",
        "sw": "Mvua! Kausha mazao kwenye turubai.",
    },
    "AFLATOXIN_DRYING_ALERT": {
        "en": "Mold risk! Dry off-ground <13.5%.",
        "lg": "Obukuku! Yanika waggulu bikale.",
        "sw": "Sumukuvu! Kausha juu ya chaga <13.5%.",
    },
}


def translate_advisory_summary(
    lang: Literal["en", "lg", "sw"],
    crop_key: str,
    zone_name: str,
    stage_key: str,
    status: str,
    action_code: str,
    rain_14d_mm: float,
    point_confidence: float,
) -> str:
    """Return a full human-readable localized advisory summary."""
    lang_key = lang if lang in SUPPORTED_LANGUAGES else "en"
    crop_label = CROP_NAMES_I18N.get(crop_key, {}).get(lang_key, crop_key)
    stage_label = STAGE_NAMES_I18N.get(stage_key, {}).get(lang_key, stage_key)
    action_text = ACTION_I18N.get(action_code, ACTION_I18N["PROCEED_STANDARD"]).get(lang_key, "")
    conf_pct = int(round(point_confidence * 100))

    if lang_key == "lg":
        return (
            f"[AgriSignal Oluganda] Ekirime: {crop_label} ({stage_label}) mu {zone_name} | "
            f"Enkuba ennaku 14: {rain_14d_mm:.0f}mm | Embeera: {status}. "
            f"Amagezi: {action_text} (Obwesigwa bw'amawulire: {conf_pct}% - gezesa ettaka lyo)."
        )
    if lang_key == "sw":
        return (
            f"[AgriSignal Kiswahili] Zao: {crop_label} ({stage_label}) eneo la {zone_name} | "
            f"Mvua siku 14: {rain_14d_mm:.0f}mm | Hali: {status}. "
            f"Ushauri: {action_text} (Uhakika wa data: {conf_pct}% - hakiki shamba lako)."
        )
    return (
        f"[AgriSignal English] Crop: {crop_label} ({stage_label}) in {zone_name} | "
        f"14d Rain: {rain_14d_mm:.0f}mm | Status: {status}. "
        f"Guidance: {action_text} (Confidence: {conf_pct}% - verify on-plot conditions)."
    )


def format_sms_advisory(
    lang: Literal["en", "lg", "sw"],
    crop_key: str,
    stage_key: str,
    status: str,
    action_code: str,
    rain_14d_mm: float,
    confidence_interval: tuple[float, float],
) -> str:
    """Format a strict <=160-character GSM-7 compatible SMS advisory with uncertainty bounds."""
    lang_key = lang if lang in SUPPORTED_LANGUAGES else "en"
    crop_label = CROP_NAMES_I18N.get(crop_key, {}).get(lang_key, crop_key)
    stage_label = STAGE_NAMES_I18N.get(stage_key, {}).get(lang_key, stage_key)
    short_action = SMS_SHORT_ACTION.get(action_code, SMS_SHORT_ACTION["PROCEED_STANDARD"]).get(
        lang_key, "Check field."
    )
    ci_lo = int(round(confidence_interval[0] * 100))
    ci_hi = int(round(confidence_interval[1] * 100))

    sms = (
        f"AGRISIGNAL {crop_label}({stage_label}): {status}. "
        f"Rain14d:{rain_14d_mm:.0f}mm. {short_action} "
        f"Conf:{ci_lo}-{ci_hi}% (No yield guarantee)"
    )
    if len(sms) > 160:
        sms = sms[:157] + "..."
    return sms
