from odoo import models, fields

class AjouterPoint(models.Model):
    _name = 'ajouter.point'
    _description = 'Ajouter Point'

    type_id = fields.Many2one(
        'my.type',
        string='Type',
        required=True
    )

    user_id = fields.Many2one(
        'res.users',
        string='Utilisateur',
        required=True
    )

    nombre = fields.Float(
        string='Nombre',
        required=True
    )
    date = fields.Date(
        string="Date",
        default=fields.Date.context_today,
        required=True
    )