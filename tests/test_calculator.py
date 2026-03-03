"""
Test suite for the Solar Payback Calculator.

Covers: solar production, self-consumption, loan math, cash purchase,
20-year projections, edge cases, and territory lookup.
"""

import pytest
from calculator import calculate
from data import BASE_SELF_CONSUMPTION, CUSTOM_BATTERY_COST_PER_KWH, NEM3_EXPORT_RATE, SYSTEM_LOSSES, TOU_RATES

# Representative zip codes
PGE_ZIP = "94025"   # Menlo Park — PG&E territory, prefix 940 → 5.1 peak sun hours
SCE_ZIP = "90210"   # Beverly Hills — SCE territory, prefix 902 → 5.6 peak sun hours
INVALID_ZIP = "00001"


# ---------------------------------------------------------------------------
# Solar production
# ---------------------------------------------------------------------------

def test_solar_production_formula():
    """annual_production ≈ system_kw × peak_sun_hours × 365 × (1 - losses)"""
    r = calculate(8.0, 250, PGE_ZIP, "none")
    expected = 8.0 * 5.1 * 365 * (1 - SYSTEM_LOSSES)
    assert abs(r.annual_production_kwh - expected) < 1


def test_monthly_production_is_annual_divided_by_12():
    r = calculate(8.0, 250, PGE_ZIP, "none")
    assert abs(r.monthly_production_kwh - r.annual_production_kwh / 12) < 1


def test_larger_system_produces_more():
    r_small = calculate(4.0, 250, PGE_ZIP, "none")
    r_large = calculate(12.0, 250, PGE_ZIP, "none")
    assert r_large.annual_production_kwh > r_small.annual_production_kwh


# ---------------------------------------------------------------------------
# Self-consumption
# ---------------------------------------------------------------------------

def test_self_consumption_without_battery():
    r = calculate(8.0, 250, PGE_ZIP, "none")
    assert r.self_consumption_ratio == round(BASE_SELF_CONSUMPTION * 100, 1)


def test_self_consumption_increases_with_battery():
    r_no_bat = calculate(8.0, 250, PGE_ZIP, "none")
    r_bat = calculate(8.0, 250, PGE_ZIP, "powerwall")
    assert r_bat.self_consumption_ratio > r_no_bat.self_consumption_ratio


def test_self_consumption_bounded_at_max():
    """Even a huge battery should not push self-consumption above 85%."""
    r = calculate(8.0, 250, PGE_ZIP, "custom", custom_battery_kwh=200.0)
    assert r.self_consumption_ratio <= 85.0


# ---------------------------------------------------------------------------
# Loan payment math
# ---------------------------------------------------------------------------

def test_loan_payment_calculation():
    """Verify monthly payment with known values using the standard amortisation formula."""
    cost_per_watt = 2.75
    total = 10.0 * 1000 * cost_per_watt  # $27,500
    monthly_rate = 5.5 / 100 / 12
    n = 20 * 12
    expected = total * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)
    r = calculate(10.0, 300, PGE_ZIP, "none", cost_per_watt=cost_per_watt,
                  loan_term_years=20, loan_apr=5.5)
    assert abs(r.monthly_payment - expected) < 0.01


def test_zero_apr_loan():
    """At 0% APR, monthly payment = total_cost / n_payments."""
    cost_per_watt = 2.75
    total = 8.0 * 1000 * cost_per_watt
    expected = total / (20 * 12)
    r = calculate(8.0, 250, PGE_ZIP, "none", financing_type="loan",
                  loan_apr=0.0, loan_term_years=20, cost_per_watt=cost_per_watt)
    assert abs(r.monthly_payment - expected) < 0.01


def test_higher_apr_increases_monthly_payment():
    r_low = calculate(8.0, 250, PGE_ZIP, "none", loan_apr=3.0)
    r_high = calculate(8.0, 250, PGE_ZIP, "none", loan_apr=9.0)
    assert r_high.monthly_payment > r_low.monthly_payment


# ---------------------------------------------------------------------------
# Cash purchase
# ---------------------------------------------------------------------------

def test_cash_purchase_no_monthly_payment():
    r = calculate(8.0, 250, PGE_ZIP, "none", financing_type="cash")
    assert r.monthly_payment == 0.0


def test_cash_purchase_solar_starts_at_total_cost():
    """The with-solar cumulative cost at year 0 equals the upfront system cost."""
    r = calculate(8.0, 250, PGE_ZIP, "none", financing_type="cash")
    assert r.cumulative_solar[0] == r.total_cost


def test_loan_solar_starts_at_zero():
    r = calculate(8.0, 250, PGE_ZIP, "none", financing_type="loan")
    assert r.cumulative_solar[0] == 0.0


def test_cash_payback_longer_than_loan_chart_crossover():
    """
    Cash purchase payback is longer than loan payback on the chart because
    the full system cost is counted upfront (starting from total_cost) while
    the loan chart starts from $0 and crosses quickly once solar savings exceed
    the monthly loan payment. Both payback values should be positive numbers.
    """
    r_loan = calculate(8.0, 250, PGE_ZIP, "none", financing_type="loan")
    r_cash = calculate(8.0, 250, PGE_ZIP, "none", financing_type="cash")
    assert r_loan.payback_years is not None and r_loan.payback_years > 0
    assert r_cash.payback_years is not None and r_cash.payback_years > 0
    # Cash must recoup the full upfront cost; loan chart starts from $0 so crosses sooner
    assert r_cash.payback_years > r_loan.payback_years


def test_financing_type_stored_in_results():
    r_loan = calculate(8.0, 250, PGE_ZIP, "none", financing_type="loan")
    r_cash = calculate(8.0, 250, PGE_ZIP, "none", financing_type="cash")
    assert r_loan.financing_type == "loan"
    assert r_cash.financing_type == "cash"


# ---------------------------------------------------------------------------
# 20-year series
# ---------------------------------------------------------------------------

def test_20_year_series_has_21_points():
    r = calculate(8.0, 250, PGE_ZIP, "none")
    assert len(r.years) == 21
    assert len(r.cumulative_no_solar) == 21
    assert len(r.cumulative_solar) == 21


def test_years_are_0_to_20():
    r = calculate(8.0, 250, PGE_ZIP, "none")
    assert r.years == list(range(21))


def test_no_solar_starts_at_zero():
    r = calculate(8.0, 250, PGE_ZIP, "none")
    assert r.cumulative_no_solar[0] == 0.0


def test_no_solar_strictly_increases():
    r = calculate(8.0, 250, PGE_ZIP, "none")
    for i in range(1, len(r.cumulative_no_solar)):
        assert r.cumulative_no_solar[i] > r.cumulative_no_solar[i - 1]


def test_no_solar_escalates_at_correct_rate():
    """
    Year 1 uses current (baseline) rates — no escalation yet.
    Year 2 is the first year where escalation compounds.
    Convention: (yr − 1) exponent so year 1 is consistent with Year 1 stat cards.
    The base charge is fixed; only the energy portion of the bill escalates.
    Year 1 still equals monthly_bill × 12 because the esc factor is 1 (exponent 0).
    """
    monthly_bill = 200.0
    escalation = 4.0
    base_charge = TOU_RATES["PGE"]["base_charge_monthly"]
    r = calculate(8.0, monthly_bill, PGE_ZIP, "none", rate_escalation=escalation)
    # Year 1: no escalation (exponent = 0) → equals the full monthly_bill * 12
    expected_year1 = monthly_bill * 12
    actual_year1 = r.cumulative_no_solar[1] - r.cumulative_no_solar[0]
    assert abs(actual_year1 - expected_year1) < 0.01
    # Year 2: only the energy portion escalates; base charge stays fixed
    expected_year2 = base_charge * 12 + (monthly_bill - base_charge) * 12 * (1 + escalation / 100) ** 1
    actual_year2 = r.cumulative_no_solar[2] - r.cumulative_no_solar[1]
    assert abs(actual_year2 - expected_year2) < 0.01


# ---------------------------------------------------------------------------
# Battery cost
# ---------------------------------------------------------------------------

def test_battery_cost_added_to_total():
    r_no_bat = calculate(8.0, 250, PGE_ZIP, "none")
    r_bat = calculate(8.0, 250, PGE_ZIP, "powerwall")
    assert r_bat.total_cost > r_no_bat.total_cost
    assert r_bat.battery_cost > 0


def test_no_battery_zero_battery_cost():
    r = calculate(8.0, 250, PGE_ZIP, "none")
    assert r.battery_cost == 0.0


def test_custom_battery_cost():
    kwh = 10.0
    r = calculate(8.0, 250, PGE_ZIP, "custom", custom_battery_kwh=kwh)
    assert r.battery_cost == kwh * CUSTOM_BATTERY_COST_PER_KWH


def test_custom_battery_cost_per_kwh_parameter():
    """
    Passing a non-default custom_battery_cost_per_kwh to calculate() must
    change battery_cost proportionally, proving the parameter is wired through
    and not silently ignored in favour of the module-level constant.
    """
    kwh = 10.0
    custom_rate = 1200.0  # $/kWh — deliberately different from the $900 default
    r = calculate(8.0, 250, PGE_ZIP, "custom", custom_battery_kwh=kwh,
                  custom_battery_cost_per_kwh=custom_rate)
    assert r.battery_cost == round(kwh * custom_rate, 2)
    # Sanity-check: differs from the default-rate result
    r_default = calculate(8.0, 250, PGE_ZIP, "custom", custom_battery_kwh=kwh)
    assert r.battery_cost != r_default.battery_cost


# ---------------------------------------------------------------------------
# Territory & irradiance
# ---------------------------------------------------------------------------

def test_pge_territory_and_plan():
    r = calculate(8.0, 250, PGE_ZIP, "none")
    assert r.utility == "PGE"
    assert r.plan_name == "E-TOU-C"


def test_sce_territory_and_plan():
    r = calculate(8.0, 250, SCE_ZIP, "none")
    assert r.utility == "SCE"
    assert r.plan_name == "TOU-D-Prime"


def test_invalid_zip_raises():
    with pytest.raises(ValueError, match="not in a supported CA utility territory"):
        calculate(8.0, 250, INVALID_ZIP, "none")


# ---------------------------------------------------------------------------
# Offset %
# ---------------------------------------------------------------------------

def test_offset_pct_bounded_to_100():
    """An oversized system should cap offset at 100%."""
    r = calculate(50.0, 250, PGE_ZIP, "none")
    assert 0 <= r.offset_pct <= 100


def test_offset_increases_with_system_size():
    r_small = calculate(4.0, 300, PGE_ZIP, "none")
    r_large = calculate(12.0, 300, PGE_ZIP, "none")
    assert r_large.offset_pct >= r_small.offset_pct


# ---------------------------------------------------------------------------
# Advanced settings
# ---------------------------------------------------------------------------

def test_higher_cost_per_watt_increases_total_cost():
    r_cheap = calculate(8.0, 250, PGE_ZIP, "none", cost_per_watt=1.50)
    r_expensive = calculate(8.0, 250, PGE_ZIP, "none", cost_per_watt=4.00)
    assert r_expensive.total_cost > r_cheap.total_cost


def test_panel_degradation_reduces_production_over_time():
    """With higher degradation, year-20 production is lower."""
    r_low = calculate(8.0, 250, PGE_ZIP, "none", panel_degradation=0.1)
    r_high = calculate(8.0, 250, PGE_ZIP, "none", panel_degradation=2.0)
    # Higher degradation → less savings → higher cumulative solar cost at year 20
    assert r_high.cumulative_solar[20] >= r_low.cumulative_solar[20]


def test_year1_uses_baseline_no_escalation_no_degradation():
    """
    Year 1 on the chart must be identical regardless of escalation or degradation
    settings, because both factors first compound in year 2 (exponent = yr − 1,
    so yr=1 → exponent 0 → factor 1). This makes chart year 1 consistent with
    the Year 1 stat card baseline.
    """
    r_base = calculate(8.0, 250, PGE_ZIP, "none", rate_escalation=0.0, panel_degradation=0.0)
    r_high = calculate(8.0, 250, PGE_ZIP, "none", rate_escalation=10.0, panel_degradation=2.0)
    # Year 1 no-solar spend must be identical (both = monthly_bill × 12)
    assert r_base.cumulative_no_solar[1] == r_high.cumulative_no_solar[1]
    # Year 1 solar cumulative spend (loan + residual grid) must also be identical
    assert r_base.cumulative_solar[1] == r_high.cumulative_solar[1]
    # But year 2 must diverge when escalation/degradation are non-zero
    assert r_high.cumulative_no_solar[2] > r_base.cumulative_no_solar[2]


# ---------------------------------------------------------------------------
# Monthly utility bill with solar (Year 1 baseline)
# ---------------------------------------------------------------------------

def test_monthly_utility_bill_includes_base_charge():
    """Bill with solar must be at least the utility's fixed base charge."""
    r_pge = calculate(8.0, 250, PGE_ZIP, "none")
    r_sce = calculate(8.0, 250, SCE_ZIP, "none")
    assert r_pge.monthly_utility_bill_with_solar >= TOU_RATES["PGE"]["base_charge_monthly"]
    assert r_sce.monthly_utility_bill_with_solar >= TOU_RATES["SCE"]["base_charge_monthly"]


def test_monthly_utility_bill_floors_at_base_charge_for_oversized_system():
    """A massive system exports everything; bill should floor at the base charge only."""
    r = calculate(50.0, 250, PGE_ZIP, "none")
    assert r.monthly_utility_bill_with_solar == TOU_RATES["PGE"]["base_charge_monthly"]


def test_monthly_utility_bill_decreases_with_larger_system():
    """More solar production → lower residual grid draw → lower bill."""
    r_small = calculate(4.0, 250, PGE_ZIP, "none")
    r_large = calculate(12.0, 250, PGE_ZIP, "none")
    assert r_large.monthly_utility_bill_with_solar <= r_small.monthly_utility_bill_with_solar


def test_monthly_utility_bill_uses_year1_baseline_not_escalated():
    """
    Bill should be the same regardless of rate_escalation setting, because it
    uses Year 1 baseline values (no escalation applied).
    """
    r_low_esc = calculate(8.0, 250, PGE_ZIP, "none", rate_escalation=0.0)
    r_high_esc = calculate(8.0, 250, PGE_ZIP, "none", rate_escalation=10.0)
    assert r_low_esc.monthly_utility_bill_with_solar == r_high_esc.monthly_utility_bill_with_solar


def test_monthly_utility_bill_manual_spot_check():
    """
    Manually verify the TOU-aware formula for a known PG&E case (no battery):
      self_consumed_value = self_consumed * offpeak   (midday solar → off-peak rate)
      export_credits      = exported * NEM3_EXPORT_RATE
      annual_energy_charge = (monthly_bill - base_charge) * 12  (energy-only portion)
      residual_energy      = max(0, annual_energy_charge - self_consumed_value - export_credits)
      expected             = base_charge + residual_energy / 12
    Solar offsets only the energy portion; base charge is always owed.
    """
    system_kw, monthly_bill = 8.0, 250.0
    tou = TOU_RATES["PGE"]
    peak_sun_hours = 5.1  # zip 940xx
    annual_production = system_kw * peak_sun_hours * 365 * (1 - SYSTEM_LOSSES)
    self_consumed = annual_production * BASE_SELF_CONSUMPTION
    exported = annual_production - self_consumed
    self_consumed_value = self_consumed * tou["offpeak"]
    export_credits = exported * NEM3_EXPORT_RATE
    annual_energy_charge = (monthly_bill - tou["base_charge_monthly"]) * 12
    residual_energy = max(0.0, annual_energy_charge - self_consumed_value - export_credits)
    expected = tou["base_charge_monthly"] + residual_energy / 12

    r = calculate(system_kw, monthly_bill, PGE_ZIP, "none")
    assert abs(r.monthly_utility_bill_with_solar - expected) < 0.01


def test_monthly_cost_exceeds_bill_for_large_loan_on_small_bill():
    """
    When the loan payment alone exceeds the original monthly bill, the total
    monthly cost with solar (loan + residual utility) should be greater than
    the original bill — the '$X/mo more than current utility bill' scenario.

    8 kW system at $2.75/W = $22,000 → ~$151/mo loan payment.
    Original bill $80/mo → loan payment alone exceeds the bill.
    """
    monthly_bill = 80.0
    r = calculate(8.0, monthly_bill, PGE_ZIP, "none", financing_type="loan")
    total_monthly_with_solar = r.monthly_payment + r.monthly_utility_bill_with_solar
    assert total_monthly_with_solar > monthly_bill


def test_monthly_cost_does_not_exceed_bill_for_typical_case():
    """
    For a typical high bill ($250/mo) with a standard 8 kW system on loan,
    total monthly cost with solar should be less than the original bill
    (the '$X/mo less than current utility bill' scenario).
    """
    monthly_bill = 250.0
    r = calculate(8.0, monthly_bill, PGE_ZIP, "none", financing_type="loan")
    total_monthly_with_solar = r.monthly_payment + r.monthly_utility_bill_with_solar
    assert total_monthly_with_solar < monthly_bill


# ---------------------------------------------------------------------------
# Year 1 savings — consistent with stat card values
# ---------------------------------------------------------------------------

def test_year1_savings_consistent_with_stat_cards():
    """
    Year 1 savings must equal (monthly_bill - monthly_utility_bill_with_solar
    - monthly_payment) * 12, matching the three stat cards shown to the user.
    """
    monthly_bill = 250.0
    r = calculate(8.0, monthly_bill, PGE_ZIP, "none", financing_type="loan")
    expected = (monthly_bill - r.monthly_utility_bill_with_solar - r.monthly_payment) * 12
    assert abs(r.year1_savings - expected) < 0.01


def test_year1_savings_cash_purchase():
    """For cash purchase, monthly_payment=0 so savings = (bill - utility_bill) * 12."""
    monthly_bill = 250.0
    r = calculate(8.0, monthly_bill, PGE_ZIP, "none", financing_type="cash")
    assert r.monthly_payment == 0.0
    expected = (monthly_bill - r.monthly_utility_bill_with_solar) * 12
    assert abs(r.year1_savings - expected) < 0.01


def test_year1_savings_specific_values():
    """
    Regression test for the reported discrepancy:
    8 kW system, $250/month bill, PG&E, loan.
    Stat cards showed ~$61 utility bill and ~$151 loan.
    year1_savings must equal (250 - utility_bill - loan) * 12, not a loop-derived value.
    """
    r = calculate(8.0, 250.0, PGE_ZIP, "none", financing_type="loan")
    from_stat_cards = (250.0 - r.monthly_utility_bill_with_solar - r.monthly_payment) * 12
    assert abs(r.year1_savings - from_stat_cards) < 0.01


def test_loop_base_charge_always_present_for_oversized_system():
    """
    Bug regression: a 16 kW system (oversized for a $250/month bill) used to
    produce residual_grid = $0 each year, making the solar line flat on the
    chart. The base charge ($24/month PG&E) is always owed regardless of how
    much solar is produced, so the with-solar line must still rise each year.
    """
    r_loan = calculate(16.0, 250, PGE_ZIP, "none", financing_type="loan")
    r_cash = calculate(16.0, 250, PGE_ZIP, "none", financing_type="cash")
    base_charge_annual = TOU_RATES["PGE"]["base_charge_monthly"] * 12
    # Year 1 utility payment (residual_grid) must include at least the base charge
    utility_yr1 = r_cash.cumulative_utility_with_solar[1]
    assert utility_yr1 >= base_charge_annual - 0.01  # tolerance for rounding
    # The with-solar line must increase each year (not flat)
    for i in range(1, len(r_cash.cumulative_solar)):
        assert r_cash.cumulative_solar[i] > r_cash.cumulative_solar[i - 1], \
            f"cumulative_solar[{i}] should be > cumulative_solar[{i-1}] (base charge missing?)"
    # Same check for loan (loan payments + base charge both accumulate)
    for i in range(1, len(r_loan.cumulative_solar)):
        assert r_loan.cumulative_solar[i] > r_loan.cumulative_solar[i - 1]


def test_year1_chart_difference_matches_year1_savings():
    """
    For a LOAN purchase, the chart's year-1 difference
    (cumulative_no_solar[1] - cumulative_solar[1]) must equal year1_savings
    within rounding tolerance ($0.13 = 2 × $0.005 × 12 months + 1 cent).

    Cash purchase is excluded: cumulative_solar[0] starts at the full system
    cost, so the chart's year-1 difference includes the upfront investment and
    is not comparable to the cash-flow year1_savings stat card.
    """
    r = calculate(8.0, 250.0, PGE_ZIP, "none", financing_type="loan")
    chart_diff = r.cumulative_no_solar[1] - r.cumulative_solar[1]
    assert abs(chart_diff - r.year1_savings) < 0.13, (
        f"chart year-1 diff={chart_diff:.2f} vs stat card year1_savings={r.year1_savings:.2f}"
    )


def test_year1_savings_independent_of_escalation():
    """
    year1_savings uses baseline Year 1 values, so changing rate_escalation
    should NOT change year1_savings (escalation only affects the 20-yr loop).
    """
    r_no_esc = calculate(8.0, 250.0, PGE_ZIP, "none", rate_escalation=0.0)
    r_high_esc = calculate(8.0, 250.0, PGE_ZIP, "none", rate_escalation=10.0)
    assert abs(r_no_esc.year1_savings - r_high_esc.year1_savings) < 0.01
