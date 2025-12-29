from odoo import models, fields

class Type(models.Model):
    _name = 'my.type'
    _description = 'Type'

    name = fields.Char(
        string='Performance',
        required=True
    )