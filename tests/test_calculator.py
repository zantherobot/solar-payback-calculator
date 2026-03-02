"""
Test suite for the Solar Payback Calculator.

Covers: solar production, self-consumption, loan math, cash purchase,
20-year projections, edge cases, and territory lookup.
"""

import pytest
from calculator import calculate
from data import BASE_SELF_CONSUMPTION, CUSTOM_BATTERY_COST_PER_KWH, SYSTEM_LOSSES

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
    """Year 1 no-solar cost should be bill × 12 × (1 + escalation)^1."""
    monthly_bill = 200.0
    escalation = 4.0
    r = calculate(8.0, monthly_bill, PGE_ZIP, "none", rate_escalation=escalation)
    expected_year1 = monthly_bill * 12 * (1 + escalation / 100) ** 1
    actual_year1 = r.cumulative_no_solar[1] - r.cumulative_no_solar[0]
    assert abs(actual_year1 - expected_year1) < 0.01


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
