/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Resumen compacto de la lista de verificación para tarjetas kanban: una línea que dice
 * si el documento está listo, qué revisar o qué lo bloquea, sin abrir el registro.
 */
export class BiotexKanbanStatus extends Component {
    static template = "biotex_ux.KanbanStatus";
    static props = { ...standardFieldProps };

    get items() {
        const data = this.props.record.data[this.props.name];
        return (data && data.items) || [];
    }
    get blocking() {
        return this.items.filter((i) => i.state === "error");
    }
    get warnings() {
        return this.items.filter((i) => i.state === "warn");
    }
    get summary() {
        if (this.blocking.length) return { cls: "ux-pill--error", icon: "fa-times-circle", text: this.blocking[0].label };
        if (this.warnings.length) return { cls: "ux-pill--warn", icon: "fa-exclamation-triangle", text: this.warnings[0].label };
        return { cls: "ux-pill--ok", icon: "fa-check-circle", text: "Sin pendientes" };
    }
    get extra() {
        const n = this.blocking.length + this.warnings.length;
        return n > 1 ? `+${n - 1}` : "";
    }
}

registry.category("fields").add("biotex_kanban_status", {
    component: BiotexKanbanStatus,
    supportedTypes: ["json"],
});
