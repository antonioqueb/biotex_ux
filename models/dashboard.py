"""Tablero de operación: los cinco indicadores acordados con Dirección más las colas por rol."""
from datetime import timedelta

from odoo import api, fields, models


class UxDashboard(models.TransientModel):
    _name = 'biotex.ux.dashboard'
    _description = 'Tablero de operación'

    @api.model
    def get_data(self, warehouse_id=None, days=30):
        env = self.env
        today = fields.Date.context_today(self)
        since = today - timedelta(days=days)
        since_dt = fields.Datetime.to_datetime(since)
        wh_dom = [('warehouse_id', '=', warehouse_id)] if warehouse_id else []
        Req = env['biotex.purchase.request']
        reqs = Req.search(wh_dom + [('create_date', '>=', since_dt)])
        lines = reqs.mapped('line_ids')
        # 1. % solicitudes con clave de catálogo
        with_code = len(lines.filtered('product_id'))
        pct_code = (with_code / len(lines) * 100) if lines else 0
        # 2. tiempo solicitud -> OC (horas)
        POL = env['purchase.order']
        pos = POL.search([('biotex_request_id', 'in', reqs.ids), ('state', 'in', ('purchase', 'done'))])
        durations = [(po.date_approve - po.biotex_request_id.create_date).total_seconds() / 3600 for po in pos if po.date_approve and po.biotex_request_id.create_date]
        avg_hours = sum(durations) / len(durations) if durations else 0
        # 3. urgentes
        urgent = len(reqs.filtered(lambda r: r.priority == '1'))
        pct_urgent = (urgent / len(reqs) * 100) if reqs else 0
        # 4. precio pagado vs promedio
        po_dom = [('state', 'in', ('purchase', 'done')), ('date_approve', '>=', since_dt), ('biotex_internal', '=', False)]
        if warehouse_id:
            po_dom.append(('biotex_warehouse_id', '=', warehouse_id))
        period_pos = POL.search(po_dom)
        deltas = [l.biotex_price_delta_pct for l in period_pos.mapped('order_line') if l.biotex_avg_price]
        avg_delta = sum(deltas) / len(deltas) if deltas else 0
        overpaid = sum(max(l.price_unit - l.biotex_avg_price, 0) * l.product_qty for l in period_pos.mapped('order_line') if l.biotex_avg_price)
        # 5. OC sin recepción y facturas sin ligar > 7 días
        stale_pos = POL.search([('state', 'in', ('purchase',)), ('biotex_internal', '=', False), ('date_approve', '<', fields.Datetime.to_datetime(today - timedelta(days=7))),
                                ('biotex_transit_state', 'in', ('none', 'in_transit', 'arrived'))] + ([('biotex_warehouse_id', '=', warehouse_id)] if warehouse_id else []))
        Move = env['account.move']
        unlinked_bills = Move.search([('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), ('invoice_date', '<', today - timedelta(days=7)),
                                      ('invoice_line_ids.purchase_line_id', '=', False)])
        # colas por rol
        PR = env['biotex.payment.request']
        Rem = env['biotex.remision']
        Contract = env['biotex.contract']
        queues = [
            {'key': 'authorize', 'label': 'Por autorizar', 'count': Req.search_count(wh_dom + [('state', '=', 'submitted')]), 'model': 'biotex.purchase.request', 'domain': wh_dom + [('state', '=', 'submitted')], 'role': 'Coordinador'},
            {'key': 'identify', 'label': 'Por identificar', 'count': Req.search_count(wh_dom + [('state', 'not in', ('received', 'cancelled')), ('line_ids.product_id', '=', False)]), 'model': 'biotex.purchase.request', 'domain': wh_dom + [('state', 'not in', ('received', 'cancelled')), ('line_ids.product_id', '=', False)], 'role': 'Compras'},
            {'key': 'purchase', 'label': 'Para cotizar u ordenar', 'count': Req.search_count(wh_dom + [('state', 'in', ('authorized', 'quoting'))]), 'model': 'biotex.purchase.request', 'domain': wh_dom + [('state', 'in', ('authorized', 'quoting'))], 'role': 'Compras'},
            {'key': 'pay', 'label': 'Pagos pendientes', 'count': PR.search_count([('state', 'in', ('requested', 'approved'))] + ([('warehouse_id', '=', warehouse_id)] if warehouse_id else [])), 'model': 'biotex.payment.request', 'domain': [('state', 'in', ('requested', 'approved'))], 'role': 'Administración'},
            {'key': 'transit', 'label': 'Guías en tránsito', 'count': env['stock.picking'].search_count([('biotex_transit_state', 'in', ('in_transit', 'arrived')), ('state', 'not in', ('done', 'cancel'))] + ([('biotex_warehouse_id', '=', warehouse_id)] if warehouse_id else [])), 'model': 'stock.picking', 'domain': [('biotex_transit_state', 'in', ('in_transit', 'arrived')), ('state', 'not in', ('done', 'cancel'))], 'role': 'Delegación'},
            {'key': 'unsigned', 'label': 'Remisiones sin firma', 'count': Rem.search_count([('state', '=', 'delivered')] + wh_dom), 'model': 'biotex.remision', 'domain': [('state', '=', 'delivered')] + wh_dom, 'role': 'Delegación'},
            {'key': 'invoice', 'label': 'Remisiones por facturar', 'count': Rem.search_count([('state', 'in', ('delivered', 'signed'))] + wh_dom), 'model': 'biotex.remision', 'domain': [('state', 'in', ('delivered', 'signed'))] + wh_dom, 'role': 'Cobranza'},
            {'key': 'contracts', 'label': 'Contratos cerca del límite', 'count': Contract.search_count([('state', '=', 'active'), ('progress', '>=', 80)]), 'model': 'biotex.contract', 'domain': [('state', '=', 'active'), ('progress', '>=', 80)], 'role': 'Dirección'},
            {'key': 'unclassified', 'label': 'Productos sin clasificar', 'count': env['product.template'].search_count([('biotex_class_state', '!=', 'complete')]), 'model': 'product.template', 'domain': [('biotex_class_state', '!=', 'complete')], 'role': 'Catálogo'},
        ]
        # series: solicitudes por estado, tiempo por delegación, contratos
        by_state = {}
        for r in reqs:
            by_state[r.state] = by_state.get(r.state, 0) + 1
        state_labels = dict(Req._fields['state'].selection)
        by_wh = {}
        for po in pos:
            wh = po.biotex_warehouse_id.name or '-'
            if po.date_approve and po.biotex_request_id.create_date:
                by_wh.setdefault(wh, []).append((po.date_approve - po.biotex_request_id.create_date).total_seconds() / 3600)
        contracts = Contract.search([('state', '=', 'active')], order='progress desc', limit=10)
        # tendencia mensual de precio vs promedio (6 meses)
        trend = []
        for i in range(5, -1, -1):
            m_start = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
            m_end = (m_start + timedelta(days=32)).replace(day=1)
            mpos = POL.search([('state', 'in', ('purchase', 'done')), ('biotex_internal', '=', False), ('date_approve', '>=', fields.Datetime.to_datetime(m_start)), ('date_approve', '<', fields.Datetime.to_datetime(m_end))])
            d = [l.biotex_price_delta_pct for l in mpos.mapped('order_line') if l.biotex_avg_price]
            trend.append({'month': m_start.strftime('%b %y'), 'delta': round(sum(d) / len(d), 1) if d else 0, 'orders': len(mpos)})
        return {
            'period': {'since': fields.Date.to_string(since), 'until': fields.Date.to_string(today), 'days': days},
            'kpis': [
                {'key': 'code', 'label': 'Solicitudes con clave de catálogo', 'value': round(pct_code, 1), 'unit': '%', 'good': pct_code >= 90, 'hint': '%d de %d líneas capturadas con producto del catálogo' % (with_code, len(lines))},
                {'key': 'lead', 'label': 'Tiempo solicitud → OC', 'value': round(avg_hours / 24, 1), 'unit': 'días', 'good': avg_hours <= 72, 'hint': 'Promedio sobre %d órdenes confirmadas' % len(durations)},
                {'key': 'urgent', 'label': 'Compras urgentes', 'value': round(pct_urgent, 1), 'unit': '%', 'good': pct_urgent <= 15, 'hint': '%d solicitudes marcadas urgentes de %d' % (urgent, len(reqs))},
                {'key': 'price', 'label': 'Precio pagado vs. promedio', 'value': round(avg_delta, 1), 'unit': '%', 'good': avg_delta <= 3, 'hint': 'Sobreprecio acumulado: $ %s en %d órdenes' % (f'{overpaid:,.0f}', len(period_pos))},
                {'key': 'stale', 'label': 'OC sin recibir y facturas sin ligar', 'value': len(stale_pos) + len(unlinked_bills), 'unit': '', 'good': (len(stale_pos) + len(unlinked_bills)) == 0, 'hint': '%d órdenes >7 días sin recepción · %d facturas de proveedor sin OC' % (len(stale_pos), len(unlinked_bills))},
            ],
            'queues': queues,
            'requests_by_state': [{'state': state_labels.get(k, k), 'count': v} for k, v in by_state.items()],
            'lead_by_warehouse': [{'warehouse': k, 'days': round(sum(v) / len(v) / 24, 1), 'orders': len(v)} for k, v in sorted(by_wh.items())],
            'contracts': [{'name': c.name, 'partner': c.partner_id.name, 'company': c.company_id.biotex_short_name or c.company_id.name, 'progress': round(c.progress, 1),
                           'remaining': c.amount_remaining, 'days_left': (c.date_end - today).days, 'id': c.id} for c in contracts],
            'price_trend': trend,
            'warehouses': [{'id': w.id, 'name': w.name} for w in env['stock.warehouse'].search([('biotex_is_delegation', '=', True)], order='name')],
        }
