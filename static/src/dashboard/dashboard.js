/** @odoo-module **/
import { Component, useState, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

const PERIODS = [
    { days: 30, label: "30 días" },
    { days: 90, label: "90 días" },
    { days: 180, label: "6 meses" },
    { days: 365, label: "12 meses" },
];

/**
 * Tablero de operación. Cinco indicadores acordados con Dirección, colas por rol y tres gráficas.
 * Todo se calcula en servidor (biotex.ux.dashboard.get_data); aquí solo se presenta y se navega.
 */
export class BiotexDashboard extends Component {
    static template = "biotex_ux.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.periods = PERIODS;
        this.state = useState({ data: null, warehouse: false, days: 30, loading: true });
        this.charts = {};
        this.refs = { state: useRef("chartState"), lead: useRef("chartLead"), trend: useRef("chartTrend") };
        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.load();
        });
        onMounted(() => this.draw());
        onWillUnmount(() => this.destroyCharts());
    }
    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("biotex.ux.dashboard", "get_data", [this.state.warehouse || null, this.state.days]);
        this.state.loading = false;
        this.draw();
    }
    setPeriod(days) {
        this.state.days = days;
        this.load();
    }
    setWarehouse(ev) {
        this.state.warehouse = ev.target.value ? parseInt(ev.target.value) : false;
        this.load();
    }
    openQueue(q) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: q.label,
            res_model: q.model,
            views: [[false, "list"], [false, "form"]],
            domain: q.domain,
            target: "current",
        });
    }
    openContract(c) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "biotex.contract", res_id: c.id, views: [[false, "form"]] });
    }
    kpiClass(k) {
        return k.good ? "ux-kpi--good" : "ux-kpi--bad";
    }
    destroyCharts() {
        for (const c of Object.values(this.charts)) c.destroy();
        this.charts = {};
    }
    draw() {
        const d = this.state.data;
        if (!d || !window.Chart) return;
        this.destroyCharts();
        const style = getComputedStyle(document.documentElement);
        const accent = style.getPropertyValue("--ux-accent").trim() || "#0b6f6a";
        const muted = style.getPropertyValue("--ux-muted").trim() || "#8a9a98";
        const danger = "#c62828";
        const grid = { color: "rgba(128,128,128,.15)" };
        const font = { family: getComputedStyle(document.body).fontFamily, size: 11 };
        if (this.refs.state.el) {
            this.charts.state = new Chart(this.refs.state.el, {
                type: "bar",
                data: { labels: d.requests_by_state.map((r) => r.state), datasets: [{ data: d.requests_by_state.map((r) => r.count), backgroundColor: accent, borderRadius: 4 }] },
                options: { plugins: { legend: { display: false } }, scales: { x: { grid: { display: false }, ticks: { font } }, y: { grid, ticks: { font, precision: 0 } } }, maintainAspectRatio: false },
            });
        }
        if (this.refs.lead.el) {
            this.charts.lead = new Chart(this.refs.lead.el, {
                type: "bar",
                data: { labels: d.lead_by_warehouse.map((r) => r.warehouse), datasets: [{ data: d.lead_by_warehouse.map((r) => r.days), backgroundColor: d.lead_by_warehouse.map((r) => (r.days > 3 ? danger : accent)), borderRadius: 4 }] },
                options: { indexAxis: "y", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.raw} días (${d.lead_by_warehouse[c.dataIndex].orders} OC)` } } }, scales: { x: { grid, ticks: { font }, title: { display: true, text: "días", font } }, y: { grid: { display: false }, ticks: { font } } }, maintainAspectRatio: false },
            });
        }
        if (this.refs.trend.el) {
            this.charts.trend = new Chart(this.refs.trend.el, {
                type: "line",
                data: { labels: d.price_trend.map((r) => r.month), datasets: [{ data: d.price_trend.map((r) => r.delta), borderColor: accent, backgroundColor: accent + "22", fill: true, tension: 0.3, pointRadius: 4, pointBackgroundColor: d.price_trend.map((r) => (r.delta > 3 ? danger : accent)) }] },
                options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.raw}% vs. promedio (${d.price_trend[c.dataIndex].orders} OC)` } } }, scales: { x: { grid: { display: false }, ticks: { font } }, y: { grid, ticks: { font, callback: (v) => v + "%" } } }, maintainAspectRatio: false },
            });
        }
        void muted;
    }
}

registry.category("actions").add("biotex_ux.dashboard", BiotexDashboard);
