"""
Core calculation engine for the Solar Payback Calculator.
"""

from __future__ import annotations

from dataclasses import dataclass

from data import (
    BATTERY_OPTIONS,
    BATTERY_ROUND_TRIP_EFF,
    BASE_SELF_CONSUMPTION,
    CUSTOM_BATTERY_COST_PER_KWH,
    MAX_SELF_CONSUMPTION,
    NEM3_EXPORT_RATE,
    SYSTEM_LOSSES,
    TOU_RATES,
    get_peak_sun_hours,
    get_utility,
)


@dataclass
class SolarResults:
    # Identifiers
    utility: str
    plan_name: str
    peak_sun_hours: float

    # Production
    annual_production_kwh: float
    monthly_production_kwh: float
    annual_consumption_kwh: float
    offset_pct: float

    # Financial
    system_cost: float
    battery_cost: float
    total_cost: float
    monthly_payment: float
    year1_savings: float

    # Self-consumption
    self_consumption_ratio: float

    # Payback
    payback_years: float | None  # None if never pays back within 20 yr
    payback_display: str

    # 20-year series (year 0 = today, years 1–20)
    years: list[int]
    cumulative_no_solar: list[float]
    cumulative_solar: list[float]


def calculate(
    system_kw: float,
    monthly_bill: float,
    zip_code: str,
    battery_key: str,
    custom_battery_kwh: float = 0,
    # Advanced settings
    cost_per_watt: float = 2.75,
    loan_term_years: int = 20,
    loan_apr: float = 5.5,
    rate_escalation: float = 4.0,
    panel_degradation: float = 0.5,
) -> SolarResults:
    # ------------------------------------------------------------------
    # 1. Location lookups
    # ------------------------------------------------------------------
    utility = get_utility(zip_code)
    if utility is None:
        raise ValueError(f"Zip code {zip_code} is not in a supported CA utility territory.")
    peak_sun_hours = get_peak_sun_hours(zip_code)
    tou = TOU_RATES[utility]

    # ------------------------------------------------------------------
    # 2. Battery info
    # ------------------------------------------------------------------
    if battery_key == "custom":
        battery_kwh = custom_battery_kwh
        battery_cost = battery_kwh * CUSTOM_BATTERY_COST_PER_KWH
    else:
        _, battery_kwh, battery_cost = BATTERY_OPTIONS[battery_key]

    # ------------------------------------------------------------------
    # 3. Solar production
    # ------------------------------------------------------------------
    annual_production = system_kw * peak_sun_hours * 365 * (1 - SYSTEM_LOSSES)
    monthly_production = annual_production / 12

    # ------------------------------------------------------------------
    # 4. Consumption estimate from bill
    # ------------------------------------------------------------------
    avg_rate = tou["weighted_avg"]
    annual_consumption = (monthly_bill * 12) / avg_rate

    # ------------------------------------------------------------------
    # 5. Self-consumption ratio
    # ------------------------------------------------------------------
    if battery_kwh > 0:
        daily_production = annual_production / 365
        daily_excess = daily_production * (1 - BASE_SELF_CONSUMPTION)
        daily_battery_capture = min(battery_kwh * BATTERY_ROUND_TRIP_EFF, daily_excess)
        self_consumption_ratio = BASE_SELF_CONSUMPTION + (
            daily_battery_capture / daily_production if daily_production > 0 else 0
        )
        self_consumption_ratio = min(self_consumption_ratio, MAX_SELF_CONSUMPTION)
    else:
        self_consumption_ratio = BASE_SELF_CONSUMPTION

    # ------------------------------------------------------------------
    # 6. System cost & loan payment
    # ------------------------------------------------------------------
    system_cost = system_kw * 1000 * cost_per_watt
    total_cost = system_cost + battery_cost

    monthly_rate = loan_apr / 100 / 12
    n_payments = loan_term_years * 12
    if monthly_rate > 0:
        monthly_payment = total_cost * (
            monthly_rate * (1 + monthly_rate) ** n_payments
        ) / ((1 + monthly_rate) ** n_payments - 1)
    else:
        monthly_payment = total_cost / n_payments

    # ------------------------------------------------------------------
    # 7. 20-year projection
    # ------------------------------------------------------------------
    esc = rate_escalation / 100
    deg = panel_degradation / 100
    offpeak = tou["offpeak"]
    peak = tou["peak"]

    years = list(range(0, 21))
    cumulative_no_solar = [0.0]
    cumulative_solar = [0.0]
    cum_ns = 0.0
    cum_s = 0.0
    payback_years = None
    year1_savings = 0.0

    for yr in range(1, 21):
        # --- No-solar annual cost ---
        no_solar_annual = monthly_bill * 12 * (1 + esc) ** yr
        cum_ns += no_solar_annual

        # --- Solar production this year (degradation) ---
        yr_production = annual_production * (1 - deg) ** yr
        self_consumed = yr_production * self_consumption_ratio
        exported = yr_production - self_consumed

        # --- Value of self-consumed kWh ---
        esc_factor = (1 + esc) ** yr
        if battery_kwh > 0:
            # Direct self-consumption (midday, off-peak rate)
            direct_frac = BASE_SELF_CONSUMPTION / self_consumption_ratio
            battery_frac = 1 - direct_frac
            self_consumed_value = (
                self_consumed * direct_frac * offpeak * esc_factor
                + self_consumed * battery_frac * peak * esc_factor
            )
        else:
            # All self-consumption at off-peak (midday solar)
            self_consumed_value = self_consumed * offpeak * esc_factor

        # --- Export credits (NEM 3.0 ACC — roughly flat) ---
        export_credits = exported * NEM3_EXPORT_RATE

        # --- Total savings vs. no-solar bill ---
        total_savings = self_consumed_value + export_credits

        # --- Residual grid cost ---
        residual_grid = max(0, no_solar_annual - total_savings)

        # --- Loan payment (only during loan term) ---
        loan_annual = monthly_payment * 12 if yr <= loan_term_years else 0

        # --- Total with-solar cost ---
        solar_annual = loan_annual + residual_grid
        cum_s += solar_annual

        cumulative_no_solar.append(round(cum_ns, 2))
        cumulative_solar.append(round(cum_s, 2))

        if yr == 1:
            year1_savings = no_solar_annual - solar_annual

        # --- Payback detection (linear interpolation) ---
        if payback_years is None and cum_ns > cum_s:
            if yr == 1:
                # Paid back in first year (unlikely but handled)
                payback_years = cum_s / no_solar_annual if no_solar_annual > 0 else 1
            else:
                prev_diff = cumulative_no_solar[yr - 1] - cumulative_solar[yr - 1]
                curr_diff = cum_ns - cum_s
                # prev_diff < 0, curr_diff > 0 → interpolate
                frac = (-prev_diff) / (curr_diff - prev_diff) if (curr_diff - prev_diff) != 0 else 0
                payback_years = (yr - 1) + frac

    # ------------------------------------------------------------------
    # 8. Format payback display
    # ------------------------------------------------------------------
    if payback_years is not None:
        full_years = int(payback_years)
        months = int(round((payback_years - full_years) * 12))
        if months == 12:
            full_years += 1
            months = 0
        if months == 0:
            payback_display = f"{full_years} years"
        else:
            payback_display = f"{full_years} years, {months} months"
    else:
        payback_display = "20+ years"

    # ------------------------------------------------------------------
    # 9. Offset %
    # ------------------------------------------------------------------
    offset_pct = min(100, (annual_production / annual_consumption * 100)) if annual_consumption > 0 else 0

    return SolarResults(
        utility=utility,
        plan_name=tou["plan_name"],
        peak_sun_hours=peak_sun_hours,
        annual_production_kwh=round(annual_production, 0),
        monthly_production_kwh=round(monthly_production, 0),
        annual_consumption_kwh=round(annual_consumption, 0),
        offset_pct=round(offset_pct, 1),
        system_cost=round(system_cost, 2),
        battery_cost=round(battery_cost, 2),
        total_cost=round(total_cost, 2),
        monthly_payment=round(monthly_payment, 2),
        year1_savings=round(year1_savings, 2),
        self_consumption_ratio=round(self_consumption_ratio * 100, 1),
        payback_years=round(payback_years, 2) if payback_years else None,
        payback_display=payback_display,
        years=years,
        cumulative_no_solar=cumulative_no_solar,
        cumulative_solar=cumulative_solar,
    )
