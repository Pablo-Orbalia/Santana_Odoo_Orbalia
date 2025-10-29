# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
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

    # NUEVO: Comunidad Autónoma (desplegable simple)
    ccaa = fields.Selection(selection=[
        ('AND', 'Andalucía'),
        ('ARA', 'Aragón'),
        ('AST', 'Principado de Asturias'),
        ('BAL', 'Illes Balears'),
        ('CAN', 'Canarias'),
        ('CNT', 'Cantabria'),
        ('CLM', 'Castilla-La Mancha'),
        ('CYL', 'Castilla y León'),
        ('CAT', 'Cataluña'),
        ('VAL', 'Comunitat Valenciana'),
        ('EXT', 'Extremadura'),
        ('GAL', 'Galicia'),
        ('RIO', 'La Rioja'),
        ('MAD', 'Comunidad de Madrid'),
        ('MUR', 'Región de Murcia'),
        ('NAV', 'Comunidad Foral de Navarra'),
        ('PV',  'País Vasco'),
        ('CEU', 'Ciudad Autónoma de Ceuta'),
        ('MEL', 'Ciudad Autónoma de Melilla'),
    ], string="Comunidad Autónoma", index=True)

    # NUEVO: etapa Kanban (para ver TODAS las columnas)
    state_stage_id = fields.Many2one(
        'orbalia.grant.state',
        string='Estado',
        compute='_compute_state_stage',
        inverse='_inverse_state_stage',
        store=True,
        required=True,
        group_expand='_group_expand_state_stage',
        help='Etapa Kanban sincronizada con "estado".'
    )

    fecha_publicacion = fields.Date(string="Fecha de publicación")
    fecha_limite = fields.Date(string="Fecha límite de presentación")
    notas = fields.Text(string="Notas")

    company_id = fields.Many2one(
        "res.company", string="Compañía", required=True, default=lambda self: self.env.company
    )

    project_ids = fields.One2many("orbalia.project", "grant_call_id", string="Expedientes")
    project_count = fields.Integer(compute="_compute_project_count", string="Nº expedientes")

    @api.depends('project_ids')
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    # --- Sincronización estado <-> etapa Kanban ---
    @api.depends('estado')
    def _compute_state_stage(self):
        State = self.env['orbalia.grant.state'].sudo()
        cache = {s.code: s.id for s in State.search([])}
        for rec in self:
            rec.state_stage_id = cache.get(rec.estado)

    def _inverse_state_stage(self):
        for rec in self:
            if rec.state_stage_id and rec.estado != rec.state_stage_id.code:
                rec.estado = rec.state_stage_id.code

    @api.model
    def _group_expand_state_stage(self, stages, domain, order=None):
        return self.env['orbalia.grant.state'].search([('active', '=', True)], order='sequence, id')

    # --- Acción: abrir expedientes de esta subvención ---
    def action_open_projects_kanban(self):
        self.ensure_one()
        act = self.env.ref('orbalia_base.action_orbalia_project', raise_if_not_found=False)
        action = (act.read()[0]) if act else {
            'type': 'ir.actions.act_window',
            'name': _('Expedientes'),
            'res_model': 'orbalia.project',
            'view_mode': 'kanban,tree,form',
        }
        raw_ctx = action.get('context', {}) or {}
        if isinstance(raw_ctx, str):
            try:
                raw_ctx = literal_eval(raw_ctx)
            except Exception:
                raw_ctx = {}
        raw_ctx.update({'default_grant_call_id': self.id, 'search_default_group_by_stage': 1, 'default_stage_id': False})
        action['context'] = raw_ctx
        action['domain'] = [('grant_call_id', '=', self.id)]
        action['name'] = _("Expedientes · %s") % (self.display_name,)
        action['view_mode'] = action.get('view_mode') or 'kanban,tree,form'
        return action

    # --- Protección de borrado ---
    def unlink(self):
        for rec in self:
            if rec.project_ids:
                raise ValidationError(_("No se puede eliminar la subvención '%s' porque tiene %d expedientes asociados.")
                                      % (rec.display_name, len(rec.project_ids)))
        return super().unlink()
