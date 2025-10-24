# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class OrbaliaProject(models.Model):
    _name = "orbalia.project"
    _description = "Subvención"
    _order = "create_date desc"

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

    stage_id = fields.Many2one(
        "orbalia.project.stage",
        string="Etapa",
        domain="[('grant_call_id', '=', grant_call_id)]",
        index=True,
        required=True,
        group_expand="_group_expand_stage_id",
    )

    etapa_display = fields.Char(
        string="Etapa display",
        compute="_compute_etapa_display",
        store=False
    )

    grant_call_id = fields.Many2one(
    "orbalia.grant.call",
    string="Subvención",
    index=True,
    required=True,   
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
    # NUEVA LÓGICA: mostrar "title" en lugar de "name"
    # -----------------------
    def name_get(self):
        """Hace que el registro se muestre con el título en lugar del código interno."""
        result = []
        for record in self:
            display = record.title or _("Sin título")
            result.append((record.id, display))
        return result

    @api.depends('title')
    def _compute_display_name(self):
        """Actualiza el display_name para búsquedas y encabezados."""
        for record in self:
            record.display_name = record.title or _("Sin título")

    @api.model
    def _group_expand_stage_id(self, stages, domain, order=None):
        """
        Pintar SOLO las columnas (etapas) de la(s) convocatoria(s) visibles.
        Si no hay convocatoria en domain/context, no devolvemos columnas (evita "globales").
        """
        gc_ids = set()

        # 1) grant_call_id desde el domain del action
        for d in domain or []:
            if isinstance(d, (list, tuple)) and len(d) >= 3 and d[0] == 'grant_call_id' and d[1] in ('=', 'in'):
                if d[1] == '=':
                    gc_ids.add(d[2])
                elif d[1] == 'in' and isinstance(d[2], (list, tuple, set)):
                    gc_ids.update(d[2])

        # 2) Si no vino en domain, intentar por contexto (abrir desde la subvención)
        if not gc_ids:
            ctx_gc = self.env.context.get('default_grant_call_id')
            if ctx_gc:
                gc_ids.add(ctx_gc)

        # 3) Sin convocatoria -> no pintamos columnas
        if not gc_ids:
            return stages.browse()

        dom = [('active', '=', True), ('grant_call_id', 'in', list(gc_ids))]
        return stages.search(dom, order="sequence, id")

    @api.depends('stage_id')
    def _compute_etapa_display(self):
        for record in self:
            record.etapa_display = f"Etapa: {record.stage_id.name or ''}"

