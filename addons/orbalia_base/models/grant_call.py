# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from ast import literal_eval

class OrbaliaGrantCall(models.Model):
    _name = "orbalia.grant.call"
    _description = "Subvención / Convocatoria"
    _order = "fecha_publicacion desc, name"

    name = fields.Char(string="Nombre de la subvención", required=True)
    organismo = fields.Char(string="Organismo")
    anio = fields.Char(string="Año")
    estado = fields.Selection([
        ('borrador', 'Borrador'),
        ('abierta', 'Abierta'),
        ('cerrada', 'Cerrada'),
        ('resuelta', 'Resuelta'),
        ('archivada', 'Archivada'),
    ], string="Estado", default='abierta', index=True)

    fecha_publicacion = fields.Date(string="Fecha de publicación")
    fecha_limite = fields.Date(string="Fecha límite de presentación")
    notas = fields.Text(string="Notas")

    company_id = fields.Many2one(
        "res.company", string="Compañía",
        required=True, default=lambda self: self.env.company
    )

    # ✅ Debe ser orbalia.project
    project_ids = fields.One2many(
        "orbalia.project", "grant_call_id", string="Expedientes"
    )
    project_count = fields.Integer(compute="_compute_project_count", string="Nº expedientes")

    @api.depends('project_ids')
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    def action_open_projects_kanban(self):
        """Abre el kanban de expedientes filtrado por esta subvención."""
        self.ensure_one()
        # lee la acción del pipeline de expedientes (ajusta el XML-ID si fuera distinto)
        action = self.env.ref('orbalia_base.action_orbalia_project').read()[0]

        # Asegurar que context es un dict
        raw_ctx = action.get('context', {}) or {}
        if isinstance(raw_ctx, str):
            try:
                raw_ctx = literal_eval(raw_ctx)
            except Exception:
                raw_ctx = {}

        # Actualiza context y otros campos de la acción
        raw_ctx.update({
            'search_default_group_by_stage': 1,   # agrupar por etapa
            'default_grant_call_id': self.id,     # al crear, hereda la subvención
        })
        action['context'] = raw_ctx

        # Filtra expedientes de esta subvención
        action['domain'] = [('grant_call_id', '=', self.id)]
        action['name'] = _("Expedientes · %s") % (self.display_name,)
        action['view_mode'] = 'kanban,list,form'

        return action

