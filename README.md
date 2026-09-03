# Distribución - Experiencia de usuario

Módulo para **Odoo 19 Enterprise** · Alphaqueb Consulting SAS · Proyecto Biotex.

Capa de experiencia sobre los módulos `biotex_*`, pensada para garantizar la calidad de captura y el entendimiento del estado en todo el ecosistema:

- **Listas de verificación en vivo** (widget `biotex_checklist`) en solicitud de compra, orden de compra, solicitud de pago, contrato, remisión y producto: cada documento explica qué le falta para avanzar, qué bloquea y por qué, con acceso directo a corregir.
- **Panel de claves del contrato** en la remisión (`biotex_contract_keys`): contratado, entregado, pendiente y saldo por clave; un clic agrega la clave a la máscara con la cantidad sugerida.
- **Matriz de existencias por delegación** en el producto (`biotex_stock_matrix`), con semáforo contra la regla de mínimo.
- **Tablero de operación** (acción `biotex_ux.dashboard`): los cinco indicadores acordados con Dirección, colas de trabajo por rol y gráficas con Chart.js.
- Tokens SCSS compartidos (píldoras de estado, barras, tarjetas) para un mismo lenguaje visual en todas las apps.

## Dependencias
`biotex_intercompany` (arrastra los demás), `web`.
