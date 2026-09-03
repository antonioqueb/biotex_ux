/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const META = {
    ok: { icon: "fa-check-circle", cls: "ux-ok", label: "Cumplido" },
    warn: { icon: "fa-exclamation-triangle", cls: "ux-warn", label: "Revisar" },
    error: { icon: "fa-times-circle", cls: "ux-error", label: "Bloquea" },
    info: { icon: "fa-info-circle", cls: "ux-info", label: "Contexto" },
};

/**
 * Lista de verificación en vivo. Recibe {items: [{key,label,state,hint,action}]} calculado en servidor
 * y lo presenta como una banda compacta con resumen y detalle desplegable. El objetivo es que quien
 * captura sepa, antes de enviar, qué falta y por qué; y que quien revisa entienda el estado sin leer todo el formulario.
 */
export class BiotexChecklist extends Component {
    static template = "biotex_ux.Checklist";
    static props = { ...standardFieldProps };

    setup() {
        this.action = useService("action");
        this.state = useState({ open: this.defaultOpen });
    }
    get items() {
        const data = this.props.record.data[this.props.name];
        return (data && data.items) || [];
    }
    get counts() {
        const c = { ok: 0, warn: 0, error: 0, info: 0 };
        for (const it of this.items) c[it.state] = (c[it.state] || 0) + 1;
        return c;
    }
    get defaultOpen() {
        const c = this.counts;
        return c.error > 0 || c.warn > 0;
    }
    get overall() {
        const c = this.counts;
        if (c.error) return { ...META.error, text: `${c.error} punto${c.error > 1 ? "s" : ""} bloquea${c.error > 1 ? "n" : ""} el avance` };
        if (c.warn) return { ...META.warn, text: `${c.warn} punto${c.warn > 1 ? "s" : ""} por revisar` };
        return { ...META.ok, text: "Todo en orden" };
    }
    meta(state) {
        return META[state] || META.info;
    }
    toggle() {
        this.state.open = !this.state.open;
    }
    go(item) {
        if (!item.action) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: item.action.res_model,
            res_id: item.action.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("fields").add("biotex_checklist", {
    component: BiotexChecklist,
    supportedTypes: ["json"],
});
