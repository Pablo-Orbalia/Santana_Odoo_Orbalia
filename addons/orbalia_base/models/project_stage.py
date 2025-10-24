# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class OrbaliaProjectStage(models.Model):
    _name = 'orbalia.project.stage'
    _description = 'Etapa de expediente'
    _order = 'sequence, id'
    _rec_name = 'name'

    name = fields.Char(string='Nombre', required=True)
    sequence = fields.Integer(string='Secuencia', default=10, index=True)
    fold = fields.Boolean(string='Plegada por defecto')
    color = fields.Integer(string='Color')
    active = fields.Boolean(default=True)

    # 🔧 Nuevo campo para cubrir referencias existentes
    description = fields.Text(string='Descripción')

    grant_call_id = fields.Many2one(
        'orbalia.grant.call',
        string='Convocatoria',
        required=True,
        ondelete='cascade',
        help='Embudo/convocatoria a la que pertenece esta etapa.',
    )

    _sql_constraints = [
        ('name_unique_per_call', 'unique(name, grant_call_id)',
         'Ya existe una etapa con ese nombre en esta convocatoria.'),
        ('sequence_unique_per_call', 'unique(grant_call_id, sequence)',
         'Ya existe una etapa con esa secuencia en esta convocatoria.'),
    ]

    @api.model
    def create(self, vals):
        # Obliga a indicar convocatoria; evita etapas "globales"
        gc_id = vals.get('grant_call_id') or self.env.context.get('default_grant_call_id')
        if not gc_id:
            raise ValidationError(_("Debe indicar la convocatoria de la etapa."))

        vals.setdefault('grant_call_id', gc_id)

        # Colocar al final del embudo (sequence determinista por convocatoria)
        last = self.search([('grant_call_id', '=', gc_id)], order='sequence desc', limit=1)
        next_seq = (last.sequence or 0) + 10
        if 'sequence' not in vals or (vals.get('sequence') == 10 and last):
            vals['sequence'] = next_seq

        return super().create(vals)

    def write(self, vals):
        for rec in self:
            new_gc = vals.get('grant_call_id', rec.grant_call_id.id)
            new_seq = vals.get('sequence', rec.sequence)
            if 'grant_call_id' in vals and new_gc != rec.grant_call_id.id:
                last = self.search([('grant_call_id', '=', new_gc)], order='sequence desc', limit=1)
                vals.setdefault('sequence', (last.sequence or 0) + 10)
            if 'sequence' in vals:
                if new_seq in (None, 0):
                    last = self.search([('grant_call_id', '=', new_gc)], order='sequence desc', limit=1)
                    vals['sequence'] = (last.sequence or 0) + 10
                else:
                    clash = self.search([
                        ('id', '!=', rec.id),
                        ('grant_call_id', '=', new_gc),
                        ('sequence', '=', new_seq),
                    ], limit=1)
                    if clash:
                        last = self.search([('grant_call_id', '=', new_gc)], order='sequence desc', limit=1)
                        vals['sequence'] = (last.sequence or 0) + 10
        return super().write(vals)
