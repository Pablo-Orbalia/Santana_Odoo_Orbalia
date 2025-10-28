# -*- coding: utf-8 -*-
from odoo import api, fields, models

class OrbaliaGrantState(models.Model):
    _name = 'orbalia.grant.state'
    _description = 'Etapa/Estado Kanban de Subvención'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código técnico', required=True, index=True)  # p.ej. 'borrador'
    sequence = fields.Integer(string='Secuencia', default=10, index=True)
    fold = fields.Boolean(string='Plegada por defecto')
    color = fields.Integer(string='Color')
    active = fields.Boolean(default=True)

    @api.model
    def _group_expand_states(self, states, domain, order=None):
        # Utilidad si quisieras usarlo desde otros modelos
        return self.search([('active', '=', True)], order='sequence, id')
