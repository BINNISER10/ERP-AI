/** @odoo-module **/
/* eslint-disable no-undef */
/* Nexus Executive AI Cockpit — لوحة القيادة الاستراتيجية */

(function () {
    "use strict";

    const WIDGET_META = {
        liquidity: { title: "معدل السيولة / Liquidity", icon: "fa-university" },
        daily_sales: { title: "المبيعات اليومية / Daily Sales", icon: "fa-shopping-cart" },
        gross_margin: { title: "هامش الربح الإجمالي / Gross Margin", icon: "fa-percent" },
        revenue_trend: { title: "اتجاه الإيرادات / Revenue Trend (6M)", icon: "fa-bar-chart" },
        cash_flow_forecast: { title: "توقع التدفق النقدي (90 يوم)", icon: "fa-line-chart" },
        ar_aging: { title: "تأخر الذمم المدينة / AR Aging", icon: "fa-clock-o" },
        branch_performance: { title: "مؤشرات أداء الفروع / Branch Performance", icon: "fa-building" },
        top_expenses: { title: "أعلى المصروفات / Top Expenses (MTD)", icon: "fa-money" },
        customer_concentration: { title: "تركز العملاء / Customer Concentration", icon: "fa-users" },
        anomaly_alerts: { title: "الرؤى التنبؤية / AI Alerts", icon: "fa-exclamation-triangle" },
    };

    let dragSourceId = null;

    async function fetchJSON(url, options) {
        const resp = await fetch(url, options);
        return resp.json();
    }

    function formatMoney(value, currency) {
        try {
            return new Intl.NumberFormat("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }).format(value || 0) + " " + (currency || "");
        } catch (e) {
            return (value || 0).toFixed(2) + " " + (currency || "");
        }
    }

    function makeCard(widgetKey) {
        const meta = WIDGET_META[widgetKey] || { title: widgetKey, icon: "fa-square" };
        const card = document.createElement("div");
        card.className = "nexus-cockpit-card";
        card.dataset.widget = widgetKey;
        card.draggable = true;
        card.innerHTML = `
            <div class="nexus-cockpit-card-header">
                <span><i class="fa ${meta.icon}"></i> ${meta.title}</span>
                <span class="nexus-cockpit-drag-handle" title="اسحب لإعادة الترتيب">
                    <i class="fa fa-arrows"></i>
                </span>
            </div>
            <div class="nexus-cockpit-card-body" id="body-${widgetKey}">
                <div class="text-muted">جارِ التحميل...</div>
            </div>
        `;
        card.addEventListener("dragstart", () => { dragSourceId = widgetKey; });
        card.addEventListener("dragover", (ev) => ev.preventDefault());
        card.addEventListener("drop", (ev) => {
            ev.preventDefault();
            if (!dragSourceId || dragSourceId === widgetKey) return;
            const container = document.getElementById("nexus-cockpit-widgets");
            const source = container.querySelector(`[data-widget="${dragSourceId}"]`);
            const target = container.querySelector(`[data-widget="${widgetKey}"]`);
            if (source && target) {
                container.insertBefore(source, target);
                persistOrder(container);
            }
        });
        return card;
    }

    function persistOrder(container) {
        const order = Array.from(container.children).map((el) => el.dataset.widget);
        fetch("/nexus/cockpit/layout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jsonrpc: "2.0", params: { order: order } }),
        }).catch((err) => console.warn("Failed to persist cockpit layout:", err));
    }

    async function renderWidget(widgetKey) {
        const body = document.getElementById(`body-${widgetKey}`);
        if (!body) return;
        let data;
        try {
            data = await fetchJSON(`/nexus/cockpit/data?widget=${encodeURIComponent(widgetKey)}`);
        } catch (err) {
            body.innerHTML = `<div class="text-danger">تعذر تحميل البيانات</div>`;
            return;
        }
        if (data.error) {
            body.innerHTML = `<div class="text-danger">${data.error}</div>`;
            return;
        }

        if (widgetKey === "liquidity" || widgetKey === "daily_sales") {
            body.innerHTML = `<div class="nexus-cockpit-kpi-value">${formatMoney(data.value, data.currency)}</div>`;
        } else if (widgetKey === "gross_margin") {
            body.innerHTML = `
                <div class="nexus-cockpit-kpi-value">${(data.value || 0).toFixed(1)}%</div>
                <div class="text-muted small">
                    Revenue: ${formatMoney(data.revenue, data.currency)} |
                    COGS: ${formatMoney(data.cogs, data.currency)}
                </div>`;
        } else if (widgetKey === "branch_performance") {
            const rows = (data.branches || []).map((b) => `
                <tr>
                    <td>${b.name}</td>
                    <td>${formatMoney(b.daily_sales, b.currency)}</td>
                    <td>${b.invoice_count}</td>
                </tr>`).join("");
            body.innerHTML = `
                <table class="table table-sm">
                    <thead><tr><th>الفرع</th><th>المبيعات اليوم</th><th>عدد الفواتير</th></tr></thead>
                    <tbody>${rows || '<tr><td colspan="3" class="text-muted">لا بيانات</td></tr>'}</tbody>
                </table>`;
        } else if (widgetKey === "anomaly_alerts") {
            const items = (data.alerts || []).map((a) => `
                <li class="list-group-item nexus-cockpit-alert-${a.severity}">
                    ${a.message}
                </li>`).join("");
            body.innerHTML = `<ul class="list-group">${items || '<li class="list-group-item text-muted">لا توجد تنبيهات حالياً ✅</li>'}</ul>`;
        } else if (widgetKey === "cash_flow_forecast") {
            const canvasId = "chart-cash-flow-forecast";
            body.innerHTML = `<div class="nexus-chart-container"><canvas id="${canvasId}"></canvas></div>`;
            const buckets = data.buckets || [];
            const ctx = document.getElementById(canvasId).getContext("2d");
            // eslint-disable-next-line no-undef
            new Chart(ctx, {
                type: "line",
                data: {
                    labels: buckets.map((b) => b.week_start),
                    datasets: [{
                        label: "Projected Balance",
                        data: buckets.map((b) => b.projected_balance),
                        borderColor: "#0B3D2E",
                        backgroundColor: "rgba(11,61,46,0.1)",
                        fill: true,
                        tension: 0.3,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                },
            });
        } else if (widgetKey === "revenue_trend") {
            const canvasId = "chart-revenue-trend";
            body.innerHTML = `<div class="nexus-chart-container"><canvas id="${canvasId}"></canvas></div>`;
            const months = data.months || [];
            const ctx = document.getElementById(canvasId).getContext("2d");
            // eslint-disable-next-line no-undef
            new Chart(ctx, {
                type: "bar",
                data: {
                    labels: months.map((m) => m.month),
                    datasets: [{
                        label: "Revenue",
                        data: months.map((m) => m.revenue),
                        backgroundColor: "rgba(11,61,46,0.7)",
                        borderColor: "#0B3D2E",
                        borderWidth: 1,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true } },
                },
            });
        } else if (widgetKey === "ar_aging") {
            const canvasId = "chart-ar-aging";
            body.innerHTML = `<div class="nexus-chart-container"><canvas id="${canvasId}"></canvas></div>`;
            const b = data.buckets || {};
            const ctx = document.getElementById(canvasId).getContext("2d");
            // eslint-disable-next-line no-undef
            new Chart(ctx, {
                type: "bar",
                data: {
                    labels: ["Current", "1-30", "31-60", "61-90", "90+"],
                    datasets: [{
                        label: "Outstanding",
                        data: [b.current, b["1_30"], b["31_60"], b["61_90"], b["90_plus"]],
                        backgroundColor: ["#4CAF50", "#FFC107", "#FF9800", "#F57C00", "#D32F2F"],
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true } },
                },
            });
        } else if (widgetKey === "top_expenses") {
            const items = data.items || [];
            const rows = items.map((i) => `
                <tr>
                    <td>${i.account}</td>
                    <td class="text-right">${formatMoney(i.amount, data.currency)}</td>
                </tr>`).join("");
            body.innerHTML = `
                <table class="table table-sm">
                    <thead><tr><th>Account</th><th class="text-right">Amount</th></tr></thead>
                    <tbody>${rows || '<tr><td colspan="2" class="text-muted">لا بيانات</td></tr>'}</tbody>
                </table>`;
        } else if (widgetKey === "customer_concentration") {
            const items = data.items || [];
            const riskClass = `nexus-cockpit-risk-${data.risk_level || "low"}`;
            const rows = items.map((i) => `
                <tr>
                    <td>${i.customer}</td>
                    <td class="text-right">${formatMoney(i.revenue, data.currency)}</td>
                    <td class="text-right">${i.share_pct}%</td>
                </tr>`).join("");
            body.innerHTML = `
                <div class="nexus-cockpit-risk-badge ${riskClass}">
                    Top 5 share: ${data.top5_share_pct || 0}% (${data.risk_level || "low"} risk)
                </div>
                <table class="table table-sm">
                    <thead><tr><th>Customer</th><th class="text-right">Revenue</th><th class="text-right">Share</th></tr></thead>
                    <tbody>${rows || '<tr><td colspan="3" class="text-muted">لا بيانات</td></tr>'}</tbody>
                </table>`;
        }
    }

    async function init() {
        const root = document.getElementById("nexus-cockpit-root");
        if (!root) return;
        const widgetsContainer = document.getElementById("nexus-cockpit-widgets");

        let layout = { order: Object.keys(WIDGET_META), hidden: [] };
        try {
            layout = await fetchJSON("/nexus/cockpit/layout");
        } catch (err) {
            console.warn("Using default cockpit layout:", err);
        }

        const order = (layout.order && layout.order.length) ? layout.order : Object.keys(WIDGET_META);
        const hidden = new Set(layout.hidden || []);

        order.forEach((widgetKey) => {
            if (hidden.has(widgetKey) || !WIDGET_META[widgetKey]) return;
            widgetsContainer.appendChild(makeCard(widgetKey));
        });

        order.forEach((widgetKey) => {
            if (!hidden.has(widgetKey) && WIDGET_META[widgetKey]) {
                renderWidget(widgetKey);
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
