/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/** Existencias por delegación con semáforo contra la regla de mínimo. */
export class BiotexStockMatrix extends Component {
    static template = "biotex_ux.StockMatrix";
    static props = { ...standardFieldProps };

    setup() {
        this.action = useService("action");
    }
    get data() {
        return this.props.record.data[this.props.name] || { rows: [], total: 0, free_total: 0 };
    }
    get max() {
        return Math.max(1, ...this.data.rows.map((r) => r.qty));
    }
    barWidth(r) {
        return Math.max(2, (Math.max(r.qty, 0) / this.max) * 100);
    }
    statusMeta(r) {
        return {
            low: { cls: "ux-bar--low", label: "Bajo mínimo" },
            ok: { cls: "ux-bar--ok", label: "En rango" },
            high: { cls: "ux-bar--high", label: "Sobre máximo" },
            none: { cls: "ux-bar--none", label: r.qty ? "Sin regla" : "Sin existencia" },
        }[r.status];
    }
    openQuants(r) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `Existencias en ${r.name}`,
            res_model: "stock.quant",
            views: [[false, "list"]],
            domain: [["product_id.product_tmpl_id", "=", this.props.record.resId], ["warehouse_id", "=", r.id]],
            context: { search_default_internal_loc: 1 },
        });
    }
}

registry.category("fields").add("biotex_stock_matrix", {
    component: BiotexStockMatrix,
    supportedTypes: ["json"],
});
