from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ux_stock_matrix = fields.Json(compute='_compute_ux_stock_matrix')

    def _compute_ux_stock_matrix(self):
        warehouses = self.env['stock.warehouse'].sudo().search([('biotex_is_delegation', '=', True)], order='biotex_is_central desc, name')
        Orderpoint = self.env['stock.warehouse.orderpoint'].sudo()
        for tmpl in self:
            rows = []
            product = tmpl.product_variant_id
            for wh in warehouses:
                p = product.sudo().with_context(warehouse_id=wh.id)
                op = Orderpoint.search([('product_id', '=', product.id), ('warehouse_id', '=', wh.id)], limit=1) if product else Orderpoint
                qty, free, incoming, outgoing = (p.qty_available, p.free_qty, p.incoming_qty, p.outgoing_qty) if product else (0, 0, 0, 0)
                status = 'none'
                if op:
                    status = 'low' if qty < op.product_min_qty else ('ok' if qty <= op.product_max_qty else 'high')
                elif qty:
                    status = 'ok'
                rows.append({'id': wh.id, 'code': wh.code, 'name': wh.name, 'central': wh.biotex_is_central, 'company': wh.company_id.biotex_short_name or wh.company_id.name,
                             'qty': qty, 'free': free, 'incoming': incoming, 'outgoing': outgoing,
                             'min': op.product_min_qty if op else None, 'max': op.product_max_qty if op else None, 'status': status})
            tmpl.ux_stock_matrix = {'uom': tmpl.uom_id.name, 'rows': rows, 'total': sum(r['qty'] for r in rows), 'free_total': sum(r['free'] for r in rows),
                                    'high_rotation': tmpl.biotex_high_rotation}
