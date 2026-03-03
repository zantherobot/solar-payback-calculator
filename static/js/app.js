/* ==========================================================================
   Solar Payback Calculator — Client-side JS
   ========================================================================== */

// Toggle custom battery input visibility and loan fields
document.addEventListener("DOMContentLoaded", function () {
    var batterySelect = document.getElementById("battery");
    var customGroup = document.getElementById("custom-battery-group");

    function toggleCustom() {
        customGroup.style.display = batterySelect.value === "custom" ? "" : "none";
    }

    batterySelect.addEventListener("change", toggleCustom);
    toggleCustom(); // run on load

    // Toggle loan-specific fields based on financing type selection
    var financingRadios = document.querySelectorAll('input[name="financing_type"]');
    var loanFields = document.querySelectorAll(".loan-field");

    function toggleLoanFields() {
        var isCash = document.querySelector('input[name="financing_type"]:checked').value === "cash";
        loanFields.forEach(function (el) {
            el.style.display = isCash ? "none" : "";
        });
    }

    financingRadios.forEach(function (radio) {
        radio.addEventListener("change", toggleLoanFields);
    });
    toggleLoanFields(); // run on load

    // Completion notification: play sound and show banner
    var banner = document.getElementById("calc-complete-banner");
    if (banner) {
        // Brief visible notification, then fade out
        setTimeout(function () {
            banner.classList.add("calc-complete-banner--fade");
        }, 2500);

        // Play a short chime using the Web Audio API
        try {
            var AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (AudioCtx) {
                var ctx = new AudioCtx();
                var notes = [523.25, 659.25, 783.99]; // C5, E5, G5
                notes.forEach(function (freq, i) {
                    var osc = ctx.createOscillator();
                    var gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.type = "sine";
                    osc.frequency.value = freq;
                    var start = ctx.currentTime + i * 0.15;
                    gain.gain.setValueAtTime(0, start);
                    gain.gain.linearRampToValueAtTime(0.18, start + 0.03);
                    gain.gain.exponentialRampToValueAtTime(0.001, start + 0.35);
                    osc.start(start);
                    osc.stop(start + 0.36);
                });
            }
        } catch (e) {
            // Audio not available — silently skip
        }

        // Smooth scroll to results
        var results = document.getElementById("results");
        if (results) {
            results.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }
});


/**
 * Render the Year-10 / Year-20 cost breakdown stacked bar chart.
 * @param {Object} data - { noSolar10, noSolar20, utilityWithSolar10, utilityWithSolar20,
 *                          solarCompany10, solarCompany20 }
 */
function renderBreakdownChart(data) {
    var ctx = document.getElementById("breakdown-chart");
    if (!ctx) return;

    function fmt(v) {
        return "$" + Math.round(v).toLocaleString("en-US");
    }

    new Chart(ctx, {
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
                    bodyFont: { family: "'Inter', sans-serif", size: 12 },
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: function (context) {
                            return "  " + context.dataset.label + ": " + fmt(context.parsed.y);
                        },
                        footer: function (items) {
                            var stack = items[0].dataset.stack;
                            if (stack === "with" && items.length > 0) {
                                var total = 0;
                                var labelIdx = items[0].dataIndex;
                                items[0].chart.data.datasets.forEach(function (ds) {
                                    if (ds.stack === "with") {
                                        total += ds.data[labelIdx] || 0;
                                    }
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
                    ticks: {
                        font: { family: "'Inter', sans-serif", size: 12 },
                        color: "#4A5568",
                    },
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


/**
 * Render the 20-year cumulative cost comparison chart.
 * @param {Object} data - { years: number[], noSolar: number[], withSolar: number[] }
 */
function renderPaybackChart(data) {
    var ctx = document.getElementById("payback-chart");
    if (!ctx) return;

    // Find crossover point index (first year where noSolar > withSolar, after year 0)
    var crossoverIdx = null;
    for (var i = 1; i < data.years.length; i++) {
        if (data.noSolar[i] > data.withSolar[i]) {
            crossoverIdx = i;
            break;
        }
    }

    // Point radius array: highlight crossover
    var noSolarRadius = data.years.map(function () { return 0; });
    var solarRadius = data.years.map(function () { return 0; });
    if (crossoverIdx !== null) {
        noSolarRadius[crossoverIdx] = 7;
        solarRadius[crossoverIdx] = 7;
    }

    new Chart(ctx, {
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
                    pointBackgroundColor: "#F4A261",
                    pointBorderColor: "#F4A261",
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
                    pointBackgroundColor: "#F4A261",
                    pointBorderColor: "#F4A261",
                    fill: false,
                    tension: 0.3,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            interaction: {
                mode: "index",
                intersect: false,
            },
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
                    bodyFont: { family: "'Inter', sans-serif", size: 12 },
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: function (context) {
                            var value = context.parsed.y;
                            return context.dataset.label + ": $" +
                                value.toLocaleString("en-US", {
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
                    grid: {
                        color: "rgba(0,0,0,0.04)",
                    },
                    ticks: {
                        font: { family: "'Inter', sans-serif", size: 11 },
                        color: "#A0AEC0",
                        callback: function (value) {
                            if (value >= 1000) {
                                return "$" + (value / 1000).toFixed(0) + "k";
                            }
                            return "$" + value;
                        },
                    },
                },
            },
        },
    });
}
