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
    """Exactly 0.5 kW is the lower bound and must succeed (no error banner)."""
    data = {**VALID_FORM, "system_kw": "0.5"}
    resp = client.post("/", data=data)
    assert resp.status_code == 200
    assert b"error-banner" not in resp.data


def test_app_rejects_system_kw_above_maximum(client):
    data = {**VALID_FORM, "system_kw": "51"}
    resp = client.post("/", data=data)
    assert resp.status_code == 200
    assert b"50" in resp.data


# ---------------------------------------------------------------------------
# custom_battery_cost_per_kwh wired through to results
# ---------------------------------------------------------------------------

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
