from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BloquerAgent(models.Model):
    _name = 'bloquer.agent'
    _description = 'Blocage Agent'

    user_id = fields.Many2one(
        'res.users',
        string='Agent',
        required=True,
        domain=lambda self: [
            ('groups_id', 'in', self.env.ref('access_rights_groups.group_agent').id)
        ]
    )

    date_debut = fields.Date(
        string='Date début',
        required=True
    )

    date_fin = fields.Date(
        string='Date fin',
        required=True
    )

    motif = fields.Text(
        string='Motif',
    )

    active = fields.Boolean(
        string='Actif',
        default=True
    )

    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rec in self:
            if rec.date_fin < rec.date_debut:
                raise ValidationError("La date de fin doit être postérieure à la date de début.")