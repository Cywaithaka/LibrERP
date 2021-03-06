# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#
#    Copyright (C) 2014 Didotech srl (<http://www.didotech.com>).
#
#                       All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import orm, fields
from openerp.tools.translate import _
from product._common import rounding
import datetime
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT


class account_analytic_line(orm.Model):
    _inherit = 'account.analytic.line'
    
    def _get_selection_list(self, cr, uid, context=None):
        #@return a list of tuples. tuples containing model name and name of the record
        model_obj = self.pool['ir.model']
        ids = model_obj.search(cr, uid, [('name', 'not ilike', '.')])
        res = model_obj.read(cr, uid, ids, ['model', 'name'])
        return [(r['model'], r['name']) for r in res] + [('', '')]
    
    _columns = {
        'origin_document': fields.reference("Origin Document", selection=_get_selection_list, size=None)
    }
    
    def get_cost_amount(self, cr, uid, product, product_qty, context=None):
        price_unit_precision = self.pool['decimal.precision'].precision_get(cr, uid, 'Sale Price')
        if product.is_kit:
            bom_obj = self.pool['mrp.bom']
            amount = 0.0
            for bom in product.bom_lines:
                bom_product_ids = bom_obj.search(cr, uid, [('bom_id', '=', bom.id)])
                bom_products = bom_obj.browse(cr, uid, bom_product_ids)
                for bom_product in bom_products:
                    if not bom_product.product_id.product_tmpl_id.type == 'service':
                        amount += bom_product.product_id.standard_price * bom_product.product_qty
            return rounding(amount * product_qty, 10 ** - price_unit_precision)
        else:
            return rounding(product.standard_price * product_qty, 10 ** - price_unit_precision)
    
    def update_or_create_line(self, cr, uid, values, context=None):
        '''
            values = {
                'name': expense_line.name,
                'product': expense_line.product_id,
                'product_qty': expense_line.unit_quantity,
                'product_uom': expense_line.uom_id,  # Optional, is not required.
                'account_id': expense_line.analytic_account.id,
                'unit_amount': values.get('unit_amount', False),  # Optional, is not required
                'date': expense_line.date_value + ' 00:00:00',
                'ref': hr_expense.name,
                'origin_document': expense_line
            }
        '''
        
        journals = {
            'hr.expense.line': {'journal': 'expense_journal_id', 'name': _('Expense Journal')},
            'stock.move': {'journal': 'delivery_note_journal_id', 'name': _('Delivery Note Journal')}
        }
        
        if values.get('account_id', False):
            user = self.pool['res.users'].browse(cr, uid, uid, context)
            
            journal = getattr(user.company_id, journals[values['origin_document']._name]['journal'])
            if journal:
                journal_id = journal.id
            else:
                raise orm.except_orm('Error', _('{journal} is not defined for this company').format(journal=journals[values['origin_document']._name]['name']))
            
            product_qty = values.get('product_qty', 1)
            price_unit_precision = self.pool['decimal.precision'].precision_get(cr, uid, 'Sale Price')
            
            if values.get('unit_amount', False):
                amount = rounding(values['unit_amount'] * product_qty, 10 ** - price_unit_precision)
            elif values.get('product', False):
                amount = self.get_cost_amount(cr, uid, values['product'], product_qty, context)
            else:
                return False
            
            if values.get('product', False):
                general_account_id = values['product'].product_tmpl_id.property_account_expense.id
                
                if not general_account_id:
                    general_account_id = values['product'].categ_id.property_account_expense_categ.id
                if not general_account_id:
                    raise orm.except_orm(_('Error!'),
                                         _('''There is no expense account defined
                                            for this product: "{0}" (id:{1})''').format(values['product'].name, values['product'].id,))
            else:
                general_account_id = False
            
            line_date = datetime.datetime.strptime(values['date'], DEFAULT_SERVER_DATETIME_FORMAT)
            line_date = datetime.date(year=line_date.year, month=line_date.month, day=line_date.day)
            
            analytic_line_ids = self.search(cr, uid, [('origin_document', '=', '{model}, {document_id}'.format(model=values['origin_document']._name, document_id=values['origin_document'].id))], context)

            if analytic_line_ids:
                return self.write(cr, uid, analytic_line_ids, {
                    'amount': -amount,
                    'user_id': uid,
                    'name': values['name'],
                    'unit_amount': product_qty,  # What a strange idea to call product_qty unit_amount!!!
                    'date': line_date,
                    'company_id': user.company_id.id,
                    'account_id': values['account_id'],
                    'general_account_id': general_account_id,
                    'product_id': values['product'].id,
                    'product_uom_id': values.get('product_uom', values['product'].uom_id.id),
                    'journal_id': journal_id,
                    'amount_currency': 0.0,
                    'ref': values.get('ref', False),
                    'origin_document': '{model}, {document_id}'.format(model=values['origin_document']._name, document_id=values['origin_document'].id)
                }, context)
            else:
                return self.create(cr, uid, {
                    'amount': -amount,
                    'user_id': uid,
                    'name': values['name'],
                    'unit_amount': product_qty,
                    'date': line_date,
                    'company_id': user.company_id.id,
                    'account_id': values['account_id'],
                    'general_account_id': general_account_id,
                    'product_id': values['product'].id,
                    'product_uom_id': values.get('product_uom', values['product'].uom_id.id),
                    'journal_id': journal_id,
                    'amount_currency': 0.0,
                    'ref': values.get('ref', False),
                    'origin_document': '{model}, {document_id}'.format(model=values['origin_document']._name, document_id=values['origin_document'].id)
                }, context)
        else:
            return False
