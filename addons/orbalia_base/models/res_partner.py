from odoo import fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"
    es_empresa_operativa = fields.Boolean(string="Es empresa operativa")
