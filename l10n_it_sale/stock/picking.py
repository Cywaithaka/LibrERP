# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2010-2012 Associazione OpenERP Italia
#    (<http://www.openerp-italia.org>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import orm, fields


class stock_picking(orm.Model):
    _inherit = "stock.picking"
    _columns = {
        'ddt_number': fields.char('DDT', size=64),
        'ddt_date': fields.date('DDT date'),
        'ddt_in_reference': fields.char('In DDT', size=32),
        'ddt_in_date': fields.date('In DDT Date'),
        'cig': fields.char('CIG', size=64, help="Codice identificativo di gara"),
        'cup': fields.char('CUP', size=64, help="Codice unico di Progetto")
    }
    
    def name_get(self, cr, uid, ids, context=None):
        res = []
        for picking in self.browse(cr, uid, ids):
            res.append((picking.id, picking.ddt_number or picking.ddt_in_reference or picking.name))
        return res
        
    def _check_ddt_in_reference_unique(self, cr, uid, ids, context=None):
        #qui và cercato da gli stock.picking quelli che hanno ddt_in_reference e partner_id uguali
        return True

    _constraints = [(_check_ddt_in_reference_unique, 'Error! For a Partner must be only one DDT reference for year.', ['ddt_in_reference', 'partner_id'])]  

    #-----------------------------------------------------------------------------
    # EVITARE LA COPIA DI 'NUMERO DDT'
    #-----------------------------------------------------------------------------
    def copy(self, cr, uid, id, default={}, context=None):
        default = default or {}
        default.update({
            'ddt_number': '',
            'ddt_in_reference': '',
            'cig': '',
            'cup': '',
        })
        if 'ddt_date' not in default:
            default.update({
                'ddt_date': False
            })
        if 'ddt_in_date' not in default:
            default.update({
                'ddt_in_date': False
            })
        if 'cig' not in default:
            default.update({
                'cig': False
            })
        if 'cup' not in default:
            default.update({
                'cup': False
            })

        return super(stock_picking, self).copy(cr, uid, id, default, context)
