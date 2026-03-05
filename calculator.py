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
    FOSSIL_EMISSION_FACTOR_LBS_KWH,
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
    financing_type: str  # "loan" or "cash"
    system_cost: float
    battery_cost: float
    total_cost: float
    monthly_payment: float  # 0 for cash purchase
    monthly_utility_bill_with_solar: float  # projected Year 1 utility bill after solar
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
    # Cost breakdown: what goes to utility vs. solar company (index 0–20)
    cumulative_utility_with_solar: list[float]
    cumulative_solar_company: list[float]

    # Carbon (Year 1 baseline, lbs CO2)
    grid_emission_rate: float       # lbs CO2 per kWh consumed from the grid
    zero_carbon_pct: float          # fraction of grid that is zero-carbon (0–1)
    annual_co2_no_solar_lbs: float  # without solar
    annual_co2_with_solar_lbs: float  # with solar (net grid draw × emission rate)


def calculate(
    system_kw: float,
    monthly_bill: float,
    zip_code: str,
    battery_key: str,
    custom_battery_kwh: float = 0,
    financing_type: str = "loan",  # "loan" or "cash"
    # Advanced settings
    cost_per_watt: float = 2.75,
    loan_term_years: int = 20,
    loan_apr: float = 5.5,
    rate_escalation: float = 4.0,
    panel_degradation: float = 0.5,
    custom_battery_cost_per_kwh: float = CUSTOM_BATTERY_COST_PER_KWH,
) -> SolarResults:
    # ------------------------------------------------------------------
    # 1. Location lookups
    # ------------------------------------------------------------------
    utility = get_utility(zip_code)
    if utility is None:
        raise ValueError(f"Zip code {zip_code} is not in a supported CA utility territory.")
    peak_sun_hours = get_peak_sun_hours(zip_code)
    if peak_sun_hours is None:
        raise ValueError(f"Zip code {zip_code} is not in a supported CA utility territory.")
    tou = TOU_RATES[utility]
    zero_carbon_pct = tou["zero_carbon_pct"]
    grid_emission_rate = (1 - zero_carbon_pct) * FOSSIL_EMISSION_FACTOR_LBS_KWH

    # ------------------------------------------------------------------
    # 2. Battery info
    # ------------------------------------------------------------------
    if battery_key == "custom":
        battery_kwh = custom_battery_kwh
        battery_cost = battery_kwh * custom_battery_cost_per_kwh
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

    if financing_type == "cash":
        monthly_payment = 0.0
    else:
        monthly_rate = loan_apr / 100 / 12
        n_payments = loan_term_years * 12
        if monthly_rate > 0:
            monthly_payment = total_cost * (
                monthly_rate * (1 + monthly_rate) ** n_payments
            ) / ((1 + monthly_rate) ** n_payments - 1)
        else:
            monthly_payment = total_cost / n_payments

    # ------------------------------------------------------------------
    # 7. Projected Year 1 monthly utility bill with solar
    # ------------------------------------------------------------------
    # Uses baseline values (no rate escalation, no panel degradation).
    # Self-consumed kWh are valued at the TOU off-peak rate (midday solar
    # displaces off-peak purchases). Same methodology as the 20-year loop,
    # so the stat card and chart are consistent at year 1.
    # Solar can only offset the energy portion of the bill; the base charge
    # (grid participation / customer charge) is always owed.
    base_charge = tou["base_charge_monthly"]
    offpeak = tou["offpeak"]
    peak = tou["peak"]
    self_consumed_yr1 = annual_production * self_consumption_ratio
    exported_yr1 = annual_production - self_consumed_yr1
    export_credits_yr1 = exported_yr1 * NEM3_EXPORT_RATE
    if battery_kwh > 0:
        direct_frac = BASE_SELF_CONSUMPTION / self_consumption_ratio
        battery_frac = 1 - direct_frac
        self_consumed_value_yr1 = (
            self_consumed_yr1 * direct_frac * offpeak
            + self_consumed_yr1 * battery_frac * peak
        )
    else:
        self_consumed_value_yr1 = self_consumed_yr1 * offpeak
    annual_energy_charge_yr1 = (monthly_bill - base_charge) * 12
    residual_energy_yr1 = max(0.0, annual_energy_charge_yr1 - self_consumed_value_yr1 - export_credits_yr1)
    monthly_utility_bill_with_solar = base_charge + residual_energy_yr1 / 12

    # Year 1 net cash-flow savings: what the homeowner stops paying to the utility,
    # minus what they now pay toward the loan. Computed from the rounded display
    # values so the arithmetic is exactly consistent with the three stat cards.
    monthly_utility_bill_with_solar_r = round(monthly_utility_bill_with_solar, 2)
    monthly_payment_r = round(monthly_payment, 2)
    year1_savings = (monthly_bill - monthly_utility_bill_with_solar_r - monthly_payment_r) * 12

    # ------------------------------------------------------------------
    # 8. 20-year projection
    # ------------------------------------------------------------------
    esc = rate_escalation / 100
    deg = panel_degradation / 100
    # offpeak and peak already set in section 7 above

    years = list(range(0, 21))
    cumulative_no_solar = [0.0]
    # Cash purchase: upfront payment at year 0; loan: payments spread over time
    initial_solar_cost = round(total_cost, 2) if financing_type == "cash" else 0.0
    cumulative_solar = [initial_solar_cost]
    # Cost breakdown: utility payments vs. solar-company payments
    cumulative_utility_with_solar = [0.0]
    cumulative_solar_company = [initial_solar_cost]
    cum_ns = 0.0
    cum_s = initial_solar_cost
    cum_u = 0.0   # cumulative utility payments (with solar)
    cum_sc = initial_solar_cost  # cumulative solar company payments
    payback_years = None

    for yr in range(1, 21):
        # --- No-solar annual cost ---
        # Year 1 uses current (baseline) rates; escalation compounds from year 2.
        # (yr - 1) exponent: yr=1 → factor 1 (no escalation), yr=2 → (1+esc)^1, etc.
        # The base charge is held fixed (it is a regulated flat fee); only the energy
        # portion escalates.  This matches how the with-solar path treats base_charge.
        base_charge_annual = base_charge * 12
        no_solar_annual = base_charge_annual + (monthly_bill - base_charge) * 12 * (1 + esc) ** (yr - 1)
        cum_ns += no_solar_annual

        # --- Solar production this year (degradation) ---
        # Same convention: year 1 at full rated output; degradation compounds from year 2.
        yr_production = annual_production * (1 - deg) ** (yr - 1)
        self_consumed = yr_production * self_consumption_ratio
        exported = yr_production - self_consumed

        # --- Value of self-consumed kWh ---
        esc_factor = (1 + esc) ** (yr - 1)
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

        # --- Residual grid cost ---
        # Solar can only offset the energy portion of the bill; the base charge
        # (fixed grid participation / customer charge) is always owed regardless
        # of how much the system produces. Without this floor, an oversized system
        # drives residual_grid to $0, hiding the monthly base charge on the chart.
        annual_energy = no_solar_annual - base_charge_annual
        residual_energy = max(0, annual_energy - self_consumed_value - export_credits)
        residual_grid = base_charge_annual + residual_energy

        # --- Loan payment (only during loan term; zero for cash purchase) ---
        loan_annual = monthly_payment * 12 if (financing_type == "loan" and yr <= loan_term_years) else 0

        # --- Total with-solar cost ---
        solar_annual = loan_annual + residual_grid
        cum_s += solar_annual

        cumulative_no_solar.append(round(cum_ns, 2))
        cumulative_solar.append(round(cum_s, 2))
        cum_u += residual_grid
        cum_sc += loan_annual
        cumulative_utility_with_solar.append(round(cum_u, 2))
        cumulative_solar_company.append(round(cum_sc, 2))

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
    # 9. Format payback display
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
    # 10. Offset %
    # ------------------------------------------------------------------
    offset_pct = min(100, (annual_production / annual_consumption * 100)) if annual_consumption > 0 else 0

    # ------------------------------------------------------------------
    # 11. Carbon (Year 1 baseline)
    # ------------------------------------------------------------------
    annual_co2_no_solar_lbs = annual_consumption * grid_emission_rate
    net_grid_kwh = max(0.0, annual_consumption - annual_production)
    annual_co2_with_solar_lbs = net_grid_kwh * grid_emission_rate

    return SolarResults(
        utility=utility,
        plan_name=tou["plan_name"],
        peak_sun_hours=peak_sun_hours,
        annual_production_kwh=round(annual_production, 0),
        monthly_production_kwh=round(monthly_production, 0),
        annual_consumption_kwh=round(annual_consumption, 0),
        offset_pct=round(offset_pct, 1),
        financing_type=financing_type,
        system_cost=round(system_cost, 2),
        battery_cost=round(battery_cost, 2),
        total_cost=round(total_cost, 2),
        monthly_payment=monthly_payment_r,
        monthly_utility_bill_with_solar=monthly_utility_bill_with_solar_r,
        year1_savings=round(year1_savings, 2),
        self_consumption_ratio=round(self_consumption_ratio * 100, 1),
        payback_years=round(payback_years, 2) if payback_years else None,
        payback_display=payback_display,
        years=years,
        cumulative_no_solar=cumulative_no_solar,
        cumulative_solar=cumulative_solar,
        cumulative_utility_with_solar=cumulative_utility_with_solar,
        cumulative_solar_company=cumulative_solar_company,
        grid_emission_rate=round(grid_emission_rate, 4),
        zero_carbon_pct=zero_carbon_pct,
        annual_co2_no_solar_lbs=round(annual_co2_no_solar_lbs, 1),
        annual_co2_with_solar_lbs=round(annual_co2_with_solar_lbs, 1),
    )
