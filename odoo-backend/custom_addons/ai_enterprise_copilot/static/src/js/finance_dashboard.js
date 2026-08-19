/** @odoo-module **/
/* eslint-disable no-undef */
/* Nexus Finance Dashboard — لوحة التحكم المالية */

(function () {
    "use strict";

    const BRAND_GREEN = "#0B3D2E";
    const BRAND_LIGHT = "#E8F5E9";
    const BRAND_RED = "#D32F2F";
    const BRAND_AMBER = "#F9A825";

    const CHART_PALETTE = [
        BRAND_GREEN, "#4CAF50", "#81C784", BRAND_AMBER,
        "#FFB74D", BRAND_RED, "#E57373", "#7986CB",
    ];

    /**
     * Fetch chart data from the controller and render via Chart.js.
     */
    async function loadChart(canvasId, chartType) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.warn("Canvas not found:", canvasId);
            return;
        }
        let data;
        try {
            const resp = await fetch(
                "/nexus/finance/chart_data?chart_type=" + encodeURIComponent(chartType)
            );
            data = await resp.json();
        } catch (err) {
            console.error("Chart load failed:", err);
            return;
        }
        if (!data || data.error) {
            console.warn("Chart data error:", data && data.error);
            return;
        }
        renderChart(canvas, data);
    }

    /**
     * Render Chart.js instance from a payload.
     */
    function renderChart(canvas, data) {
        const ctx = canvas.getContext("2d");
        const datasets = (data.datasets || []).map((d, i) => ({
            label: d.label || "",
            data: d.data || [],
            backgroundColor: d.color || d.colors || CHART_PALETTE[i % CHART_PALETTE.length],
            borderColor: d.color || CHART_PALETTE[i % CHART_PALETTE.length],
            borderWidth: 2,
            fill: false,
            tension: 0.3,
        }));
        // eslint-disable-next-line no-undef
        new Chart(ctx, {
            type: data.chart_type === "kpi" ? "bar" : data.chart_type,
            data: { labels: data.labels || [], datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom" },
                    title: { display: true, text: data.title || "" },
                },
                scales: {
                    y: { beginAtZero: true },
                },
            },
        });
    }

    /**
     * Render KPI cards into a container.
     */
    function renderKPIs(containerId, data) {
        const container = document.getElementById(containerId);
        if (!container || !data || !data.kpis) return;
        container.innerHTML = "";
        data.kpis.forEach((kpi) => {
            const card = document.createElement("div");
            card.className = "nexus-kpi-card";
            card.style.borderLeftColor = kpi.color || BRAND_GREEN;
            card.innerHTML = `
                <div class="nexus-kpi-label">${kpi.label}</div>
                <div class="nexus-kpi-value">${formatMoney(kpi.value, data.currency)}</div>
                <div class="nexus-kpi-delta ${kpi.delta_pct >= 0 ? "text-success" : "text-danger"}">
                    ${kpi.delta_pct >= 0 ? "▲" : "▼"} ${Math.abs(kpi.delta_pct)}%
                    <small class="text-muted">vs ${formatMoney(kpi.previous, data.currency)}</small>
                </div>
            `;
            container.appendChild(card);
        });
    }

    function formatMoney(value, currency) {
        try {
            return new Intl.NumberFormat("en-US", {
                style: "decimal",
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }).format(value) + " " + (currency || "");
        } catch (e) {
            return (value || 0).toFixed(2) + " " + (currency || "");
        }
    }

    /**
     * Initialize the dashboard once the DOM is ready.
     */
    function init() {
        const root = document.querySelector(".nexus-finance-dashboard");
        if (!root) return;
        // KPI Summary first
        fetch("/nexus/finance/chart_data?chart_type=kpi_summary")
            .then((r) => r.json())
            .then((d) => renderKPIs("nexus-kpi-container", d));
        // Charts
        loadChart("nexus-chart-revenue-expense", "revenue_expense");
        loadChart("nexus-chart-aging-receivable", "aging_receivable");
        loadChart("nexus-chart-cash-flow", "cash_flow");
        loadChart("nexus-chart-top-customers", "top_customers");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
