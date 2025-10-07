{
    'name': 'Orbalia Base',
    'version': '1.0.0',
    'summary': 'Base de Orbalia (menú y modelo de ejemplo)',
    'category': 'Tools',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'project'],  # 'mail' y 'project' bien añadidos
    'data': [
        'security/ir.model.access.csv',
        'views/project_views.xml',
        'views/res_partner_views.xml',
        # si luego añadimos la secuencia, la pondremos aquí: 'data/sequence.xml',
    ],
    'installable': True,
    'application': True,
}
