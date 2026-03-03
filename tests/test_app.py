"""
Tests for app.py input validation and form wiring.
Uses the Flask test client (client fixture from conftest.py).
"""

# Valid baseline POST data for a PG&E system
VALID_FORM = {
    "system_kw": "8.0",
    "monthly_bill": "250",
    "zip_code": "94025",
    "battery": "none",
    "custom_battery_kwh": "",
    "financing_type": "loan",
    "cost_per_watt": "2.75",
    "loan_term": "20",
    "loan_apr": "5.5",
    "rate_escalation": "4.0",
    "panel_degradation": "0.5",
    "custom_battery_cost_per_kwh": "900",
}


# ---------------------------------------------------------------------------
# System size validation (lower bound: < 0.5 kW)
# ---------------------------------------------------------------------------

def test_app_rejects_system_kw_below_minimum(client):
    """
    Values below 0.5 kW must be rejected with the 0.5–50 kW error message.
    This covers the fix from <= 0 → < 0.5, which previously allowed e.g. 0.1 kW.
    """
    data = {**VALID_FORM, "system_kw": "0.1"}
    resp = client.post("/", data=data)
    assert resp.status_code == 200
    assert b"0.5" in resp.data


def test_app_rejects_system_kw_zero(client):
    """Zero is below the minimum and must also be rejected."""
    data = {**VALID_FORM, "system_kw": "0"}
    resp = client.post("/", data=data)
    assert resp.status_code == 200
    assert b"0.5" in resp.data


def test_app_accepts_system_kw_at_minimum(client):
    """Exactly 0.5 kW is the lower bound and must succeed (no validation error message)."""
    data = {**VALID_FORM, "system_kw": "0.5"}
    resp = client.post("/", data=data)
    assert resp.status_code == 200
    assert b"System size must be between" not in resp.data


def test_app_rejects_system_kw_above_maximum(client):
    data = {**VALID_FORM, "system_kw": "51"}
    resp = client.post("/", data=data)
    assert resp.status_code == 200
    assert b"50" in resp.data


# ---------------------------------------------------------------------------
# custom_battery_cost_per_kwh wired through to results
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Headline card: monthly cost (loan) vs. payback period (cash)
# ---------------------------------------------------------------------------

def test_app_loan_shows_monthly_cost_section(client):
    """
    When financing_type=loan, the headline card must show 'Monthly Cost with Solar'
    and NOT show 'Estimated Payback Period'.
    """
    data = {**VALID_FORM, "financing_type": "loan"}
    resp = client.post("/", data=data)
    assert resp.status_code == 200
    assert b"Monthly Cost with Solar" in resp.data
    assert b"Estimated Payback Period" not in resp.data


def test_app_cash_shows_payback_period_section(client):
    """
    When financing_type=cash, the headline card must show 'Estimated Payback Period'
    and NOT show 'Monthly Cost with Solar'.
    """
    data = {**VALID_FORM, "financing_type": "cash"}
    resp = client.post("/", data=data)
    assert resp.status_code == 200
    assert b"Estimated Payback Period" in resp.data
    assert b"Monthly Cost with Solar" not in resp.data


# ---------------------------------------------------------------------------
# /calculate JSON endpoint
# ---------------------------------------------------------------------------

_CALC_EXPECTED_KEYS = {
    "financing_type", "monthly_payment", "monthly_utility_bill_with_solar",
    "monthly_bill", "payback_display", "utility", "plan_name", "peak_sun_hours",
    "monthly_production_kwh", "offset_pct", "year1_savings", "total_cost",
    "self_consumption_ratio", "annual_co2_no_solar_lbs", "annual_co2_with_solar_lbs",
    "zero_carbon_pct", "chart", "breakdown",
}


def test_calculate_api_returns_json(client):
    """Valid POST to /calculate returns 200 with all expected top-level keys."""
    resp = client.post("/calculate", data=VALID_FORM)
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/json")
    data = resp.get_json()
    assert data is not None
    assert _CALC_EXPECTED_KEYS.issubset(data.keys())


def test_calculate_api_chart_has_21_points(client):
    """chart.years, chart.noSolar, and chart.withSolar must each have 21 entries (years 0-20)."""
    resp = client.post("/calculate", data=VALID_FORM)
    data = resp.get_json()
    assert len(data["chart"]["years"])    == 21
    assert len(data["chart"]["noSolar"])  == 21
    assert len(data["chart"]["withSolar"]) == 21


def test_calculate_api_invalid_zip_returns_400(client):
    """A non-CA zip returns 400 with an error key."""
    data = {**VALID_FORM, "zip_code": "12345"}
    resp = client.post("/calculate", data=data)
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_calculate_api_missing_system_kw_returns_400(client):
    """Empty system_kw is not a valid float — endpoint must return 400."""
    data = {**VALID_FORM, "system_kw": ""}
    resp = client.post("/calculate", data=data)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_calculate_api_cash_has_zero_monthly_payment(client):
    """Cash purchase must yield monthly_payment == 0."""
    data = {**VALID_FORM, "financing_type": "cash"}
    resp = client.post("/calculate", data=data)
    assert resp.status_code == 200
    assert resp.get_json()["monthly_payment"] == 0


def test_calculate_api_echoes_monthly_bill(client):
    """monthly_bill in the response must equal the submitted form value."""
    data = {**VALID_FORM, "monthly_bill": "300"}
    resp = client.post("/calculate", data=data)
    assert resp.status_code == 200
    assert resp.get_json()["monthly_bill"] == 300.0


def test_app_custom_battery_cost_affects_system_cost(client):
    """
    Submitting a non-default custom_battery_cost_per_kwh with a custom battery
    must change the displayed total system cost compared to the default $900/kWh.
    Proves the field is read from the form and passed to calculate().
    """
    base = {**VALID_FORM, "battery": "custom", "custom_battery_kwh": "10"}

    resp_default = client.post("/", data={**base, "custom_battery_cost_per_kwh": "900"})
    resp_custom = client.post("/", data={**base, "custom_battery_cost_per_kwh": "1200"})

    assert resp_default.status_code == 200
    assert resp_custom.status_code == 200
    # At $900/kWh: battery = $9,000; at $1,200/kWh: battery = $12,000.
    # The rendered page includes the total cost, so the two responses must differ.
    assert resp_default.data != resp_custom.data
