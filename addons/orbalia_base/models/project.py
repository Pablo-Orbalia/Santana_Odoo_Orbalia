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
        index=True,
        required=True,
        default=lambda self: self.env["orbalia.project.stage"].search([], order="sequence", limit=1).id,
        group_expand="_group_expand_stage_id",   # <- aquí
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
        Mostrar todas las etapas activas aunque no tengan expedientes.
        'stages' es un recordset de orbalia.project.stage.
        'order' puede no venir en tu versión; por eso es opcional.
        """
        return stages.search([('active', '=', True)], order="sequence, id")

