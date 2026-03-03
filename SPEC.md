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
- Monthly loan payment (loan financing) or "Cash Purchase" label (cash)
- Self-consumption ratio (%)

---

## Key Calculations & Assumptions

### Solar Production

- Use **NREL PVWatts**-style estimates based on zip code → solar irradiance (peak sun hours)
- Default assumptions: south-facing roof, 20° tilt, 14% system losses (inverter, wiring, soiling)
- Formula: `annual_kWh = system_kW × peak_sun_hours × 365 × (1 - losses)`

### Consumption Estimate (kWh)

Annual household consumption is back-calculated from the monthly bill:

```
annual_consumption_kwh = (monthly_bill × 12) / weighted_avg_rate
```

**Known simplification:** this divides the *total* bill (including the fixed base charge) by the energy rate, slightly overstating kWh by roughly `base_charge × 12 / avg_rate` (~800 kWh/year for PG&E at $250/month). This only affects the `offset_pct` display and carbon stats — the dollar-based financial projections derive bill amounts directly from the inputs and are not affected.

### NEM 3.0 (CA Net Billing Tariff) Rules

- Export credits are based on the **Avoided Cost Calculator (ACC)** — significantly lower than retail rate
- Export credit values vary by time of day and month
- Simplified model for v1:
  - **Self-consumed solar**: valued at full retail TOU rate (avoided cost to homeowner)
  - **Exported solar**: valued at ~$0.04–0.08/kWh (ACC approximation, varies by hour)
  - Use a weighted average export rate rather than hour-by-hour simulation in v1
  - Export credits are held **flat** across all 20 years (no escalation). NEM 3.0 ACC rates are set periodically by the CPUC and have remained roughly stable; applying escalation would overstate future export value and is not supported by current rate trends.
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
| Financing | Loan (user can switch to Cash Purchase) |
| Solar loan term | 20 years |
| Solar loan APR | 5.5% |
| Annual electricity rate escalation | 4% |
| Annual solar panel degradation | 0.5%/year |
| Battery cost | Included in common battery presets (~$7,000–$13,500); Custom battery default: **$900/kWh installed** |

#### Cash Purchase Model
When the user selects cash purchase, the full system cost is applied at year 0 on the 20-year chart. No monthly loan payment is included. Payback is the year cumulative utility bills (without solar) first exceed the cumulative solar cost (upfront + residual grid bills). Cash payback is typically **longer** than loan payback for the same system, because `cumulative_solar[0]` starts at the full upfront cost; the no-solar line must climb by that entire amount before crossing the solar cost curve, whereas the loan chart's two lines both start at $0 and cross earlier.

### 20-Year Comparison Logic

**No Solar path:**
- The base charge is a regulated flat fee; only the energy portion of the bill escalates. Both paths (no-solar and with-solar) treat base charge as fixed, so the comparison is symmetric:
  `year_N_cost = base_charge × 12 + (monthly_bill − base_charge) × 12 × (1 + escalation_rate)^(N−1)`
- Year 1 uses current (baseline) rates — no escalation yet. Escalation first compounds in year 2.
- Cumulate over 20 years

**With Solar path:**
- Monthly loan payment (fixed, based on total system cost)
- Plus residual grid cost (energy not offset by solar/battery, at TOU rates)
- Grid costs escalate annually from year 2; loan payment stays fixed
- Solar production degrades from year 2 (year 1 is at full rated output)
- Cumulate over 20 years

**Why (N−1)?** Year 1 represents the first full year of ownership at today's rates and full panel output, consistent with the "Year 1 baseline" stat cards. Escalation and degradation compound starting in year 2. This is the standard convention for consumer-facing solar calculators (e.g., EnergySage, SunPower).

**Note on year 1 stat card vs. chart consistency:** The chart's year 1 difference (`no_solar[1] − solar[1]`) will be close to but not identical to `year1_savings` on the stat card. Both use year 1 baseline values, but the chart's solar side values self-consumed energy at the off-peak TOU rate (midday solar displaces off-peak consumption per NEM 3.0), while the stat card uses the average blended rate for the residual grid charge. This methodological difference is intentional: the stat card uses a simpler, bill-offset model consistent with how homeowners read their utility bill; the chart uses a TOU-aware model that more accurately reflects time-of-use savings over 20 years.

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

### Charts

**20-year cumulative cost line chart:**
- Two lines: "Without Solar" vs. "With Solar" using Chart.js
- X-axis: Years 0–20; Y-axis: Cumulative cost ($)
- Crossover point highlighted (enlarged data point on both lines)

**"Where Your Money Goes" stacked bar chart** (displayed below the line chart):
- Year-10 and Year-20 snapshots of cumulative spend
- Three segments: "Without Solar — utility payments" (gray), "With Solar — to solar company" (amber), "With Solar — to utility" (green)
- Tooltip shows each segment value and a combined "Total with solar" footer for the solar stack

---

## Scope Boundaries (v1)

### In Scope
- CA-specific NEM 3.0 simplified model
- SCE and PG&E rate territories (lookup by zip)
- Loan financing model
- Cash purchase financing model
- Common battery options with TOU load shifting estimate

### Out of Scope (Future Iterations)
- Other states / utility territories
- Hourly simulation (8,760-hour model)
- SDG&E territory
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

A collapsible "Advanced Settings" panel below the main inputs, collapsed by default. Allows power users to override financial assumptions. The panel **auto-opens** when the page re-renders after a submission that used any non-default value, so the user always sees the settings that produced their result. The "Loan Term" and "Loan APR" fields are **hidden** when Cash Purchase is selected (they are irrelevant and would otherwise clutter the form). The "Custom Battery Cost" field is **always visible** regardless of battery selection — it documents a key assumption users may want to verify even when reviewing results for a preset battery.

| Setting | Default | Range |
|---|---|---|
| System cost ($/watt) | $2.75 | $1.50–$5.00 |
| Solar loan term (years) | 20 | 5–30 |
| Solar loan APR (%) | 5.5% | 0–12% |
| Annual electricity rate escalation (%) | 4% | 0–10% |
| Annual panel degradation (%) | 0.5% | 0–2% |
| Custom battery cost ($/kWh installed) | $900 | $500–$1,500 |

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

## Projected Monthly Utility Bill with Solar

Displayed as a stat card labeled **"Monthly Utility Bill (Yr 1 est.)"** — the estimated monthly electricity bill a homeowner will owe their utility in Year 1 after solar is installed.

### Components

**1. Base charge** — fixed monthly customer charge owed regardless of solar production:

| Utility | Amount |
|---|---|
| PG&E | $24/month |
| SCE | $10/month |

Stored as `base_charge_monthly` in `TOU_RATES` in `data.py`.

**2. Self-consumed solar value** — solar used on-site, valued at TOU rates:

```
# No battery: all self-consumption is direct midday use → off-peak rate
self_consumed_value = self_consumed_kwh × offpeak_rate

# With battery: direct midday use at off-peak, stored portion discharged at peak
direct_frac = BASE_SELF_CONSUMPTION / self_consumption_ratio
battery_frac = 1 − direct_frac
self_consumed_value = self_consumed_kwh × direct_frac  × offpeak_rate
                    + self_consumed_kwh × battery_frac × peak_rate
```

Using the TOU rate at the time of consumption (off-peak for midday, peak for battery discharge) gives the most accurate avoided-cost figure, and keeps the stat card methodology consistent with the 20-year loop.

**3. NEM 3.0 export credit offset:**

```
export_credits = exported_kwh × NEM3_EXPORT_RATE  ($0.05/kWh)
```

Where `exported_kwh = annual_production_kwh − self_consumed_kwh`

**4. Monthly projected utility bill:**

```
annual_energy_charge = (monthly_bill − base_charge) × 12   # energy-only portion of current bill
residual_energy      = max(0, annual_energy_charge − self_consumed_value − export_credits)
monthly_utility_bill = base_charge + residual_energy / 12
```

The energy charge is decomposed from the total bill so that solar savings only offset the energy portion. The base charge is always owed on top. The `max(0, ...)` ensures the residual energy charge can't go negative (NEM 3.0 does not pay out net surplus monthly).

### Notes

- Uses **Year 1 baseline values**: no rate escalation, no panel degradation — representing the bill in the first year after installation
- If solar over-generates relative to consumption, the bill floors at `base_charge`
- Stored as `monthly_utility_bill_with_solar` on `SolarResults`

### Battery Effect on the Bill

A battery increases `self_consumption_ratio` (40% → up to 85%) and shifts the value of the additional self-consumed kWh from the off-peak rate ($0.30) to the peak rate ($0.49). Both effects reduce the residual energy charge, lowering the bill — and the peak-rate avoidance is what makes battery add-ons financially attractive under NEM 3.0.

Self-consumption ratio with battery:
```
daily_excess         = daily_production × (1 − BASE_SELF_CONSUMPTION)
daily_battery_capture = min(battery_kwh × BATTERY_ROUND_TRIP_EFF, daily_excess)
self_consumption_ratio = min(BASE_SELF_CONSUMPTION + daily_battery_capture / daily_production,
                             MAX_SELF_CONSUMPTION)
```
Constants: `BASE_SELF_CONSUMPTION = 0.40`, `MAX_SELF_CONSUMPTION = 0.85`, `BATTERY_ROUND_TRIP_EFF = 0.90`.

**Known simplification:** `self_consumption_ratio` is computed at year-1 full output and applied unchanged to degraded production in all subsequent years. In practice, the ratio would rise slightly as panels degrade (same household load, less supply), underestimating self-consumed value in years 10–20. This is a conservative simplification.

### Consistency with Year 1 Savings

`year1_savings` is derived from the same baseline figures for consistency across all Year 1 stat cards:

```
year1_savings = (monthly_bill − monthly_utility_bill_with_solar − monthly_payment) × 12
```

This is the homeowner's net annual cash-flow improvement in Year 1: the reduction in utility payments minus the new loan obligation. For cash purchases, `monthly_payment = 0`.

---

## Carbon Estimates

Year 1 CO₂ figures are computed at baseline (no escalation, no degradation):

```
grid_emission_rate       = (1 − zero_carbon_pct) × 0.855 lbs CO₂/kWh
annual_co2_no_solar_lbs  = annual_consumption_kwh × grid_emission_rate
annual_co2_with_solar_lbs = max(0, annual_consumption_kwh − annual_production_kwh) × grid_emission_rate
```

**Known simplification:** `net_grid_kwh` uses *total* annual production (including exported kWh), not just self-consumed kWh. This assumes exported solar fully displaces grid emissions on a 1:1 basis — reasonable under NEM 2.0 net metering but approximate under NEM 3.0, where exports are valued and scheduled differently. A more precise model would count only the carbon displaced by self-consumed kWh; for v1 the simpler net-draw approach is sufficient.

### Carbon Card (UI)

Displayed as a card in the results section with:
- Lbs CO₂/yr without solar and with solar (Year 1 baseline)
- Metric-ton equivalent for each (divide by 2,205 lbs/metric ton)
- "CO₂ avoided per year" badge showing the difference (lbs and metric tons), omitted when difference is zero
- Attribution line: utility name, zero-carbon %, and a link to the CEC Annual Power Content Label for the source data
- When solar fully offsets consumption (`annual_co2_with_solar_lbs == 0`), the with-solar value displays as "0 lbs CO₂/yr" with the note "Solar fully offsets your consumption"

---

## Resolved Decisions

1. **Loan and Cash Purchase** both supported — user selects via radio button
2. **Advanced Settings** included — collapsible panel for adjusting financial assumptions
3. **Federal ITC removed** — no longer applicable in 2026
4. **Branding**: Contemporary green energy professional
