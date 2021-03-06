# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2013-2014 Didotech SRL (info at didotech.com)
#                          All Rights Reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from openerp.osv import orm, fields
import decimal_precision as dp
import netsvc
from tools import ustr


class sale_order_confirm_line(orm.TransientModel):
    def _amount_line(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            price_subtotal = self.calc_price_subtotal(line.quantity, line.discount, line.price_unit)
            res[line.id] = price_subtotal

        return res

    _name = "sale.order.confirm.line"
    _rec_name = 'product_id'
    _columns = {
        'order_id': fields.integer('Order Reference'),
        'sale_line_id': fields.many2one('sale.order.line', 'Order Line Reference'),
        'product_id': fields.many2one('product.product', string='Product', ondelete='CASCADE'),
        'name': fields.char('Description', size=256, select=True, readonly=True),
        'sequence': fields.integer('Sequence'),
        'price_unit': fields.float('Unit Price', digits_compute=dp.get_precision('Sale Price')),
        'price_subtotal': fields.function(_amount_line, string='Subtotal', digits_compute=dp.get_precision('Sale Price')),
        'quantity': fields.float('Quantity', digits_compute=dp.get_precision('Product UoM')),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure', ondelete='CASCADE'),
        'discount': fields.float('Discount (%)', digits=(16, 2)),
        'wizard_id': fields.many2one('sale.order.confirm', string="Wizard", ondelete='CASCADE'),
        'changed': fields.boolean('Changed'),
        'tax_id': fields.many2many('account.tax', string='Taxes')
    }
    _order = 'sequence, id'
    _defaults = {
        'quantity': 1.0,
        'discount': 0.0
    }

    def onchange_product(self, cr, uid, ids, product_id, product_qty, sale_order_id, context=None):
        if context is None:
            context = {}
        result = {}
        
        sale_order = self.pool['sale.order'].browse(cr, uid, sale_order_id, context=context)
        product = self.pool['product.product'].browse(cr, uid, product_id, context=context)
        if product.default_code:
            result['name'] = '[%s] %s' % (product.default_code, product.name)
        else:
            result['name'] = '%s' % (product.name)
        
        if sale_order.pricelist_id:
            result['price_unit'] = self.pool['product.pricelist'].price_get(cr, uid, [sale_order.pricelist_id.id],
                                                                            product_id, product_qty or 1.0, sale_order.partner_id.id,
                                                                            dict(
                                                                                context,
                                                                                uom=product.uom_id.id,
                                                                                date=sale_order.date_order,
                                                                            ))[sale_order.pricelist_id.id]
        else:
            result['price_unit'] = product.list_price or 0.0
        
        result['product_uom'] = product.uom_id.id
        result['changed'] = True
        result['discount'] = 0
        tax_ids = [tax_id.id for tax_id in product.taxes_id]
        result['tax_id'] = [(6, 0, tax_ids)]
        
        return {'value': result}

    def onchange_qty(self, cr, uid, ids, product_id, product_qty, discount, price_unit, sale_order_id, context):
        result = {}
        sale_order = self.pool['sale.order'].browse(cr, uid, sale_order_id, context=context)
        product = self.pool['product.product'].browse(cr, uid, product_id, context=context)
        
        if product_id and sale_order.pricelist_id:
            
            result['price_unit'] = self.pool['product.pricelist'].price_get(cr, uid, [sale_order.pricelist_id.id],
                                                                            product_id, product_qty or 1.0, sale_order.partner_id.id,
                                                                            dict(
                                                                                context,
                                                                                uom=product.uom_id.id,
                                                                                date=sale_order.date_order,
                                                                            ))[sale_order.pricelist_id.id]
            price_unit = result['price_unit']
        
        result['price_subtotal'] = self.calc_price_subtotal(product_qty, discount, price_unit)
        result['changed'] = True
        return {'value': result}

    def onchange_discount(self, cr, uid, ids, quantity, discount, price_unit):
        result = {}
        result['price_subtotal'] = self.calc_price_subtotal(quantity, discount, price_unit)
        result['changed'] = True
        return {'value': result}

    def onchange_price(self, cr, uid, ids, quantity, discount, price_unit):
        result = {}
        
        result['price_subtotal'] = self.calc_price_subtotal(quantity, discount, price_unit)
        result['changed'] = True
        return {'value': result}
    
    def calc_price_subtotal(self, quantity, discount, price_unit):
        products_price = price_unit * quantity
        discount_price = (discount or 0.0) * products_price / 100
        price_subtotal = products_price - discount_price
        return price_subtotal


class sale_order_confirm(orm.TransientModel):
    _name = "sale.order.confirm"
    _description = "Confirm wizard for Sale order"

    _columns = {
        'client_order_ref': fields.char('Customer Reference', size=64, required=True),
        'order_date': fields.date('Date', required=True),
        'sale_order_id': fields.integer('Order'),
        'new_sale_order': fields.boolean('New Sale Order'),
        'confirm_line': fields.one2many('sale.order.confirm.line', 'wizard_id', 'Products'),
    }
    
    def get_generic_product(self, cr, uid):
        product_ids = self.pool['product.product'].search(cr, uid, [('name', '=', 'Generic product')])
        if product_ids:
            return product_ids[0]
        else:
            uom_id = 1
            price = 1.0
            
            return self.pool['product.product'].create(cr, uid, {
                'name': 'Generic product',
                'uom_id': uom_id,
                'uom_po_id': uom_id,
                'cost_price': price,
                'min_cost_price': price * 0.5,
                'max_cost_price': price * 1.5,
                
            })

    def default_get(self, cr, uid, fields, context=None):
        sale_order_obj = self.pool['sale.order']
        sale_order_line_obj = self.pool['sale.order.line']
        # sale_order_confirm_line_obj = self.pool['sale.order.confirm.line')
        
        if context is None:
            context = {}
            
        res = super(sale_order_confirm, self).default_get(cr, uid, fields, context=context)

        sale_order_data = sale_order_obj.read(cr, uid, context['active_ids'][0], ['id', 'date_order', 'order_line', 'pricelist_id', 'partner_id'])

        res['order_date'] = sale_order_data['date_order']
        res['sale_order_id'] = sale_order_data['id']
        res['pricelist_id'] = sale_order_data['pricelist_id'] and sale_order_data['pricelist_id'][0] or False
        res['partner_id'] = sale_order_data['partner_id'] and sale_order_data['partner_id'][0] or False
        res['new_sale_order'] = False
        sale_order_confirm_line_list = []
        
        sale_order_lines = sale_order_line_obj.browse(cr, uid, sale_order_data['order_line'])
        for sale_order_line in sale_order_lines:
            products_price = sale_order_line.price_unit * sale_order_line.product_uom_qty
            discount_price = (sale_order_line.discount or 0.0) * products_price / 100
            
            if sale_order_line.product_id:
                product_id = sale_order_line.product_id.id
            else:
                product_id = self.get_generic_product(cr, uid)
                
            if sale_order_line.tax_id:
                tax_id = [(6, 0, [tax_id.id for tax_id in sale_order_line.tax_id])]
            else:
                product = self.pool['product.product'].browse(cr, uid, product_id, context)
                tax_id = [(6, 0, [tax_id.id for tax_id in product.taxes_id])]
                sale_order_line_obj.write(cr, uid, sale_order_line.id, {'tax_id': tax_id})
            
            sale_order_confirm_line_list.append({
                'order_id': sale_order_data['id'],
                'sale_line_id': sale_order_line.id,
                'name': sale_order_line.name,
                'product_id': product_id,
                'sequence': sale_order_line.sequence,
                'price_unit': sale_order_line.price_unit,
                'quantity': sale_order_line.product_uom_qty,
                'product_uom': sale_order_line.product_uom.id,
                'discount': sale_order_line.discount,
                'changed': False,
                'tax_id': tax_id,
                'price_subtotal': products_price - discount_price
            })
        res.update(confirm_line=sale_order_confirm_line_list)
        return res
    
    def onchange_line(self, cr, uid, ids, confirm_lines):
        result = {
            'new_sale_order': False
        }
        for confirm_line in confirm_lines:
            if (isinstance(confirm_line[2], dict)) and ('changed' in confirm_line[2]) and (confirm_line[2]['changed']):
                result['new_sale_order'] = True
        return {'value': result}

    def sale_order_confirmated(self, cr, uid, ids, context=None):
        sale_order_obj = self.pool['sale.order']
        sale_order_line_obj = self.pool['sale.order.line']
        sale_order_confirm_line_obj = self.pool['sale.order.confirm.line']
        wf_service = netsvc.LocalService("workflow")
        
        sale_order_confirm_data = self.read(cr, uid, ids[0], ['order_date', 'sale_order_id', 'new_sale_order', 'confirm_line', 'client_order_ref', 'order_date'])
        order_id = False
        if sale_order_confirm_data['new_sale_order']:
            old_sale_order_data = sale_order_obj.read(cr, uid, sale_order_confirm_data['sale_order_id'], ['shop_id', 'partner_id', 'partner_order_id', 'partner_invoice_id', 'partner_shipping_id', 'pricelist_id', 'sale_version_id', 'version', 'name', 'order_policy', 'picking_policy', 'invoice_quantity', 'section_id', 'categ_id'])
            new_sale_order = {}
            for key in ('shop_id', 'partner_id', 'partner_order_id', 'partner_invoice_id', 'partner_shipping_id', 'pricelist_id'):
                new_sale_order[key] = old_sale_order_data[key][0]
            for key in ('picking_policy', 'order_policy', 'invoice_quantity'):
                new_sale_order[key] = old_sale_order_data[key]
            
            if not old_sale_order_data['sale_version_id']:
                old_sale_order_name = old_sale_order_data['name'] + u" V.2"
                old_sale_order_data['version'] = 2
                new_sale_order['sale_version_id'] = old_sale_order_data['id']
            else:
                old_sale_order_name = old_sale_order_data['sale_version_id'][1] + u" V." + ustr(old_sale_order_data['version'] + 1)
                new_sale_order['sale_version_id'] = old_sale_order_data['sale_version_id'][0]
            
            new_sale_order.update({
                'version': old_sale_order_data['version'] + 1,
                'name': old_sale_order_name,
                'client_order_ref': sale_order_confirm_data['client_order_ref'],
                'date_order': sale_order_confirm_data['order_date'],
            })
            # qui creo il nuovo sale.order
            context['versioning'] = True
            order_id = sale_order_obj.create(cr, uid, new_sale_order, context=context)

            sequence = 10
            for sale_order_confirm_line_id in sale_order_confirm_data['confirm_line']:
                sale_order_confirm_line_data = sale_order_confirm_line_obj.browse(cr, uid, sale_order_confirm_line_id)

                if sale_order_confirm_line_data.product_uom:
                    product_uom = sale_order_confirm_line_data.product_uom.id
                else:
                    product_uom = False
                
                tax_ids = [tax.id for tax in sale_order_confirm_line_data.tax_id]

                sale_order_line_obj.create(cr, uid, {
                    'product_id': sale_order_confirm_line_data.product_id.id,
                    'name': sale_order_confirm_line_data.product_id.name_get()[0][1],
                    'product_uom_qty': sale_order_confirm_line_data.quantity,
                    'product_uom': product_uom,
                    'price_unit': sale_order_confirm_line_data.price_unit,
                    'discount': sale_order_confirm_line_data.discount,
                    'sequence': sequence,
                    'order_id': int(order_id),
                    'delay': 7.0,
                    'tax_id': [(6, 0, tax_ids)],
                    'sale_line_copy_id': sale_order_confirm_line_data.sale_line_id.id or None
                }, context=context)
                
                sequence += 1
            wf_service.trg_validate(uid, 'sale.order', order_id, 'order_confirm', cr)
            # wf_service.trg_validate(uid, 'sale.order', sale_order_confirm_data['sale_order_id'], 'cancel', cr)
            sale_order_obj.write(cr, uid, sale_order_confirm_data['sale_order_id'], {'active': False})
        else:
            sale_order_obj.write(cr, uid, sale_order_confirm_data['sale_order_id'], {
                'customer_validation': True,
                'client_order_ref': sale_order_confirm_data['client_order_ref'],
                'date_order': sale_order_confirm_data['order_date'],
            })
            wf_service.trg_validate(uid, 'sale.order', sale_order_confirm_data['sale_order_id'], 'order_confirm', cr)
         
        mod_obj = self.pool['ir.model.data']
        res = mod_obj.get_object_reference(cr, uid, 'sale', 'view_order_form')
        res_id = res and res[1] or False,

        if order_id:
            result = {
                'type': 'ir.actions.act_window',
                'name': 'Sale Order',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': res_id,
                'res_model': 'sale.order',
                'nodestroy': True,
                'target': 'current',
                'res_id': order_id,
            }
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result
