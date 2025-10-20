from odoo import api, fields, models, _


class OrbaliaProject(models.Model):
    _name = "orbalia.project"
    _description = "Subvención"
    _order = "create_date desc"

    # Identificación
    name = fields.Char(
        string="Código",
        required=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("orbalia.grant") or "/",
    )
    title = fields.Char(string="Título", required=True)

    # Datos generales
    organismo = fields.Char(string="Organismo")
    convocatoria = fields.Char(string="Convocatoria")
    partner_id = fields.Many2one("res.partner", string="Entidad solicitante")

    # Compañía y moneda
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda de compañía",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # Importes
    importe_solicitado = fields.Monetary(
        string="Importe solicitado",
        currency_field="company_currency_id",
    )
    importe_concedido = fields.Monetary(
        string="Importe concedido",
        currency_field="company_currency_id",
    )

    # Fechas
    fecha_solicitud = fields.Date(
        string="Fecha de solicitud",
        default=fields.Date.context_today,
    )
    fecha_resolucion = fields.Date(string="Fecha de resolución")
    fecha_justificacion = fields.Date(string="Fecha de justificación")
    fecha_limite_justificacion = fields.Date(string="Fecha límite de justificación")

    # Estado administrativo (se mantiene)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("submitted", "Presentada"),
            ("awarded", "Concedida"),
            ("rejected", "Rechazada"),
            ("cancel", "Cancelada"),
        ],
        string="Estado",
        default="draft",
    )

    stage_id = fields.Many2one(
        "orbalia.project.stage",
        string="Etapa",
        index=True,
        required=True,  # ← obligatorio
        default=lambda self: self.env["orbalia.project.stage"].search([], order="sequence", limit=1).id,
    )

    # Notas
    nota = fields.Text(string="Notas")

    # Acciones de cambio de estado administrativo
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
