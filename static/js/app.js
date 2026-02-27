/* ==========================================================================
   Solar Payback Calculator — Client-side JS
   ========================================================================== */

// Toggle custom battery input visibility
document.addEventListener("DOMContentLoaded", function () {
    var batterySelect = document.getElementById("battery");
    var customGroup = document.getElementById("custom-battery-group");

    function toggleCustom() {
        if (batterySelect.value === "custom") {
            customGroup.style.display = "";
        } else {
            customGroup.style.display = "none";
        }
    }

    batterySelect.addEventListener("change", toggleCustom);
    toggleCustom(); // run on load

    // Smooth scroll to results after form submission
    var results = document.getElementById("results");
    if (results) {
        results.scrollIntoView({ behavior: "smooth", block: "start" });
    }
});


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
