from odoo import api, fields, models


class Remision(models.Model):
    _inherit = 'biotex.remision'

    ux_contract_keys = fields.Json(compute='_compute_ux_contract_keys')

    @api.depends('contract_id', 'contract_id.line_ids.qty_remaining', 'contract_id.line_ids.amount_delivered', 'line_ids.product_id', 'line_ids.product_qty', 'mask_ids.product_qty', 'mask_ids.contract_line_id')
    def _compute_ux_contract_keys(self):
        for r in self:
            keys = []
            delivered_products = {l.product_id.id: l.product_qty for l in r.line_ids}
            masked = {}
            for m in r.mask_ids:
                masked[m.contract_line_id.id] = masked.get(m.contract_line_id.id, 0) + m.product_qty
            for cl in r.contract_id.line_ids:
                keys.append({
                    'id': cl.id, 'code': cl.code, 'name': cl.name, 'product': cl.product_id.display_name or '',
                    'product_id': cl.product_id.id, 'qty': cl.product_qty, 'delivered': cl.qty_delivered, 'remaining': cl.qty_remaining,
                    'price': cl.price_unit, 'amount_remaining': cl.qty_remaining * cl.price_unit,
                    'in_this': masked.get(cl.id, 0.0),
                    'matches_line': cl.product_id.id in delivered_products,
                    'suggest_qty': min(delivered_products.get(cl.product_id.id, 0.0), max(cl.qty_remaining, 0.0)) if cl.product_id.id in delivered_products else 0.0,
                })
            r.ux_contract_keys = {'currency': r.currency_id.symbol, 'keys': keys, 'editable': r.state == 'draft'}

    def ux_add_mask(self, contract_line_id, qty):
        """Agrega una clave a cobrar desde el panel (registro ya guardado)."""
        self.ensure_one()
        cl = self.env['biotex.contract.line'].browse(contract_line_id)
        line = self.line_ids.filtered(lambda l: l.product_id == cl.product_id)[:1]
        existing = self.mask_ids.filtered(lambda m: m.contract_line_id == cl)[:1]
        if existing:
            existing.product_qty += qty
        else:
            self.env['biotex.remision.mask'].create({'remision_id': self.id, 'contract_line_id': cl.id, 'product_qty': qty, 'line_id': line.id if line else False})
        return True
