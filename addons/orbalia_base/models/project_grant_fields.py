from odoo import api, fields, models

class ProjectGrant(models.Model):
    _inherit = "project.project"

    organismo = fields.Char(string="Organismo")
    convocatoria = fields.Char(string="Convocatoria")

    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id.id,
    )
    importe_solicitado = fields.Monetary(string="Importe solicitado", currency_field="currency_id")
    importe_concedido = fields.Monetary(string="Importe concedido", currency_field="currency_id")

    fecha_solicitud = fields.Date(string="Fecha de solicitud", default=fields.Date.context_today)
    fecha_resolucion = fields.Date(string="Fecha de resolución")

    grant_state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("submitted", "Presentada"),
            ("awarded", "Concedida"),
            ("rejected", "Rechazada"),
            ("cancel", "Cancelada"),
        ],
        string="Estado subvención",
        default="draft",
    )

    # Botones (cambian sólo el estado de subvención, no el del proyecto)
    def action_submit(self):
        self.write({"grant_state": "submitted"})

    def action_award(self):
        self.write({"grant_state": "awarded"})

    def action_reject(self):
        self.write({"grant_state": "rejected"})

    def action_cancel(self):
        self.write({"grant_state": "cancel"})

    def action_reset(self):
        self.write({"grant_state": "draft"})
