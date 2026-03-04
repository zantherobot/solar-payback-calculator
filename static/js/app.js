/* ==========================================================================
   Solar Payback Calculator — Client-side JS
   ========================================================================== */

// Chart instances — created on first render, updated in-place thereafter.
var paybackChartInst = null;
var breakdownChartInst = null;


// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function debounce(fn, delay) {
    var timer;
    var debounced = function () {
        var args = arguments;
        clearTimeout(timer);
        timer = setTimeout(function () { fn.apply(null, args); }, delay);
    };
    debounced.cancel = function () { clearTimeout(timer); };
    return debounced;
}

function fmtNum(n) {
    return Math.round(n).toLocaleString("en-US");
}


// ---------------------------------------------------------------------------
// DOM update helpers
// ---------------------------------------------------------------------------

function setHtml(id, html) {
    var el = document.getElementById(id);
    if (el) el.innerHTML = html;
}

function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
}


// ---------------------------------------------------------------------------
// Apply JSON results to the page
// ---------------------------------------------------------------------------

function applyResults(data) {
    var liveError = document.getElementById("live-error");
    var resultsSection = document.getElementById("results");

    if (data.error) {
        if (liveError) { liveError.textContent = data.error; liveError.style.display = ""; }
        return;
    }

    if (liveError) liveError.style.display = "none";
    if (resultsSection) resultsSection.style.display = "";

    // --- Headline card ---
    var paybackCard = document.getElementById("payback-card");
    if (paybackCard) {
        if (data.financing_type === "loan") {
            var mws = data.monthly_payment + data.monthly_utility_bill_with_solar;
            var savings = data.monthly_bill - mws;
            paybackCard.innerHTML =
                '<p class="payback-label">Monthly Cost with Solar</p>' +
                '<div class="monthly-cost-compare">' +
                  '<div class="monthly-cost-col">' +
                    '<p class="payback-value">$' + fmtNum(mws) + '<span class="payback-unit">/mo</span></p>' +
                    '<p class="monthly-cost-sublabel">Loan $' + fmtNum(data.monthly_payment) +
                      ' + Utility $' + fmtNum(data.monthly_utility_bill_with_solar) + '</p>' +
                  '</div>' +
                  '<div class="monthly-savings-col">' +
                    (savings >= 0
                      ? '<span class="monthly-savings-badge">$' + fmtNum(savings) + '/mo less than current utility bill</span>'
                      : '<span class="monthly-savings-badge monthly-savings-badge--over">$' + fmtNum(-savings) + '/mo more than current utility bill</span>') +
                  '</div>' +
                '</div>';
        } else {
            paybackCard.innerHTML =
                '<p class="payback-label">Estimated Payback Period</p>' +
                '<p class="payback-value">' + data.payback_display + '</p>' +
                '<p class="payback-meta">' +
                  data.utility + ' \u00B7 ' + data.plan_name + ' \u00B7 ' +
                  data.peak_sun_hours + ' avg. peak sun hours/day' +
                '</p>';
        }
    }

    // --- Stat cards ---
    setHtml("val-monthly-production", fmtNum(data.monthly_production_kwh) + ' <span>kWh</span>');
    setText("val-offset",             data.offset_pct + "%");
    setText("val-year1-savings",      "$" + fmtNum(data.year1_savings));
    setText("val-total-cost",         "$" + fmtNum(data.total_cost));
    setText("val-monthly-utility",    "$" + fmtNum(data.monthly_utility_bill_with_solar));
    setText("val-self-consumption",   data.self_consumption_ratio + "%");

    var financingCard = document.getElementById("stat-financing-card");
    if (financingCard) {
        financingCard.innerHTML = data.financing_type === "loan"
            ? '<p class="stat-label">Monthly Loan Payment</p>' +
              '<p class="stat-value">$' + fmtNum(data.monthly_payment) + '</p>'
            : '<p class="stat-label">Financing</p>' +
              '<p class="stat-value" style="font-size:1.1rem;">Cash Purchase</p>';
    }

    // --- Carbon card ---
    setHtml("carbon-source-note",
        'Based on ' + data.utility + ' grid: ' + Math.round(data.zero_carbon_pct * 100) + '% zero-carbon' +
        ' (' + data.plan_name + ' default plan &middot; <a href="https://www.energy.ca.gov/programs-and-topics' +
        '/programs/power-source-disclosure-program/power-content-label/annual-power-5"' +
        ' target="_blank" rel="noopener noreferrer">CEC 2024 Power Content Label</a>).' +
        ' Intensity varies by rate plan.');

    setHtml("carbon-no-solar-value",
        fmtNum(data.annual_co2_no_solar_lbs) + ' <span>lbs CO&#x2082;/yr</span>');
    setText("carbon-no-solar-tons",
        '\u2248 ' + (data.annual_co2_no_solar_lbs / 2205).toFixed(1) + ' metric tons');

    setHtml("carbon-with-solar-section",
        data.annual_co2_with_solar_lbs === 0
            ? '<p class="carbon-value carbon-value--zero">0 <span>lbs CO&#x2082;/yr</span></p>' +
              '<p class="carbon-tons">Solar fully offsets your consumption</p>'
            : '<p class="carbon-value">' + fmtNum(data.annual_co2_with_solar_lbs) +
              ' <span>lbs CO&#x2082;/yr</span></p>' +
              '<p class="carbon-tons">\u2248 ' + (data.annual_co2_with_solar_lbs / 2205).toFixed(1) +
              ' metric tons</p>');

    var co2Avoided = data.annual_co2_no_solar_lbs - data.annual_co2_with_solar_lbs;
    setHtml("carbon-savings-section",
        co2Avoided > 0
            ? '<div class="carbon-savings"><span class="carbon-savings-badge">' +
              fmtNum(co2Avoided) + ' lbs CO&#x2082; avoided per year' +
              ' (\u2248 ' + (co2Avoided / 2205).toFixed(1) + ' metric tons)' +
              '</span></div>'
            : '');

    // --- Charts ---
    renderPaybackChart(data.chart);
    renderBreakdownChart(data.breakdown);
}


// ---------------------------------------------------------------------------
// Live recalculation
// ---------------------------------------------------------------------------

function isFormReady() {
    var systemKw  = parseFloat(document.getElementById("system_kw").value);
    var bill      = parseFloat(document.getElementById("monthly_bill").value);
    var zip       = document.getElementById("zip_code").value.trim();
    return !isNaN(systemKw) && !isNaN(bill) && zip.length === 5;
}

async function recalculate() {
    if (!isFormReady()) return;

    var resultsSection = document.getElementById("results");
    if (resultsSection) resultsSection.classList.add("results-updating");

    try {
        var resp = await fetch("/calculate", {
            method: "POST",
            body: new FormData(document.getElementById("calc-form")),
        });
        var data = await resp.json();
        applyResults(data);
    } catch (e) {
        // Network error — silently skip; stale results remain visible.
    } finally {
        if (resultsSection) resultsSection.classList.remove("results-updating");
    }
}

var debouncedRecalc = debounce(recalculate, 400);


// ---------------------------------------------------------------------------
// DOMContentLoaded: wire up UI interactions
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", function () {
    // --- Custom battery input visibility ---
    var batterySelect  = document.getElementById("battery");
    var customGroup    = document.getElementById("custom-battery-group");

    function toggleCustom() {
        customGroup.style.display = batterySelect.value === "custom" ? "" : "none";
    }
    batterySelect.addEventListener("change", toggleCustom);
    toggleCustom();

    // --- Loan-specific fields visibility ---
    var financingRadios = document.querySelectorAll('input[name="financing_type"]');
    var loanFields      = document.querySelectorAll(".loan-field");

    function toggleLoanFields() {
        var isCash = document.querySelector('input[name="financing_type"]:checked').value === "cash";
        loanFields.forEach(function (el) { el.style.display = isCash ? "none" : ""; });
    }
    financingRadios.forEach(function (r) { r.addEventListener("change", toggleLoanFields); });
    toggleLoanFields();

    // --- Live update listeners ---
    var form     = document.getElementById("calc-form");
    var zipInput = document.getElementById("zip_code");

    // Number / text inputs (except zip): debounced on every keystroke.
    form.addEventListener("input", function (e) {
        if (e.target === zipInput) return;
        debouncedRecalc();
    });

    // Selects and radios: respond immediately, cancel any pending debounce.
    form.addEventListener("change", function (e) {
        if (e.target.tagName === "SELECT" || e.target.type === "radio") {
            debouncedRecalc.cancel();
            recalculate();
        }
    });

    // Zip: fire on blur once the field is exactly 5 digits.
    zipInput.addEventListener("blur", function () {
        if (zipInput.value.trim().length === 5) {
            debouncedRecalc.cancel();
            recalculate();
        }
    });

    // Calculate button: immediate recalculate.
    var calcBtn = document.getElementById("calc-btn");
    if (calcBtn) {
        calcBtn.addEventListener("click", function () {
            debouncedRecalc.cancel();
            recalculate();
        });
    }
});


// ---------------------------------------------------------------------------
// Charts — create on first call, update in-place on subsequent calls
// ---------------------------------------------------------------------------

/**
 * Render or update the 20-year cumulative cost comparison chart.
 * @param {Object} data - { years, noSolar, withSolar }
 */
function renderPaybackChart(data) {
    var canvas = document.getElementById("payback-chart");
    if (!canvas) return;

    // Crossover point (first year no-solar exceeds with-solar)
    var crossoverIdx = null;
    for (var i = 1; i < data.years.length; i++) {
        if (data.noSolar[i] > data.withSolar[i]) { crossoverIdx = i; break; }
    }
    var noSolarRadius = data.years.map(function () { return 0; });
    var solarRadius   = data.years.map(function () { return 0; });
    if (crossoverIdx !== null) {
        noSolarRadius[crossoverIdx] = 7;
        solarRadius[crossoverIdx]   = 7;
    }

    if (paybackChartInst) {
        paybackChartInst.data.datasets[0].data        = data.noSolar;
        paybackChartInst.data.datasets[0].pointRadius = noSolarRadius;
        paybackChartInst.data.datasets[1].data        = data.withSolar;
        paybackChartInst.data.datasets[1].pointRadius = solarRadius;
        paybackChartInst.update("none");
        return;
    }

    paybackChartInst = new Chart(canvas, {
        type: "line",
        data: {
            labels: data.years.map(function (y) { return "Year " + y; }),
            datasets: [
                {
                    label: "Without Solar",
                    data: data.noSolar,
                    borderColor: "#A0AEC0",
                    backgroundColor: "rgba(160, 174, 192, 0.08)",
                    borderWidth: 2.5,
                    pointRadius: noSolarRadius,
                    pointBackgroundColor: "#A0AEC0",
                    pointBorderColor: "#A0AEC0",
                    fill: false,
                    tension: 0.3,
                },
                {
                    label: "With Solar",
                    data: data.withSolar,
                    borderColor: "#2D6A4F",
                    backgroundColor: "rgba(45, 106, 79, 0.08)",
                    borderWidth: 2.5,
                    pointRadius: solarRadius,
                    pointBackgroundColor: "#2D6A4F",
                    pointBorderColor: "#2D6A4F",
                    fill: false,
                    tension: 0.3,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: {
                    position: "top",
                    labels: {
                        font: { family: "'Inter', sans-serif", size: 13 },
                        usePointStyle: true,
                        pointStyle: "line",
                        padding: 20,
                    },
                },
                tooltip: {
                    backgroundColor: "#1B1B1B",
                    titleFont: { family: "'Inter', sans-serif", size: 13 },
                    bodyFont:  { family: "'Inter', sans-serif", size: 12 },
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: function (context) {
                            return context.dataset.label + ": $" +
                                context.parsed.y.toLocaleString("en-US", {
                                    minimumFractionDigits: 0,
                                    maximumFractionDigits: 0,
                                });
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        font: { family: "'Inter', sans-serif", size: 11 },
                        color: "#A0AEC0",
                        maxTicksLimit: 11,
                        callback: function (value, index) {
                            return index % 2 === 0 ? "Yr " + index : "";
                        },
                    },
                },
                y: {
                    grid: { color: "rgba(0,0,0,0.04)" },
                    ticks: {
                        font: { family: "'Inter', sans-serif", size: 11 },
                        color: "#A0AEC0",
                        callback: function (value) {
                            return value >= 1000 ? "$" + (value / 1000).toFixed(0) + "k" : "$" + value;
                        },
                    },
                },
            },
        },
    });
}


/**
 * Render or update the Year-10 / Year-20 cost breakdown stacked bar chart.
 * @param {Object} data - { noSolar10, noSolar20, utilityWithSolar10, utilityWithSolar20,
 *                          solarCompany10, solarCompany20 }
 */
function renderBreakdownChart(data) {
    var canvas = document.getElementById("breakdown-chart");
    if (!canvas) return;

    if (breakdownChartInst) {
        breakdownChartInst.data.datasets[0].data = [data.noSolar10,       data.noSolar20];
        breakdownChartInst.data.datasets[1].data = [data.solarCompany10,  data.solarCompany20];
        breakdownChartInst.data.datasets[2].data = [data.utilityWithSolar10, data.utilityWithSolar20];
        breakdownChartInst.update("none");
        return;
    }

    function fmt(v) { return "$" + Math.round(v).toLocaleString("en-US"); }

    breakdownChartInst = new Chart(canvas, {
        type: "bar",
        data: {
            labels: ["Year 10", "Year 20"],
            datasets: [
                {
                    label: "Without Solar — utility payments",
                    data: [data.noSolar10, data.noSolar20],
                    backgroundColor: "rgba(160, 174, 192, 0.75)",
                    borderColor: "rgba(160, 174, 192, 1)",
                    borderWidth: 1,
                    stack: "without",
                },
                {
                    label: "With Solar — to solar company",
                    data: [data.solarCompany10, data.solarCompany20],
                    backgroundColor: "rgba(244, 162, 97, 0.85)",
                    borderColor: "rgba(244, 162, 97, 1)",
                    borderWidth: 1,
                    stack: "with",
                },
                {
                    label: "With Solar — to utility",
                    data: [data.utilityWithSolar10, data.utilityWithSolar20],
                    backgroundColor: "rgba(45, 106, 79, 0.75)",
                    borderColor: "rgba(45, 106, 79, 1)",
                    borderWidth: 1,
                    stack: "with",
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: "top",
                    labels: {
                        font: { family: "'Inter', sans-serif", size: 12 },
                        usePointStyle: true,
                        pointStyle: "rect",
                        padding: 16,
                    },
                },
                tooltip: {
                    backgroundColor: "#1B1B1B",
                    titleFont: { family: "'Inter', sans-serif", size: 13 },
                    bodyFont:  { family: "'Inter', sans-serif", size: 12 },
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: function (context) {
                            return "  " + context.dataset.label + ": " + fmt(context.parsed.y);
                        },
                        footer: function (items) {
                            if (items[0].dataset.stack === "with" && items.length > 0) {
                                var total = 0;
                                var idx = items[0].dataIndex;
                                items[0].chart.data.datasets.forEach(function (ds) {
                                    if (ds.stack === "with") total += ds.data[idx] || 0;
                                });
                                return "  Total with solar: " + fmt(total);
                            }
                            return "";
                        },
                    },
                },
            },
            scales: {
                x: {
                    stacked: true,
                    grid: { display: false },
                    ticks: { font: { family: "'Inter', sans-serif", size: 12 }, color: "#4A5568" },
                },
                y: {
                    stacked: true,
                    grid: { color: "rgba(0,0,0,0.04)" },
                    ticks: {
                        font: { family: "'Inter', sans-serif", size: 11 },
                        color: "#A0AEC0",
                        callback: function (value) {
                            return value >= 1000 ? "$" + (value / 1000).toFixed(0) + "k" : "$" + value;
                        },
                    },
                },
            },
        },
    });
}
