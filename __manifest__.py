{
    'name': 'Distribución - Experiencia de usuario',
    'summary': 'Listas de verificación en vivo por documento, panel de claves del contrato en la remisión, matriz de existencias por delegación y tablero de operación con los cinco indicadores',
    'version': '19.0.1.0.0',
    'category': 'Distribución de insumos',
    'author': 'Alphaqueb Consulting SAS',
    'license': 'LGPL-3',
    'icon': '/biotex_ux/static/description/icon.svg',
    'depends': ['biotex_intercompany', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_request_views.xml',
        'views/remision_views.xml',
        'views/contract_views.xml',
        'views/product_views.xml',
        'views/purchase_order_views.xml',
        'views/payment_request_views.xml',
        'views/dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biotex_ux/static/src/scss/*.scss',
            'biotex_ux/static/src/**/*.js',
            'biotex_ux/static/src/**/*.xml',
        ],
    },
    'installable': True,
}
