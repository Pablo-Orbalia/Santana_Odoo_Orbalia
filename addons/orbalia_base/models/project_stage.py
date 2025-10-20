from odoo import api, fields, models

class OrbaliaProjectStage(models.Model):
    _name = "orbalia.project.stage"
    _description = "Etapa de subvención (Orbalia)"
    _order = "sequence, id"

    name = fields.Char(string="Nombre de la etapa", required=True)
    sequence = fields.Integer(string="Secuencia", default=10, help="Orden de la columna en el kanban.")
    active = fields.Boolean(string="Activa", default=True)
    description = fields.Text(string="Descripción")

    _sql_constraints = [
        ("name_uniq", "unique(name)", "El nombre de la etapa debe ser único."),
    ]

