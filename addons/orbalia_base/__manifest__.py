{
    'name': 'Orbalia Base',
    'version': '1.0.1',
    'summary': 'Base de Orbalia (menú y modelo de ejemplo)',
    'category': 'Tools',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'project'],
    'data': [
        'security/ir.model.access.csv',

        # DATA (opcional si creaste la secuencia)
        'data/sequence.xml',

        # VISTAS
        'views/project_views.xml',          # vistas del modelo orbalia.project
        'views/project_grant_views.xml',
        'views/project_kanban.xml',     # herencia de project.project (usar modifiers)
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': True,
}
