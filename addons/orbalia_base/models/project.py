from odoo import models, fields

class OrbaliaProject(models.Model):
    _name = 'orbalia.project'
    _description = 'Proyecto Orbalia'

    name = fields.Char(string="Nombre del proyecto", required=True)
    description = fields.Text(string="Descripción")
    active = fields.Boolean(string="Activo", default=True)
