# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from ast import literal_eval


class OrbaliaGrantCall(models.Model):
    _name = "orbalia.grant.call"
    _description = "Subvención / Convocatoria"
    _order = "fecha_publicacion desc, name"

    # -----------------------
    # CAMPOS
    # -----------------------
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
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company
    )

    # Expedientes vinculados a esta convocatoria
    project_ids = fields.One2many(
        "orbalia.project", "grant_call_id", string="Expedientes"
    )
    project_count = fields.Integer(
        compute="_compute_project_count",
        string="Nº expedientes"
    )

    # -----------------------
    # CÓMPUTOS
    # -----------------------
    @api.depends('project_ids')
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    # -----------------------
    # ACCIONES
    # -----------------------
    def action_open_projects_kanban(self):
        """
        Abre el embudo (Kanban) de expedientes filtrado por ESTA convocatoria,
        y con el contexto necesario para que las creaciones (proyectos y etapas
        vía quick-create) queden ligadas a esta subvención.
        """
        self.ensure_one()

        # Intentamos leer la acción estándar; si no existe, construimos una ad-hoc
        act = self.env.ref('orbalia_base.action_orbalia_project', raise_if_not_found=False)
        action = (act.read()[0]) if act else {
            'type': 'ir.actions.act_window',
            'name': _('Expedientes'),
            'res_model': 'orbalia.project',
            'view_mode': 'kanban,tree,form',
        }

        # Normalizar contexto de la acción
        raw_ctx = action.get('context', {}) or {}
        if isinstance(raw_ctx, str):
            try:
                raw_ctx = literal_eval(raw_ctx)
            except Exception:
                raw_ctx = {}

        raw_ctx.update({
            'default_grant_call_id': self.id,
            'search_default_group_by_stage': 1,
            'default_stage_id': False,
        })
        action['context'] = raw_ctx

        # Filtro por la convocatoria actual
        action['domain'] = [('grant_call_id', '=', self.id)]

        # Título más informativo
        action['name'] = _("Expedientes · %s") % (self.display_name,)

        # Asegurar modos de vista
        action['view_mode'] = action.get('view_mode') or 'kanban,tree,form'

        return action

    # -----------------------
    # RESTRICCIÓN DE BORRADO
    # -----------------------
    def unlink(self):
        """
        Impide eliminar la subvención si tiene expedientes asociados.
        """
        for rec in self:
            if rec.project_ids:
                # Mensaje claro para usuario final
                raise ValidationError(_(
                    "No se puede eliminar la subvención '%s' porque tiene %d expedientes asociados."
                ) % (rec.display_name, len(rec.project_ids)))
        return super().unlink()
