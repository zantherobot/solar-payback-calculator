"""
Solar Payback Calculator — Flask application.
"""

import json

from flask import Flask, jsonify, render_template, request

from calculator import calculate
from data import BATTERY_OPTIONS

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    results = None
    chart_data = None
    breakdown_data = None
    error = None

    # Defaults for form fields
    form = {
        "system_kw": "",
        "monthly_bill": "",
        "zip_code": "",
        "battery": "none",
        "custom_battery_kwh": "",
        "financing_type": "loan",
        # Advanced
        "cost_per_watt": "2.75",
        "loan_term": "20",
        "loan_apr": "5.5",
        "rate_escalation": "4.0",
        "panel_degradation": "0.5",
        "custom_battery_cost_per_kwh": "900",
    }

    if request.method == "POST":
        # Populate form dict from submitted values
        for key in form:
            form[key] = request.form.get(key, form[key])

        try:
            system_kw = float(form["system_kw"])
            monthly_bill = float(form["monthly_bill"])
            zip_code = form["zip_code"].strip()
            battery_key = form["battery"]
            custom_kwh = float(form["custom_battery_kwh"] or 0)
            financing_type = form["financing_type"]

            # Advanced
            cost_per_watt = float(form["cost_per_watt"])
            loan_term = int(form["loan_term"])
            loan_apr = float(form["loan_apr"])
            rate_esc = float(form["rate_escalation"])
            panel_deg = float(form["panel_degradation"])
            custom_batt_cost = float(form["custom_battery_cost_per_kwh"])

            # Basic validation
            if system_kw < 0.5 or system_kw > 50:
                raise ValueError("System size must be between 0.5 and 50 kW.")
            if monthly_bill <= 0:
                raise ValueError("Monthly bill must be a positive number.")
            if len(zip_code) != 5 or not zip_code.isdigit():
                raise ValueError("Please enter a valid 5-digit zip code.")
            if battery_key == "custom" and custom_kwh < 0:
                raise ValueError("Custom battery size must be 0 or greater.")
            if financing_type not in ("loan", "cash"):
                raise ValueError("Financing type must be 'loan' or 'cash'.")

            results = calculate(
                system_kw=system_kw,
                monthly_bill=monthly_bill,
                zip_code=zip_code,
                battery_key=battery_key,
                custom_battery_kwh=custom_kwh,
                financing_type=financing_type,
                cost_per_watt=cost_per_watt,
                loan_term_years=loan_term,
                loan_apr=loan_apr,
                rate_escalation=rate_esc,
                panel_degradation=panel_deg,
                custom_battery_cost_per_kwh=custom_batt_cost,
            )

            chart_data = json.dumps({
                "years": results.years,
                "noSolar": results.cumulative_no_solar,
                "withSolar": results.cumulative_solar,
            })

            breakdown_data = json.dumps({
                "noSolar10": results.cumulative_no_solar[10],
                "noSolar20": results.cumulative_no_solar[20],
                "utilityWithSolar10": results.cumulative_utility_with_solar[10],
                "utilityWithSolar20": results.cumulative_utility_with_solar[20],
                "solarCompany10": results.cumulative_solar_company[10],
                "solarCompany20": results.cumulative_solar_company[20],
            })

        except ValueError as e:
            error = str(e)
        except Exception:
            error = "Something went wrong with the calculation. Please check your inputs."

    battery_options = [
        (key, label) for key, (label, _, _) in BATTERY_OPTIONS.items()
    ]

    return render_template(
        "index.html",
        form=form,
        results=results,
        chart_data=chart_data,
        breakdown_data=breakdown_data,
        error=error,
        battery_options=battery_options,
    )


@app.route("/calculate", methods=["POST"])
def calculate_api():
    """JSON endpoint for live recalculation without a page reload."""
    defaults = {
        "system_kw": "",
        "monthly_bill": "",
        "zip_code": "",
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
    form = {k: request.form.get(k, v) for k, v in defaults.items()}

    try:
        system_kw = float(form["system_kw"])
        monthly_bill = float(form["monthly_bill"])
        zip_code = form["zip_code"].strip()
        battery_key = form["battery"]
        custom_kwh = float(form["custom_battery_kwh"] or 0)
        financing_type = form["financing_type"]
        cost_per_watt = float(form["cost_per_watt"])
        loan_term = int(form["loan_term"])
        loan_apr = float(form["loan_apr"])
        rate_esc = float(form["rate_escalation"])
        panel_deg = float(form["panel_degradation"])
        custom_batt_cost = float(form["custom_battery_cost_per_kwh"])

        if system_kw < 0.5 or system_kw > 50:
            raise ValueError("System size must be between 0.5 and 50 kW.")
        if monthly_bill <= 0:
            raise ValueError("Monthly bill must be a positive number.")
        if len(zip_code) != 5 or not zip_code.isdigit():
            raise ValueError("Please enter a valid 5-digit zip code.")
        if battery_key == "custom" and custom_kwh < 0:
            raise ValueError("Custom battery size must be 0 or greater.")
        if financing_type not in ("loan", "cash"):
            raise ValueError("Financing type must be 'loan' or 'cash'.")

        r = calculate(
            system_kw=system_kw,
            monthly_bill=monthly_bill,
            zip_code=zip_code,
            battery_key=battery_key,
            custom_battery_kwh=custom_kwh,
            financing_type=financing_type,
            cost_per_watt=cost_per_watt,
            loan_term_years=loan_term,
            loan_apr=loan_apr,
            rate_escalation=rate_esc,
            panel_degradation=panel_deg,
            custom_battery_cost_per_kwh=custom_batt_cost,
        )

        return jsonify({
            "financing_type": r.financing_type,
            "monthly_payment": r.monthly_payment,
            "monthly_utility_bill_with_solar": r.monthly_utility_bill_with_solar,
            "monthly_bill": monthly_bill,
            "payback_display": r.payback_display,
            "utility": r.utility,
            "plan_name": r.plan_name,
            "peak_sun_hours": r.peak_sun_hours,
            "monthly_production_kwh": r.monthly_production_kwh,
            "offset_pct": r.offset_pct,
            "year1_savings": r.year1_savings,
            "total_cost": r.total_cost,
            "self_consumption_ratio": r.self_consumption_ratio,
            "annual_co2_no_solar_lbs": r.annual_co2_no_solar_lbs,
            "annual_co2_with_solar_lbs": r.annual_co2_with_solar_lbs,
            "zero_carbon_pct": r.zero_carbon_pct,
            "chart": {
                "years": r.years,
                "noSolar": r.cumulative_no_solar,
                "withSolar": r.cumulative_solar,
            },
            "breakdown": {
                "noSolar10": r.cumulative_no_solar[10],
                "noSolar20": r.cumulative_no_solar[20],
                "utilityWithSolar10": r.cumulative_utility_with_solar[10],
                "utilityWithSolar20": r.cumulative_utility_with_solar[20],
                "solarCompany10": r.cumulative_solar_company[10],
                "solarCompany20": r.cumulative_solar_company[20],
            },
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Something went wrong with the calculation. Please check your inputs."}), 500


if __name__ == "__main__":
    import os
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug, host="0.0.0.0", port=port)
