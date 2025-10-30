{
    'name': 'Orbalia Base',
    'version': '1.0.2',
    'summary': 'Base de Orbalia (subvenciones con etapas configurables)',
    'category': 'Tools',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'project','contacts'],
    'data': [
        'security/ir.model.access.csv',

        # DATA
        'data/sequence.xml',
        'data/grant_state_data.xml',
        # (opcional) etapas por defecto:
        #'data/project_stage_data.xml',

        # VISTAS
        'views/project_stage_views.xml',
        'views/grant_call_views.xml',
        'views/project_views.xml',
        'views/project_grant_views.xml',
        'views/project_kanban.xml',
        'views/res_partner_views.xml',
    ],
        'assets': {
        'web.assets_backend': [
            'orbalia_base/static/src/css/project_form.css',
        ],
    },
    'installable': True,
    'application': True,
}
