/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { formatMonetary } from "@web/views/fields/formatters";

/**
 * Panel de claves del contrato dentro de la remisión. Muestra por clave lo contratado, lo entregado,
 * lo pendiente y el saldo en dinero, marca las claves cuyo producto coincide con lo entregado y permite
 * cobrar con una clave en un clic (agrega la línea de máscara con la cantidad sugerida).
 */
export class BiotexContractKeys extends Component {
    static template = "biotex_ux.ContractKeys";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ filter: "", busy: false });
    }
    get data() {
        return this.props.record.data[this.props.name] || { keys: [], editable: false };
    }
    get keys() {
        const q = this.state.filter.toLowerCase();
        return this.data.keys
            .filter((k) => !q || k.code.toLowerCase().includes(q) || k.name.toLowerCase().includes(q) || (k.product || "").toLowerCase().includes(q))
            .sort((a, b) => (b.matches_line - a.matches_line) || a.code.localeCompare(b.code));
    }
    money(v) {
        return `${this.data.currency || ""} ${formatMonetary(v || 0, { digits: [16, 2] })}`;
    }
    pct(k) {
        return k.qty ? Math.min(100, (k.delivered / k.qty) * 100) : 0;
    }
    async use(k) {
        if (!this.data.editable || this.state.busy) return;
        const qty = k.suggest_qty > 0 ? k.suggest_qty : Math.max(k.remaining, 0) || 1;
        this.state.busy = true;
        try {
            const record = this.props.record;
            await record.save();
            if (!record.resId) return;
            await this.orm.call("biotex.remision", "ux_add_mask", [[record.resId], k.id, qty]);
            await record.load();
            this.notification.add(`Clave ${k.code} agregada por ${qty} ${k.product ? "" : "unidades"}`.trim(), { type: "success" });
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("fields").add("biotex_contract_keys", {
    component: BiotexContractKeys,
    supportedTypes: ["json"],
});
