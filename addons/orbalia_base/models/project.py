from odoo import api, fields, models, _

class OrbaliaProject(models.Model):
    _name = "orbalia.project"
    _description = "Subvención"
    _order = "create_date desc"

    name = fields.Char(string="Código", required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('orbalia.grant') or '/')
    title = fields.Char(string="Título", required=True)
    organismo = fields.Char(string="Organismo")
    convocatoria = fields.Char(string="Convocatoria")

    currency_id = fields.Many2one(
        'res.currency', string="Moneda",
        default=lambda self: self.env.company.currency_id.id
    )
    importe_solicitado = fields.Monetary(
        string="Importe solicitado", currency_field='currency_id'
    )
    importe_concedido = fields.Monetary(
        string="Importe concedido", currency_field='currency_id'
    )

    fecha_solicitud = fields.Date(string="Fecha de solicitud", default=fields.Date.context_today)
    fecha_resolucion = fields.Date(string="Fecha de resolución")
    partner_id = fields.Many2one('res.partner', string="Entidad solicitante")
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('submitted', 'Presentada'),
        ('awarded', 'Concedida'),
        ('rejected', 'Rechazada'),
        ('cancel', 'Cancelada'),
    ], string="Estado", default='draft')
    nota = fields.Text(string="Notas")

    def action_submit(self):
        self.write({'state': 'submitted'})
    def action_award(self):
        self.write({'state': 'awarded'})
    def action_reject(self):
        self.write({'state': 'rejected'})
    def action_cancel(self):
        self.write({'state': 'cancel'})
    def action_reset(self):
        self.write({'state': 'draft'})
