# Solar Payback Calculator — Product Spec

## Overview

A public-facing web app that helps California homeowners estimate the financial payback of going solar (with optional battery storage) under NEM 3.0 rules. The first iteration is a simple, stateless calculator — no accounts or saved data.

## Tech Stack

- **Backend**: Python (Flask) — lightweight, fast to build, easy to extend later
- **Frontend**: Server-rendered HTML templates (Jinja2) with minimal JS for interactivity
- **Styling**: Simple, clean CSS (no framework dependency to start)
- **Deployment**: Single-process Flask app, easy to containerize later

> *Why Flask over a JS framework?* For a calculator with no persistent state, server-side rendering keeps things simple. We can always add a React/Vue frontend later if needed.

---

## User Inputs

| Input | Type | Details |
|---|---|---|
| **System size** | Number (kW) | Manual entry, e.g. 4–15 kW |
| **Avg. monthly electricity bill** | Currency ($) | Pre-solar monthly bill |
| **Zip code** | Text (5-digit) | Used to look up solar irradiance and utility rate/TOU schedule |
| **Battery** | Dropdown select | `None`, `Tesla Powerwall 3 (13.5 kWh)`, `Enphase IQ 5P (5 kWh)`, `Franklin WH (13.6 kWh)`, `Custom (enter kWh)` |

---

## Outputs

### Primary

- **Estimated payback period** (years + months)
- **20-year cost comparison table/chart**: cumulative payments to electric company (no solar) vs. cumulative payments to solar company (loan) over 20 years

### Secondary (displayed alongside)

- Estimated monthly solar production (kWh)
- Estimated monthly electricity offset (%)
- Estimated Year 1 savings
- Net system cost

---

## Key Calculations & Assumptions

### Solar Production

- Use **NREL PVWatts**-style estimates based on zip code → solar irradiance (peak sun hours)
- Default assumptions: south-facing roof, 20° tilt, 14% system losses (inverter, wiring, soiling)
- Formula: `annual_kWh = system_kW × peak_sun_hours × 365 × (1 - losses)`

### NEM 3.0 (CA Net Billing Tariff) Rules

- Export credits are based on the **Avoided Cost Calculator (ACC)** — significantly lower than retail rate
- Export credit values vary by time of day and month
- Simplified model for v1:
  - **Self-consumed solar**: valued at full retail TOU rate (avoided cost to homeowner)
  - **Exported solar**: valued at ~$0.04–0.08/kWh (ACC approximation, varies by hour)
  - Use a weighted average export rate rather than hour-by-hour simulation in v1
- Self-consumption ratio estimate: ~40% without battery, ~70–80% with battery

### Battery & TOU Load Shifting

- If battery is included:
  - Assume battery charges from excess midday solar (when export credits are low)
  - Battery discharges during peak TOU hours (4–9 PM) to offset high-rate grid consumption
  - Increases self-consumption ratio, reducing low-value exports
  - Round-trip efficiency: 90%
- TOU schedule: Use SCE TOU-D-Prime or PG&E E-TOU-C as default (based on zip code → utility territory)
  - Off-peak: ~$0.25/kWh
  - Peak (4–9 PM): ~$0.45–0.55/kWh
  - These are hardcoded defaults for v1, noted as approximate

### Financial Assumptions (Defaults)

| Assumption | Default Value |
|---|---|
| System cost | $2.75/watt (before incentives) |
| Solar loan term | 20 years |
| Solar loan APR | 5.5% |
| Annual electricity rate escalation | 4% |
| Annual solar panel degradation | 0.5%/year |
| Battery cost | Included in common battery presets (~$10,000–$15,000) |

### 20-Year Comparison Logic

**No Solar path:**
- `year_N_cost = monthly_bill × 12 × (1 + escalation_rate)^N`
- Cumulate over 20 years

**With Solar path:**
- Monthly loan payment (fixed, based on total system cost)
- Plus residual grid cost (energy not offset by solar/battery, at TOU rates)
- Grid costs escalate annually; loan payment stays fixed
- Cumulate over 20 years

**Payback period** = the year where cumulative solar savings exceed cumulative solar costs (i.e., the crossover point).

---

## UI / UX

### Layout

1. **Input section** (top or left): Clean form with the 4 inputs + "Calculate" button
2. **Results section** (below or right):
   - Big headline number: "Estimated payback: **X years**"
   - 20-year comparison chart (bar or line chart showing cumulative cost curves)
   - Summary stats cards (monthly production, offset %, year-1 savings, net cost)
3. **Disclaimer footer**: "Estimates only. Actual results vary based on roof orientation, shading, utility rates, and other factors."

### Chart

- Simple line chart (two lines: "Without Solar" vs. "With Solar") using Chart.js
- X-axis: Years 0–20
- Y-axis: Cumulative cost ($)
- Crossover point visually highlighted

---

## Scope Boundaries (v1)

### In Scope
- CA-specific NEM 3.0 simplified model
- SCE and PG&E rate territories (lookup by zip)
- Loan financing model
- Common battery options with TOU load shifting estimate

### Out of Scope (Future Iterations)
- Other states / utility territories
- Hourly simulation (8,760-hour model)
- SDG&E territory
- Cash purchase option
- Federal/state/local incentives
- Roof orientation / shading inputs
- API integration with live PVWatts or utility rate databases
- User accounts / saved scenarios
- PDF report export

---

## Data Sources (v1 — Hardcoded/Simplified)

| Data | Source | Approach in v1 |
|---|---|---|
| Solar irradiance by zip | NREL / PVWatts | Lookup table for CA zip code ranges (map to ~5.0–6.0 peak sun hours) |
| TOU rates | PG&E / SCE | Hardcoded rate tables for E-TOU-C and TOU-D-Prime |
| NEM 3.0 export credits | CPUC ACC | Simplified average export credit by TOU period |
| Utility territory by zip | PG&E / SCE maps | Simple zip code → utility mapping table |

---

## Advanced Settings

A collapsible "Advanced Settings" panel below the main inputs, collapsed by default. Allows power users to override financial assumptions:

| Setting | Default | Range |
|---|---|---|
| System cost ($/watt) | $2.75 | $1.50–$5.00 |
| Solar loan term (years) | 20 | 5–30 |
| Solar loan APR (%) | 5.5% | 0–12% |
| Annual electricity rate escalation (%) | 4% | 0–10% |
| Annual panel degradation (%) | 0.5% | 0–2% |

---

## Branding & Visual Design

**Theme**: Contemporary green energy — clean, professional, trustworthy.

- **Color palette**:
  - Primary: Deep green (#2D6A4F) — headers, buttons, accents
  - Secondary: Warm amber/gold (#F4A261) — highlights, chart crossover point, CTAs
  - Background: Light off-white (#FAFAF5) with white (#FFFFFF) cards
  - Text: Dark charcoal (#1B1B1B)
  - Subtle accents: Soft sage (#95D5B2) for secondary elements
- **Typography**: Clean sans-serif (Inter or similar), generous whitespace
- **Tone**: Modern, approachable, data-forward — not corporate, not startup-gimmicky
- **Chart colors**: Green line (with solar) vs. muted gray line (without solar)

---

## Resolved Decisions

1. **Loan only** for v1 (no cash purchase scenario)
2. **Advanced Settings** included — collapsible panel for adjusting financial assumptions
3. **Federal ITC removed** — no longer applicable in 2026
4. **Branding**: Contemporary green energy professional
