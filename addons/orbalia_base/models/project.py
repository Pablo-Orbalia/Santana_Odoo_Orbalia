# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError  # por si lo usas en otras partes

class OrbaliaProject(models.Model):
    _name = "orbalia.project"
    _description = "Subvención"
    _order = "create_date desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # -----------------------
    # CAMPOS PRINCIPALES
    # -----------------------
    name = fields.Char(
        string="Código",
        required=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("orbalia.grant") or "/",
    )
    title = fields.Char(string="Título de la oportunidad de venta", required=True)
    partner_id = fields.Many2one("res.partner", string="Cuenta")
    organismo = fields.Char(string="Organismo")
    convocatoria = fields.Char(string="Convocatoria")

    company_id = fields.Many2one(
        "res.company", string="Compañía", required=True, default=lambda self: self.env.company
    )
    company_currency_id = fields.Many2one(
        "res.currency", string="Moneda de compañía", related="company_id.currency_id", store=True, readonly=True
    )

    # Importes
    importe_solicitado = fields.Monetary(
        string="Valor de trato", currency_field="company_currency_id", required=True
    )
    importe_concedido = fields.Monetary(
        string="Importe concedido", currency_field="company_currency_id"
    )

    # Fechas
    fecha_solicitud = fields.Date(string="Fecha de solicitud", default=fields.Date.context_today)
    fecha_resolucion = fields.Date(string="Fecha de resolución")
    fecha_justificacion = fields.Date(string="Fecha de justificación")
    fecha_limite_justificacion = fields.Date(string="Fecha límite de justificación")

    # Estado administrativo
    state = fields.Selection([
        ("draft", "Borrador"),
        ("submitted", "Presentada"),
        ("awarded", "Concedida"),
        ("rejected", "Rechazada"),
        ("cancel", "Cancelada"),
    ], string="Estado", default="draft")

    # Embudo / Convocatoria
    grant_call_id = fields.Many2one(
        "orbalia.grant.call",
        string="Subvención",
        index=True,
        required=True,
    )

    # Etapa (columna Kanban)
    stage_id = fields.Many2one(
        "orbalia.project.stage",
        string="Etapa",
        domain="[('grant_call_id', '=', grant_call_id)]",
        index=True,
        required=True,
        group_expand="_group_expand_stage_id",
        ondelete="restrict",
        tracking=True,  # <-- opcional
    )
    title = fields.Char(string="Título de la oportunidad de venta", required=True, tracking=True)
    partner_id = fields.Many2one("res.partner", string="Cuenta", tracking=True)

    # Display auxiliar
    etapa_display = fields.Char(
        string="Etapa display",
        compute="_compute_etapa_display",
        store=False
    )

    # Notas / descripción
    nota = fields.Text(string="Descripción de trato")

    # -----------------------
    # NUEVOS CAMPOS SOLICITADOS
    # -----------------------
    contacto_primario_id = fields.Many2one(
        "res.partner", string="Contacto primario", required=True,
        domain="[('parent_id','=',partner_id)]"
    )
    propietario_trato_id = fields.Many2one(
        "res.users", string="Propietario de trato", required=True, default=lambda self: self.env.user
    )
    fecha_cierre_prevista = fields.Date(string="Fecha de cierre prevista")
    revisor_id = fields.Many2one("res.users", string="Revisor")
    fecha_firma_colaboracion = fields.Date(string="Fecha firma colaboración")
    url_drive = fields.Char(string="URL Drive")
    enlace_colaborador = fields.Char(string="Enlace Colaborador")
    fecha_trato_perdido = fields.Date(string="Fecha trato perdido")
    nombre_subvencion = fields.Char(string="Nombre de la subvención")
    proveedor_id = fields.Many2one("res.partner", string="Proveedor")
    deal_padre_id = fields.Many2one("orbalia.project", string="Deal padre")
    info_acuerdos = fields.Text(string="Información acuerdos")
    punto_solicitud = fields.Char(string="Punto Solicitud")

    # -----------------------
    # TRAZABILIDAD / AUDITORÍA (panel derecho)
    # -----------------------
    last_stage_user_id = fields.Many2one('res.users', string="Usuario del último cambio de etapa", readonly=True)
    last_stage_date = fields.Datetime(string="Fecha último cambio de etapa", readonly=True)

    last_change_user_id = fields.Many2one('res.users', string="Último usuario que modificó", readonly=True)
    last_change_date = fields.Datetime(string="Fecha última modificación", readonly=True)

    # -----------------------
    # ACCIONES DE CAMBIO DE ESTADO
    # -----------------------
    def action_submit(self):
        self.write({"state": "submitted"})

    def action_award(self):
        self.write({"state": "awarded"})

    def action_reject(self):
        self.write({"state": "rejected"})

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_reset(self):
        self.write({"state": "draft"})

    # -----------------------
    # Mostrar "title" como display_name
    # -----------------------
    def name_get(self):
        result = []
        for record in self:
            display = record.title or _("Sin título")
            result.append((record.id, display))
        return result

    @api.depends('title')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.title or _("Sin título")

    # -----------------------
    # Group expand estable por convocatoria
    # -----------------------
    @api.model
    def _group_expand_stage_id(self, stages, domain, order=None):
        """
        Devuelve SOLO las etapas de la(s) convocatoria(s) visibles y en orden estable.
        """
        gc_ids = set()

        # 1) grant_call_id desde el domain
        for token in (domain or []):
            if isinstance(token, (list, tuple)) and len(token) >= 3:
                left, op, right = token[0], token[1], token[2]
                if left == 'grant_call_id' and op in ('=', 'in'):
                    if op == '=':
                        gc_ids.add(right)
                    elif op == 'in' and isinstance(right, (list, tuple, set)):
                        gc_ids.update(right)

        # 2) Contexto
        ctx = self.env.context
        for key in ('default_grant_call_id', 'grant_call_id', 'active_id'):
            if ctx.get(key):
                gc_ids.add(ctx[key])
        active_ids = ctx.get('active_ids') or []
        if isinstance(active_ids, (list, tuple, set)):
            gc_ids.update(active_ids)

        # 3) Sin convocatoria -> no pintamos columnas
        if not gc_ids:
            return stages.browse()

        # 4) Etapas activas de esas convocatorias, orden estable
        dom = [('active', '=', True), ('grant_call_id', 'in', list(gc_ids))]
        return stages.search(dom, order="grant_call_id, sequence, id")

    @api.depends('stage_id')
    def _compute_etapa_display(self):
        for record in self:
            record.etapa_display = f"Etapa: {record.stage_id.name or ''}"

    # -----------------------
    # OVERRIDES PARA TRAZABILIDAD
    # -----------------------
    @api.model
    def create(self, vals):
        # Inicializamos trazabilidad en creación
        now = fields.Datetime.now()
        vals.setdefault('last_change_user_id', self.env.user.id)
        vals.setdefault('last_change_date', now)
        # Si viene etapa en la creación, registramos también trazabilidad de etapa
        if vals.get('stage_id'):
            vals.setdefault('last_stage_user_id', self.env.user.id)
            vals.setdefault('last_stage_date', now)
        record = super().create(vals)
        return record

    def write(self, vals):
        """
        Actualiza:
          - last_stage_user_id / last_stage_date si cambia la etapa.
          - last_change_user_id / last_change_date ante cualquier modificación real.
        """
        now = fields.Datetime.now()
        stage_changed = 'stage_id' in vals and vals.get('stage_id') is not None

        # Siempre que se escribe, hay modificación: registramos usuario/fecha.
        vals.setdefault('last_change_user_id', self.env.user.id)
        vals.setdefault('last_change_date', now)

        if stage_changed:
            vals.setdefault('last_stage_user_id', self.env.user.id)
            vals.setdefault('last_stage_date', now)

        return super().write(vals)
