# Solar Calculator

A web app for California homeowners to estimate the financial and environmental impact of going solar under NEM 3.0 rules. Enter your system size, monthly bill, zip code, and financing preference — results update live.

Built with Flask + Chart.js. Deployed on Railway.

## Features

- **Loan or cash purchase** — headline result adapts to financing type (monthly cost comparison vs. payback period)
- **20-year cumulative cost chart** — no-solar vs. with-solar cost curves with crossover point
- **"Where Your Money Goes" breakdown** — year-10 and year-20 snapshots of spend split between utility and solar company
- **Battery storage options** — Tesla Powerwall 3, Enphase IQ 5P, Franklin WH, or custom kWh
- **Carbon emissions card** — annual CO₂ avoided based on utility grid mix (CEC 2024 Power Content Label)
- **Live updates** — results recalculate on input change, no page reload required
- **Advanced settings** — override cost/watt, loan terms, rate escalation, panel degradation, battery cost

## Territories Covered

PG&E and SCE zip codes. NEM 3.0 (Net Billing Tariff) rules apply.

## Running Locally

```bash
pip install -r requirements.txt
python app.py
# Visit http://localhost:5000
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## Tech Stack

- **Backend**: Python / Flask
- **Templates**: Jinja2
- **Charts**: Chart.js
- **Deployment**: Railway (auto-deploy on push to `staging` / `main`)

## Calculation Notes

- Solar production uses a PVWatts-style formula: `annual_kWh = system_kW × peak_sun_hours × 365 × (1 - 0.14 losses)`
- Self-consumed solar is valued at TOU retail rates; exported solar at the NEM 3.0 ACC rate (~$0.05/kWh)
- Battery increases self-consumption ratio (40% → up to 85%) and shifts discharged energy to peak-rate avoidance
- 20-year projections apply 4% annual rate escalation (adjustable) and 0.5%/yr panel degradation (adjustable)
- No federal ITC applied (not applicable in 2026)

See [SPEC.md](SPEC.md) for full methodology.

## Author

Built by [Henry White](https://www.linkedin.com/in/henry-a-white/) using [Claude Code](https://claude.ai/code).
