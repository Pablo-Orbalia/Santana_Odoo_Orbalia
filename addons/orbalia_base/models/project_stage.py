# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class OrbaliaProjectStage(models.Model):
    _name = 'orbalia.project.stage'
    _description = 'Etapa de expediente'
    _order = 'grant_call_id, sequence, id'
    _rec_name = 'name'

    # -----------------------
    # CAMPOS PRINCIPALES
    # -----------------------
    name = fields.Char(string='Nombre', required=True)
    sequence = fields.Integer(string='Secuencia', default=10, index=True)
    fold = fields.Boolean(string='Plegada por defecto')
    color = fields.Integer(string='Color')
    active = fields.Boolean(default=True)
    description = fields.Text(string='Descripción')

    grant_call_id = fields.Many2one(
        'orbalia.grant.call',
        string='Convocatoria',
        required=True,
        ondelete='cascade',
        help='Embudo o convocatoria a la que pertenece esta etapa.',
    )

    _sql_constraints = [
        ('name_unique_per_call', 'unique(name, grant_call_id)',
         'Ya existe una etapa con ese nombre en esta convocatoria.'),
        ('sequence_unique_per_call', 'unique(grant_call_id, sequence)',
         'Ya existe una etapa con esa secuencia en esta convocatoria.'),
    ]

    # -----------------------
    # UTILIDADES INTERNAS
    # -----------------------
    def _next_sequence_for_call(self, grant_call_id):
        """Devuelve la siguiente secuencia libre (última +10)."""
        last = self.search([('grant_call_id', '=', grant_call_id)], order='sequence desc', limit=1)
        return (last.sequence or 0) + 10

    def _context_grant_call_id(self):
        """Obtiene el ID de convocatoria desde vals o contexto."""
        return (
            self.env.context.get('default_grant_call_id')
            or self.env.context.get('grant_call_id')
            or self.env.context.get('active_id')
        )

    # -----------------------
    # CREATE / WRITE / NAME_CREATE
    # -----------------------
    @api.model
    def create(self, vals):
        gc_id = vals.get('grant_call_id') or self._context_grant_call_id()
        if not gc_id:
            raise ValidationError(_("Debe indicar la convocatoria de la etapa."))

        vals.setdefault('grant_call_id', gc_id)

        # Fija secuencia determinista al final del embudo
        if not vals.get('sequence') or vals.get('sequence') in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
            vals['sequence'] = self._next_sequence_for_call(gc_id)

        return super().create(vals)

    def write(self, vals):
        """Normaliza secuencia cuando se reordena desde el Kanban."""
        for rec in self:
            gc_id = vals.get('grant_call_id', rec.grant_call_id.id)
            seq = vals.get('sequence')
            if seq and seq < 10:
                vals['sequence'] = self._next_sequence_for_call(gc_id)
        return super().write(vals)

    @api.model
    def name_create(self, name):
        """Creación rápida (desde +Etapa en el Kanban)."""
        gc_id = self._context_grant_call_id()
        if not gc_id:
            raise ValidationError(_("Debe indicar la convocatoria de la etapa."))
        vals = {
            'name': name,
            'grant_call_id': gc_id,
            'sequence': self._next_sequence_for_call(gc_id),
        }
        record = self.create(vals)
        return (record.id, record.name)
