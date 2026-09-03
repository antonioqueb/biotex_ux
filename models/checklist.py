"""Listas de verificación en vivo: cada documento explica qué le falta para avanzar y por qué.

Estados: ok (cumplido), warn (revisar), error (bloquea), info (contexto). Cada punto puede llevar
una acción para ir directo a corregir. Se renderiza con el widget OWL `biotex_checklist`."""
from odoo import api, fields, models


def item(key, label, state, hint='', action=None, value=None):
    return {'key': key, 'label': label, 'state': state, 'hint': hint, 'action': action, 'value': value}


class PurchaseRequest(models.Model):
    _inherit = 'biotex.purchase.request'

    ux_checklist = fields.Json(compute='_compute_ux_checklist')
    ux_late = fields.Boolean(compute='_compute_ux_late', string='Fecha requerida vencida')

    @api.depends('date_needed', 'state')
    def _compute_ux_late(self):
        today = fields.Date.context_today(self)
        for r in self:
            r.ux_late = bool(r.date_needed and r.date_needed < today and r.state not in ('received', 'cancelled'))

    @api.depends('support_type', 'contract_id', 'contract_id.state', 'contract_id.amount_remaining', 'support_ref', 'partner_id',
                 'line_ids.product_id', 'line_ids.image', 'line_ids.product_qty', 'line_ids.stock_elsewhere_qty', 'line_ids.suggested_supplier_ids',
                 'state', 'company_id', 'company_exception_reason', 'warehouse_id', 'priority', 'is_paid', 'purchase_order_ids.state')
    def _compute_ux_checklist(self):
        for r in self:
            items = []
            # 1. sustento
            if r.support_type == 'contract':
                c = r.contract_id
                if not c:
                    items.append(item('support', 'Sustento: contrato', 'error', 'Seleccione el contrato que respalda la compra.'))
                elif c.state != 'active':
                    items.append(item('support', 'Contrato %s no vigente' % c.name, 'error', 'El contrato está en estado "%s".' % dict(c._fields['state'].selection).get(c.state), {'res_model': 'biotex.contract', 'res_id': c.id}))
                else:
                    pct = c.progress
                    st = 'ok' if pct < c.alert_pct else 'warn'
                    items.append(item('support', 'Contrato %s vigente, %.0f%% consumido' % (c.name, pct), st,
                                      'Saldo disponible %s %s.' % (c.currency_id.symbol, f'{c.amount_remaining:,.2f}'), {'res_model': 'biotex.contract', 'res_id': c.id}))
            elif r.support_type == 'emergent':
                items.append(item('support', 'Compra directa / emergente', 'ok' if (r.partner_id and r.support_ref) else 'error',
                                  'Se requiere institución y número de oficio.' if not (r.partner_id and r.support_ref) else 'Oficio %s de %s.' % (r.support_ref, r.partner_id.name)))
            elif r.support_type == 'private':
                items.append(item('support', 'Cliente privado', 'ok' if r.partner_id else 'error', 'Indique el cliente.' if not r.partner_id else r.partner_id.name))
            else:
                items.append(item('support', 'Reposición de stock mínimo', 'info', 'Solo alta rotación; no acumular para 2-3 meses.'))
            # 2. identificación de producto
            lines = r.line_ids
            unident = lines.filtered(lambda l: not l.product_id)
            if not lines:
                items.append(item('lines', 'Sin productos', 'error', 'Agregue al menos una línea.'))
            elif unident:
                items.append(item('lines', '%d de %d líneas sin clave de catálogo' % (len(unident), len(lines)), 'warn',
                                  'Compras deberá identificar el producto antes de ordenar. Adjunte foto, referencia y marca/modelo del equipo.'))
            else:
                items.append(item('lines', 'Todas las líneas con clave de catálogo', 'ok'))
            # 3. fotos donde la familia lo exige
            need_photo = lines.filtered(lambda l: (not l.product_id and not l.image) or (l.product_id and l.product_id.categ_id.biotex_photo_required and not l.product_id.image_128 and not l.image))
            if need_photo:
                items.append(item('photo', '%d línea(s) requieren foto' % len(need_photo), 'warn', 'Cables, sensores y circuitos requieren foto de conexiones.'))
            # 4. existencias en otras delegaciones
            elsewhere = lines.filtered(lambda l: l.stock_elsewhere_qty >= l.product_qty and l.product_qty > 0)
            if elsewhere:
                items.append(item('stock', '%d línea(s) se cubren por traspaso' % len(elsewhere), 'warn',
                                  'Hay existencia suficiente en otras delegaciones; considere traspaso antes de comprar.'))
            elif lines.filtered('product_id'):
                items.append(item('stock', 'Sin existencia suficiente en otras delegaciones', 'info', 'Procede la compra.'))
            # 5. proveedores conocidos
            no_sup = lines.filtered(lambda l: l.product_id and not l.suggested_supplier_ids)
            if no_sup:
                items.append(item('suppliers', '%d producto(s) sin proveedor conocido' % len(no_sup), 'warn', 'No hay historial ni ficha de proveedor; compras deberá cotizar desde cero.'))
            # 6. razón social
            if not r.is_default_buyer:
                items.append(item('company', 'Razón social distinta a la compradora por defecto', 'ok' if r.company_exception_reason else 'error',
                                  r.company_exception_reason or 'Documente el motivo de excepción.'))
            # 7. flujo
            flow = {'draft': ('Borrador: envíe a autorización', 'info'), 'submitted': ('Esperando autorización del coordinador', 'warn'),
                    'authorized': ('Autorizada: compras puede cotizar u ordenar', 'ok'), 'quoting': ('En cotización', 'info'),
                    'ordered': ('Ordenada' + (' · pago pendiente' if not r.is_paid and any(po.partner_id.biotex_payment_condition == 'cash' for po in r.purchase_order_ids) else ''), 'info'),
                    'paid': ('Pagada: el proveedor debe surtir', 'ok'), 'transit': ('En tránsito con guía', 'info'),
                    'received_partial': ('Recibida parcialmente', 'warn'), 'received': ('Recibida', 'ok'), 'cancelled': ('Cancelada', 'info')}
            label, st = flow.get(r.state, ('', 'info'))
            items.append(item('flow', label, st, r.cancel_reason or ''))
            if r.priority == '1' and r.state not in ('received', 'cancelled'):
                items.append(item('urgent', 'Urgente: compras puede cotizar en paralelo, no ordenar sin autorización', 'warn'))
            r.ux_checklist = {'items': items}


class Remision(models.Model):
    _inherit = 'biotex.remision'

    ux_checklist = fields.Json(compute='_compute_ux_checklist')

    @api.depends('contract_id', 'contract_id.state', 'line_ids.free_qty', 'line_ids.product_qty', 'line_ids.masked_qty', 'mask_ids.amount',
                 'amount_billed', 'amount_delivered', 'state', 'signature', 'signed_by', 'invoice_id', 'is_intercompany', 'support_type', 'warehouse_id')
    def _compute_ux_checklist(self):
        for r in self:
            items = []
            c = r.contract_id
            if r.support_type == 'contract':
                if not c:
                    items.append(item('contract', 'Sin contrato', 'error', 'Seleccione el contrato.'))
                elif c.state != 'active':
                    items.append(item('contract', 'Contrato %s no vigente' % c.name, 'error', '', {'res_model': 'biotex.contract', 'res_id': c.id}))
                else:
                    limit = c.amount_total * (1 + c.tolerance_pct / 100.0)
                    after = c.amount_delivered + (r.amount_billed if r.state in ('draft', 'confirmed') else 0)
                    if c.amount_total and after > limit + 0.005:
                        items.append(item('contract', 'Excede el monto del contrato', 'error',
                                          'Tras esta remisión: %s %s de %s %s (tolerancia %.0f%%).' % (c.currency_id.symbol, f'{after:,.2f}', c.currency_id.symbol, f'{c.amount_total:,.2f}', c.tolerance_pct),
                                          {'res_model': 'biotex.contract', 'res_id': c.id}))
                    else:
                        items.append(item('contract', 'Contrato %s: %.0f%% consumido tras esta remisión' % (c.name, (after / c.amount_total * 100) if c.amount_total else 0), 'ok',
                                          'Saldo después: %s %s.' % (c.currency_id.symbol, f'{(c.amount_total - after):,.2f}'), {'res_model': 'biotex.contract', 'res_id': c.id}))
            # existencias
            short = r.line_ids.filtered(lambda l: l.free_qty < l.product_qty)
            if r.state in ('draft', 'confirmed'):
                if not r.line_ids:
                    items.append(item('stock', 'Sin productos entregados', 'error'))
                elif short and not r.direct_delivery:
                    items.append(item('stock', '%d producto(s) sin existencia suficiente en %s' % (len(short), r.warehouse_id.name), 'error',
                                      'No se remisiona lo que no entró. Reciba o traspase antes.'))
                else:
                    items.append(item('stock', 'Existencia disponible en %s' % r.warehouse_id.name, 'ok'))
            # máscara
            if r.support_type == 'contract':
                if not r.mask_ids:
                    items.append(item('mask', 'Sin claves a cobrar', 'error', 'Asocie lo entregado a la(s) clave(s) del contrato (máscara).'))
                else:
                    diff = abs(r.amount_diff)
                    pct = (diff / r.amount_delivered * 100) if r.amount_delivered else 0
                    unm = r.line_ids.filtered(lambda l: l.masked_qty < l.product_qty)
                    st = 'ok' if pct <= 5 else 'warn'
                    items.append(item('mask', 'Cobro %s %s por %d clave(s), diferencia %.1f%% vs. entregado' % (r.currency_id.symbol, f'{r.amount_billed:,.2f}', len(r.mask_ids), pct), st,
                                      ('%d producto(s) sin clave asociada; se casa por monto.' % len(unm)) if unm else 'Entregado y cobrado cuadran.'))
            if r.is_intercompany:
                items.append(item('inter', 'Multiempresa: inventario de %s, emite %s' % (r.stock_company_id.name, r.company_id.name), 'info',
                                  'Al confirmar se generan venta y compra internas sin traspaso físico.'))
            # firma / factura
            if r.state in ('delivered', 'signed', 'invoiced'):
                items.append(item('sign', 'Firmada por %s' % r.signed_by if r.signature else 'Sin firma del cliente', 'ok' if r.signature else 'warn',
                                  '' if r.signature else 'Suba la foto de la remisión firmada o capture la firma en pantalla.'))
            if r.state in ('signed', 'invoiced'):
                items.append(item('invoice', 'Facturada: %s' % r.invoice_id.name if r.invoice_id else 'Pendiente de facturar', 'ok' if r.invoice_id else 'info',
                                  '', {'res_model': 'account.move', 'res_id': r.invoice_id.id} if r.invoice_id else None))
            r.ux_checklist = {'items': items}


class Contract(models.Model):
    _inherit = 'biotex.contract'

    ux_checklist = fields.Json(compute='_compute_ux_checklist')

    @api.depends('state', 'date_start', 'date_end', 'amount_total', 'amount_delivered', 'progress', 'alert_pct', 'line_ids.product_id', 'warehouse_ids', 'amount_invoiced')
    def _compute_ux_checklist(self):
        today = fields.Date.context_today(self)
        for c in self:
            items = []
            if c.state == 'active':
                total_days = max((c.date_end - c.date_start).days, 1)
                elapsed = min(max((today - c.date_start).days, 0), total_days)
                time_pct = elapsed / total_days * 100
                left = (c.date_end - today).days
                items.append(item('time', '%d días de vigencia restantes (%.0f%% del plazo transcurrido)' % (left, time_pct), 'warn' if left <= 30 else 'ok'))
                gap = c.progress - time_pct
                if c.delivery_mode != 'total':
                    st = 'ok' if abs(gap) <= 15 else 'warn'
                    items.append(item('pace', 'Avance %.0f%% del monto vs. %.0f%% del tiempo' % (c.progress, time_pct), st,
                                      'Ritmo de entrega adelantado.' if gap > 15 else ('Ritmo de entrega atrasado: riesgo de no agotar el contrato.' if gap < -15 else 'Ritmo acorde al calendario.')))
                if c.progress >= c.alert_pct:
                    items.append(item('limit', 'Cerca del límite: %.0f%% consumido' % c.progress, 'warn', 'Saldo %s %s.' % (c.currency_id.symbol, f'{c.amount_remaining:,.2f}')))
            elif c.state == 'draft':
                items.append(item('state', 'Borrador: active el contrato cuando esté firmado', 'info'))
            else:
                items.append(item('state', dict(c._fields['state'].selection).get(c.state), 'info'))
            noprod = c.line_ids.filtered(lambda l: not l.product_id)
            if noprod:
                items.append(item('keys', '%d clave(s) sin producto de catálogo' % len(noprod), 'warn', 'La máscara será manual en cada remisión.'))
            else:
                items.append(item('keys', '%d claves ligadas al catálogo' % len(c.line_ids), 'ok'))
            if not c.warehouse_ids:
                items.append(item('wh', 'Sin delegación asignada', 'warn', 'No se precargará en las solicitudes de ninguna delegación.'))
            unbilled = c.amount_delivered - c.amount_invoiced
            if unbilled > 0.005:
                items.append(item('bill', 'Remisionado sin facturar: %s %s' % (c.currency_id.symbol, f'{unbilled:,.2f}'), 'warn', 'Agrupe remisiones y facture.'))
            c.ux_checklist = {'items': items}


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ux_checklist = fields.Json(compute='_compute_ux_checklist')

    @api.depends('categ_id', 'default_code', 'biotex_name', 'biotex_measure', 'biotex_content', 'biotex_brand_id', 'biotex_reference', 'barcode',
                 'image_1920', 'biotex_image_2', 'biotex_image_3', 'biotex_photo_waived', 'seller_ids', 'biotex_synonym_ids', 'list_price', 'standard_price', 'biotex_equipment_ids')
    def _compute_ux_checklist(self):
        for p in self:
            items = []
            fam_ok = p.categ_id.biotex_level == 'family'
            items.append(item('family', 'Familia: %s' % p.categ_id.complete_name if fam_ok else 'Sin familia', 'ok' if fam_ok else 'error', '' if fam_ok else 'Use el asistente de clasificación.'))
            items.append(item('code', 'Clave %s' % p.default_code if p.default_code else 'Sin clave', 'ok' if p.default_code else 'error', '' if p.default_code else 'Se asigna al clasificar en una familia.'))
            desc_ok = bool(p.biotex_name and p.biotex_measure)
            items.append(item('desc', 'Descripción estructurada (nombre + medida + contenido)', 'ok' if desc_ok else 'error', '' if desc_ok else 'Capture nombre base y medida; el contenido es opcional.'))
            items.append(item('brand', 'Marca: %s' % p.biotex_brand_id.name if p.biotex_brand_id else 'Sin marca', 'ok' if p.biotex_brand_id else 'error'))
            if p.biotex_reference:
                items.append(item('ref', 'Referencia del fabricante %s' % p.biotex_reference, 'ok'))
            elif p.barcode:
                items.append(item('ref', 'Código propio %s (etiqueta QR)' % p.barcode, 'ok', 'Producto sin referencia de fabricante.'))
            else:
                items.append(item('ref', 'Sin referencia ni código propio', 'warn', 'Se asignará código propio al dar de alta la clave.'))
            photos = p.biotex_photo_count
            if photos:
                items.append(item('photo', '%d foto(s)' % photos, 'ok'))
            elif p.biotex_photo_waived:
                items.append(item('photo', 'Sin foto, autorizado por Dirección', 'warn'))
            elif p.categ_id.biotex_photo_required:
                items.append(item('photo', 'Sin foto: la familia la exige', 'error', 'No se marcará completo sin foto.'))
            else:
                items.append(item('photo', 'Sin foto (opcional en esta familia)', 'info'))
            if p.categ_id.biotex_code in ('CAB', 'SEN', 'CIR') and not p.biotex_equipment_ids:
                items.append(item('equip', 'Sin equipo compatible', 'warn', 'Cables, sensores y circuitos deben indicar marca y modelo del equipo.'))
            items.append(item('supplier', '%d proveedor(es) en ficha' % len(p.seller_ids) if p.seller_ids else 'Sin proveedor en ficha', 'ok' if p.seller_ids else 'warn',
                              '' if p.seller_ids else 'Se completa con la primera compra confirmada.'))
            if not p.biotex_synonym_ids:
                items.append(item('syn', 'Sin sinónimos', 'info', 'Agregue nombres coloquiales (ambú, punzocat) para que todos lo encuentren.'))
            if p.list_price and p.standard_price and p.list_price <= p.standard_price:
                items.append(item('price', 'Precio de venta menor o igual al costo', 'warn'))
            p.ux_checklist = {'items': items}


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    ux_checklist = fields.Json(compute='_compute_ux_checklist')

    @api.depends('state', 'biotex_request_id', 'biotex_is_default_buyer', 'biotex_company_exception_reason', 'order_line.biotex_price_alert',
                 'biotex_price_justification', 'partner_id.biotex_payment_condition', 'biotex_payment_state', 'biotex_transit_state', 'biotex_warehouse_id',
                 'partner_id.biotex_requires_formal_po', 'partner_id.biotex_incomplete', 'biotex_internal')
    def _compute_ux_checklist(self):
        for po in self:
            items = []
            if po.biotex_internal:
                items.append(item('internal', 'Compra interna entre razones sociales (sin recepción física)', 'info'))
            req = po.biotex_request_id
            if req:
                items.append(item('support', 'Solicitud %s · %s' % (req.name, req.contract_id.name or dict(req._fields['support_type'].selection).get(req.support_type)),
                                  'ok' if req.state not in ('draft', 'submitted') else 'error',
                                  'Autorizada por %s' % req.authorized_by_id.name if req.authorized_by_id else 'La solicitud no está autorizada.',
                                  {'res_model': 'biotex.purchase.request', 'res_id': req.id}))
            elif not po.biotex_internal:
                items.append(item('support', 'Sin solicitud de compra ligada', 'warn', 'Lo que no está en sistema no se compra: ligue la OC a un folio.'))
            if not po.biotex_is_default_buyer:
                items.append(item('company', 'Razón social distinta a la compradora por defecto', 'ok' if po.biotex_company_exception_reason else 'error', po.biotex_company_exception_reason or 'Documente la excepción.'))
            bad = po.order_line.filtered('biotex_price_alert')
            if bad:
                items.append(item('price', '%d línea(s) por encima del promedio histórico' % len(bad), 'ok' if po.biotex_price_justification else 'error',
                                  po.biotex_price_justification or 'Capture la justificación de precio para confirmar.'))
            elif po.order_line:
                items.append(item('price', 'Precios dentro del promedio histórico', 'ok'))
            cond = po.partner_id.biotex_payment_condition
            if cond == 'cash':
                pay = {'none': ('Contado: se generará solicitud de pago al confirmar', 'info'), 'pending': ('Contado: pago pendiente en la cola de administración', 'warn'), 'paid': ('Contado: pagada', 'ok')}[po.biotex_payment_state]
                items.append(item('pay', pay[0], pay[1]))
            else:
                items.append(item('pay', 'Crédito: el proveedor surte sin pago previo', 'ok'))
            if po.partner_id.biotex_requires_formal_po:
                items.append(item('formal', 'El proveedor exige orden de compra formal (PDF)', 'info', 'Envíe la OC por correo; WhatsApp no aplica.'))
            if po.partner_id.biotex_incomplete:
                items.append(item('partner', 'Proveedor con datos pendientes (alta ágil)', 'warn', 'Complete RFC y datos fiscales antes de la factura.'))
            items.append(item('dest', 'Destino: %s' % po.biotex_warehouse_id.name if po.biotex_warehouse_id else 'Sin delegación destino', 'ok' if po.biotex_warehouse_id else 'error'))
            if po.state in ('purchase', 'done') and not po.biotex_internal:
                tr = {'none': ('Sin guía registrada', 'warn'), 'in_transit': ('En tránsito', 'info'), 'arrived': ('Llegó: registre la recepción', 'warn'), 'received': ('Recibida', 'ok'), 'partial': ('Recibida parcialmente', 'warn')}[po.biotex_transit_state]
                items.append(item('transit', tr[0], tr[1]))
            po.ux_checklist = {'items': items}


class PaymentRequest(models.Model):
    _inherit = 'biotex.payment.request'

    ux_checklist = fields.Json(compute='_compute_ux_checklist')

    @api.depends('state', 'proof', 'payment_reference', 'date_needed', 'days_waiting', 'amount', 'amount_order', 'bank_account', 'partner_id.biotex_incomplete')
    def _compute_ux_checklist(self):
        today = fields.Date.context_today(self)
        for p in self:
            items = []
            if p.amount and p.amount_order and abs(p.amount - p.amount_order) > 0.01:
                items.append(item('amount', 'Monto distinto al total de la OC (%s %s)' % (p.currency_id.symbol, f'{p.amount_order:,.2f}'), 'warn', 'Anticipo o pago parcial: indíquelo en notas.'))
            items.append(item('bank', 'Cuenta bancaria del proveedor' + (': %s' % p.bank_account if p.bank_account else ' no capturada'), 'ok' if p.bank_account else 'warn'))
            if p.state in ('requested', 'approved'):
                if p.date_needed and p.date_needed < today:
                    items.append(item('due', 'Fecha límite vencida (%s)' % p.date_needed, 'error', 'El proveedor no surte hasta recibir el pago.'))
                elif p.date_needed:
                    items.append(item('due', 'Pagar antes del %s' % p.date_needed, 'warn' if (p.date_needed - today).days <= 2 else 'ok'))
                items.append(item('wait', '%d día(s) en espera' % p.days_waiting, 'warn' if p.days_waiting > 3 else 'ok'))
                items.append(item('proof', 'Comprobante o referencia al pagar', 'info', 'Adjunte el comprobante o capture la referencia SPEI para registrar el pago.'))
            elif p.state == 'paid':
                items.append(item('proof', 'Pagada el %s · %s' % (p.date_paid, p.payment_reference or 'comprobante adjunto'), 'ok'))
            if p.partner_id.biotex_incomplete:
                items.append(item('partner', 'Proveedor con datos pendientes', 'warn', 'Verifique RFC y cuenta antes de transferir.'))
            p.ux_checklist = {'items': items}
