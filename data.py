"""
Hardcoded lookup data for the Solar Payback Calculator v1.

All rates are approximate and intended for estimation only.
"""

# ---------------------------------------------------------------------------
# Battery presets: id -> (label, kWh, installed cost $)
# ---------------------------------------------------------------------------
BATTERY_OPTIONS = {
    "none":      ("None", 0, 0),
    "powerwall": ("Tesla Powerwall 3 (13.5 kWh)", 13.5, 13_000),
    "enphase":   ("Enphase IQ 5P (5 kWh)", 5.0, 7_000),
    "franklin":  ("Franklin WH (13.6 kWh)", 13.6, 13_500),
    "custom":    ("Custom", 0, 0),  # cost calculated at runtime
}

CUSTOM_BATTERY_COST_PER_KWH = 900  # $/kWh installed

# ---------------------------------------------------------------------------
# Utility territory lookup by 3-digit zip prefix
# ---------------------------------------------------------------------------
_UTILITY_BY_PREFIX = {
    # Southern CA — SCE territory (approximate)
    **{str(p): "SCE" for p in range(900, 909)},
    **{str(p): "SCE" for p in range(910, 919)},
    # San Diego county — SDGE territory
    **{str(p): "SDGE" for p in range(919, 922)},
    # Inland Empire / Palm Springs — SCE territory
    **{str(p): "SCE" for p in range(922, 930)},
    **{str(p): "SCE" for p in range(930, 936)},
    # Central & Northern CA — PG&E territory
    **{str(p): "PGE" for p in range(936, 967)},
}


def get_utility(zip_code: str) -> str | None:
    """Return 'PGE', 'SCE', or 'SDGE' for a CA zip code, or None if not found."""
    prefix = zip_code[:3]
    return _UTILITY_BY_PREFIX.get(prefix)


# ---------------------------------------------------------------------------
# Peak sun hours (annual average) by 3-digit zip prefix
# Source: NREL PVWatts approximations for CA regions
# ---------------------------------------------------------------------------
_SUN_HOURS_BY_PREFIX = {
    # LA basin
    **{str(p): 5.6 for p in range(900, 909)},
    # San Gabriel Valley / Pasadena / Inland
    **{str(p): 5.7 for p in range(910, 920)},
    # San Diego county (SDGE)
    **{str(p): 5.7 for p in range(919, 920)},  # inland San Diego (El Cajon, Santee)
    **{str(p): 5.5 for p in range(920, 922)},  # coastal San Diego
    # Inland Empire / Palm Springs
    **{str(p): 5.5 for p in range(922, 926)},
    **{str(p): 5.8 for p in range(926, 930)},
    # Central Coast (SLO, Santa Barbara)
    **{str(p): 5.3 for p in range(930, 936)},
    # Central Valley (Fresno, Bakersfield)
    **{str(p): 5.6 for p in range(936, 940)},
    # SF Bay Area
    **{str(p): 5.1 for p in range(940, 945)},
    **{str(p): 5.2 for p in range(945, 950)},
    # San Jose / Santa Cruz
    **{str(p): 5.3 for p in range(950, 955)},
    # Sacramento area
    **{str(p): 5.4 for p in range(955, 959)},
    # Far Northern CA
    **{str(p): 5.0 for p in range(959, 967)},
}


def get_peak_sun_hours(zip_code: str) -> float | None:
    """Return average daily peak sun hours for a CA zip code."""
    prefix = zip_code[:3]
    return _SUN_HOURS_BY_PREFIX.get(prefix)


# ---------------------------------------------------------------------------
# TOU rate schedules (approximate 2025 rates, $/kWh)
# zero_carbon_pct: share of electricity from zero-carbon sources per the
# CEC Annual Power Content Label (default residential plan, 2024 report).
# ---------------------------------------------------------------------------
TOU_RATES = {
    "PGE": {
        "plan_name": "E-TOU-C",
        "peak": 0.49,           # 4–9 PM
        "offpeak": 0.30,
        "weighted_avg": 0.36,
        "zero_carbon_pct": 0.98,  # 98% zero-carbon (CEC 2024 Power Content Label)
        "base_charge_monthly": 24.00,  # PG&E minimum monthly bill (NEM 3.0 grid participation charge)
    },
    "SCE": {
        "plan_name": "TOU-D-Prime",
        "peak": 0.54,           # 4–9 PM
        "offpeak": 0.27,
        "weighted_avg": 0.35,
        "zero_carbon_pct": 0.49,  # 49% zero-carbon (CEC 2024 Power Content Label)
        "base_charge_monthly": 10.00,  # SCE minimum monthly customer charge
    },
    "SDGE": {
        "plan_name": "TOU-DR3",
        "peak": 0.64,           # 4–9 PM
        "offpeak": 0.40,
        "weighted_avg": 0.50,
        "zero_carbon_pct": 0.45,  # 45% zero-carbon (CEC 2024 Power Content Label)
        "base_charge_monthly": 17.00,  # SDG&E minimum monthly customer charge
    },
}

# ---------------------------------------------------------------------------
# Carbon emission factor for the fossil-fuel portion of CA grid generation.
# Primarily natural gas combined-cycle; approximately 0.855 lbs CO2/kWh.
# Multiply by (1 - zero_carbon_pct) to get a utility's effective grid rate.
# ---------------------------------------------------------------------------
FOSSIL_EMISSION_FACTOR_LBS_KWH = 0.855

# ---------------------------------------------------------------------------
# NEM 3.0 export credit (Avoided Cost Calculator approximation)
# Simplified flat average — real ACC varies by hour/month
# ---------------------------------------------------------------------------
NEM3_EXPORT_RATE = 0.05  # $/kWh average

# ---------------------------------------------------------------------------
# System constants
# ---------------------------------------------------------------------------
SYSTEM_LOSSES = 0.14          # inverter + wiring + soiling
BATTERY_ROUND_TRIP_EFF = 0.90
BASE_SELF_CONSUMPTION = 0.40  # without battery
MAX_SELF_CONSUMPTION = 0.85   # ceiling with battery
