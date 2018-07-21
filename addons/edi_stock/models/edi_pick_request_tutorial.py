"""EDI stock transfer request tutorial

This example shows the code required to implement a simple EDI pick
request document format comprising a CSV file with a fixed list of
columns:

* Product code
* Quantity

The picking type will be deduced from the filename by matching against
the sequence prefixes defined for each avaiable picking type.  For
example: a picking type with a prefix "WH/OUT/" will match filenames
starting with "OUT".
"""

import csv
import pathlib
import re
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class EdiDocument(models.Model):
    """Extend ``edi.document`` to include stock transfer tutorial records"""

    _inherit = 'edi.document'

    pick_request_tutorial_ids = fields.One2many(
        'edi.pick.request.tutorial.record', 'doc_id',
        string="Stock Transfer Requests",
    )
    move_request_tutorial_ids = fields.One2many(
        'edi.move.request.tutorial.record', 'doc_id',
        string="Stock Move Requests",
    )


class EdiPickRequestTutorialRecord(models.Model):
    """EDI stock transfer request tutorial record"""

    _name = 'edi.pick.request.tutorial.record'
    _inherit = 'edi.pick.request.record'
    _description = "Stock Transfer Request"


class EdiMoveRequestTutorialRecord(models.Model):
    """EDI stock move request tutorial record"""

    _name = 'edi.move.request.tutorial.record'
    _inherit = 'edi.move.request.record'
    _description = "Stock Move Request"

    pick_request_id = fields.Many2one('edi.pick.request.tutorial.record')


class EdiPickRequestTutorialDocument(models.AbstractModel):
    """EDI stock transfer request tutorial document model"""

    _name = 'edi.pick.request.tutorial.document'
    _inherit = 'edi.pick.request.document'
    _description = "Tutorial stock transfer request CSV file"""

    @api.model
    def pick_types_map(self):
        """Construct a mapping from filenames to picking types

        Construct a mapping from input filenames to picking types,
        using the sequence prefix defined for each picking type.

        For example: the filename "OUT_TEST.CSV" will be mapped to the
        picking type with sequence prefix "WH/OUT/".
        """
        PickingType = self.env['stock.picking.type']
        prefix_test = lambda prefix: re.compile(
            r'%s[\W\d_]' % next(x for x in reversed(prefix.split('/')) if x),
            flags=re.IGNORECASE
        )
        return {
            prefix_test(x.sequence_id.prefix): x
            for x in PickingType.search([]) if x.sequence_id.prefix
        }

    @api.model
    def prepare(self, doc):
        """Prepare document"""
        super().prepare(doc)
        EdiPickRequestRecord = self.pick_request_record_model(doc)
        EdiMoveRequestRecord = self.move_request_record_model(doc)
        PickingType = self.env['stock.picking.type']
        pick_type_map = self.pick_types_map()

        # Create picking for each input attachment
        for fname, data in doc.inputs():

            # Look up picking type based on filename
            pick_type = PickingType.union(*(v for k, v in pick_type_map.items()
                                            if k.match(fname)))
            if not pick_type:
                raise UserError(_("\"%s\" matches no picking types") % fname)
            if len(pick_type) > 1:
                raise UserError(_("\"%s\" matches multiple picking types: %s") %
                                (fname, ", ".join(pick_type.mapped('name'))))

            # Create stock transfer request
            pick_request = EdiPickRequestRecord.create({
                'doc_id': doc.id,
                'name': pathlib.Path(fname).stem,
                'pick_type_id': pick_type.id,
            })

            # Create stock moves
            reader = csv.reader(data.decode().splitlines())
            for line, (product, qty) in enumerate(reader, start=1):
                EdiMoveRequestRecord.create({
                    'doc_id': doc.id,
                    'pick_request_id': pick_request.id,
                    'name': "%04d" % line,
                    'product_key': product,
                    'qty': float(qty),
                })