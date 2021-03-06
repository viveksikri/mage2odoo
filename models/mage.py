from openerp.osv import osv, fields
from openerp.tools.translate import _
from pprint import pprint as pp


class MageSetup(osv.osv):
    _name = 'mage.setup'
    _columns = {
	'name': fields.char('Name', required=True),
	'debug_mode': fields.selection([('none', 'None'), ('error', 'Error'), ('debug', 'All')],
	string='Debug Mode', help="None: This will not log any messages to Sentry.\n" \
		"Error: This will send only error events to Sentry\n" \
		"All: This will send every event, success and failure to Sentry"),
	'sentry_dsn': fields.char('Sentry DSN', help="Exception Messages wil be sent to the logging server"),
	'url': fields.char('URL', required=True),
	'integrity_product': fields.many2one('product.product', 'Product Deleted Replacement', help="Select a product to use in the case a product returned on an order has been deleted from Magento"),
	'import_images': fields.boolean('Import Images'),
	'import_images_method': fields.selection([
		('standalone', 'Separately'),
		('withproduct', 'With Products')], 'Images Import Method'),
	'images_storage': fields.selection([
		('database', 'Database'),
		('filesystem', 'Filesystem (Not yet supported)')], 'Image Storage Method'),
	'username': fields.char('Username', required=True),
	'default_fiscal_position': fields.many2one('account.fiscal.position', 'Default Fiscal Position', help="This will assign a fiscal position to all orders"),
	'import_disabled_products': fields.boolean('Import Disabled Products'),
	'password': fields.char('Password', required=True, help="This is the API Key for Magento"),
	'default_shipping_partner': fields.many2one('res.partner', 'Default Shipping Partner', help="This will assign a required partner to any shipping method that is created"),
	'shipping_product': fields.many2one('product.product', \
		'Shipping Product', domain="[('type', '=', 'service')]", help="Only service products can be used here"),
	'picking_policy': fields.selection([
		('direct', 'Deliver each product when available'),
		('one', 'Deliver all products at once')], 'Shipping Policy'
	),
	'last_imported_customer': fields.integer('Last Imported Customer', help="When syncing customers, start at a given id"),
	'pay_sale_if_paid': fields.boolean('Pay Sale in Odoo if Paid in Magento', help="This wil pay the sale order on a deferred scheduled basis if the order status is paid in Magento.\nThis feature requires the module mage2odoo_sale_automation"),
	'use_invoice_date': fields.boolean('Use Invoice Date from Magento'),
	'deliver_if_delivered': fields.boolean('Delivery automatic if Delivered in Magento', help="Create and fulfill the sales order automatically if it is fulfilled in Magento.\nThis feature requires the module mage2odoo_sale_automation"),
	'use_order_date_as_delivery_date': fields.boolean('Use Order Date as Delivery Date'),
	'use_order_date': fields.boolean('Use Order Date from Magento'),
	'default_product_tax': fields.many2one('account.tax', 'Default Tax', help="If this box is checked, tax will be applied to all products"),
	'nontaxable_tax_class_id': fields.char('Nontaxable Class Id', help="This field can be used to not apply tax even with default tax applied"),
        'invoice_policy': fields.selection([
                ('manual', 'On Demand'),
                ('picking', 'On Delivery Order'),
                ('prepaid', 'Before Delivery')], 'Invoice Policy'
	),
	'states_or_statuses': fields.selection([('status', 'Import by Status'), ('state', 'Import by State')],
	string='Import by Status or State', required=True),
        'order_statuses': fields.many2many('mage.mapping.order.state', 'mage_setup_import_status_rel', 'status_id', \
                'storeview_id', 'Import Order Statuses'
        ),

    }

    def create(self, cr, uid, vals, context=None):
        new_id = super(MageSetup, self).create(cr, uid, vals, context)
	self.create_mage_jobs(cr, uid, new_id)

        return new_id


#    def write(self, cr, uid, ids, vals, context=None):
#	if isinstance(ids, (int, long)):
#	    ids = [ids]
#	res = super(MageSetup, self).write(cr, uid, ids, vals, context=context)


    def create_mage_jobs(self, cr, uid, mage_id, context=None):
	model_obj = self.pool.get('ir.model')
	job_obj = self.pool.get('mage.job')
	mapping_obj = self.pool.get('mage.mapping')
	setup = self.browse(cr, uid, mage_id)
	from defaults import *
	#This will always be present if the module is installed
	integrator_id = model_obj.search(cr, uid, [('model', '=', 'mage.integrator')])[0]

	for job_vals in DEFAULT_JOBS:
	    job_name = setup.name + ' : ' + job_vals['name']
	    job = {'name': job_name,
		   'python_model': integrator_id,
		   'python_function_name': job_vals['python_function_name'],
		   'mage_instance': mage_id,
		   'job_type': job_vals['job_type'],
	    }

	    if job_vals['mapping_name']:
		model_ids = model_obj.search(cr, uid, [('model', '=', job_vals['mapping_model_name'])])
		if model_ids:
	            mapping_vals = {
				'name': job_vals['mapping_name'],
				'model_id': model_ids[0],
		    }
		    mapping_id = mapping_obj.create(cr, uid, mapping_vals)
		    mapping_lines = self.create_default_mappinglines(cr, uid, job_vals, mapping_id)
		    job['mapping'] = mapping_id

	    job_id = job_obj.create(cr, uid, job)

	    if job_vals['scheduler']:
		job_obj.button_schedule_mage_job(cr, uid, [job_id])

	return True


    def create_default_mappinglines(self, cr, uid, job_vals, mapping_id):
	field_obj = self.pool.get('ir.model.fields')
	line_obj = self.pool.get('mage.mapping.line')
	for f in job_vals['mapping_lines']:
		field_ids = field_obj.search(cr, uid, \
			[('name', '=', f['field_name']), ('model', '=', f['field_model'])])
		if field_ids:
		    vals = {
			'external_type': f['external_type'],
			'function_name': f['function_name'],
			'mage_fieldname': f['mage_fieldname'],
			'mapping_type': f['mapping_type'],
			'type': f['type'],
			'field': field_ids[0],
			'mapping': mapping_id,
		    }
		    line = line_obj.create(cr, uid, vals)
	return True


class MageWebsite(osv.osv):
    _name = 'mage.website'
    _columns = {
	'name': fields.char('Name'),
	'code': fields.char('Code'),
	'is_default': fields.boolean('Default Website'),
	'default_store_group': fields.many2one('mage.store.group', 'Default Store Group'),
	'sort_order': fields.integer('Sort Order'),
	'external_id': fields.integer('External Id'),
#	'store_groups': fields.one2many('mage.store.group', 'website', 'Stores'),
    }


    def prepare_odoo_record_vals(self, cr, uid, job, record, context=None):
        return {
            'is_default': record['is_default'],
            'external_id': record['website_id'],
            'code': record['code'],
            'sort_order': record['sort_order'],
            'name': record['name'],
        }


class MageStoreGroup(osv.osv):
    _name = 'mage.store.group'
    _columns = {
        'name': fields.char('Name'),
        'website': fields.many2one('mage.website', 'Website'),
        'external_id': fields.integer('External Id'),
	'default_store_view': fields.many2one('mage.store.view', 'Default Store View'),
	'store_views': fields.one2many('mage.store.view', 'store', 'Store Views'),
    }


    def prepare_odoo_record_vals(self, cr, uid, job, record, context=None):
	website_obj = self.pool.get('mage.website')
        return {
                'website': website_obj.get_mage_record(cr, uid, record['website_id']),
                'external_id': record['group_id'],
                'name': record['name'],
        }


class MageStoreView(osv.osv):
    _name = 'mage.store.view'
    _columns = {
        'name': fields.char('Name'),
	'store': fields.many2one('mage.store.group', 'Store Group'),
	'code': fields.char('Code'),
	'website': fields.many2one('mage.website', 'Website'),
        'picking_policy': fields.selection([
                ('direct', 'Deliver each product when available'),
                ('one', 'Deliver all products at once')], 'Shipping Policy'
        ),
        'invoice_policy': fields.selection([
                ('manual', 'On Demand'),
                ('picking', 'On Delivery Order'),
                ('prepaid', 'Before Delivery')], 'Invoice Policy'
        ),
	'skip_order_status': fields.boolean('Do not change status on Magento'),
	'do_not_import': fields.boolean('Do Not Import'),
	'external_id': fields.integer('External Id'),
	'sort_order': fields.integer('Sort Order'),
	'odoo_guest_customer': fields.many2one('res.partner', 'Stealth Checkout Customer'),
	'import_orders_start_datetime': fields.datetime('Import Orders from This Time'),
	'import_orders_end_datetime': fields.datetime('Import Orders To This Time'),
	'warehouse': fields.many2one('stock.warehouse', 'Warehouse'),
	'last_import_datetime': fields.datetime('Last Imported At'),
	'last_export_datetime': fields.datetime('Last Exported At'),
	'order_prefix': fields.char('Order Prefix'),
	'allow_storeview_level_statuses': fields.boolean('Allow storeview level status configuration'),
	'order_statuses': fields.many2many('mage.mapping.order.state', 'mage_store_view_import_status_rel', 'status_id', \
                'storeview_id', 'Import Order Statuses'
	),
    }

    _defaults = {
	'do_not_export': False,
    }


    def prepare_odoo_record_vals(self, cr, uid, job, record, context=None):
	website_obj = self.pool.get('mage.website')
	group_obj = self.pool.get('mage.store.group')
        return {
		'website': website_obj.get_mage_record(cr, uid, record['website_id']),
                'code': record['code'],
                'name': record['name'],
                'sort_order': record['sort_order'],
                'external_id': record['store_id'],
                'store': group_obj.get_mage_record(cr, uid, record['group_id']),

        }


class MageMappingOrderState(osv.osv):
    _name = 'mage.mapping.order.state'
    _name_get = 'mage_order_status_name'
    _columns = {
	'name': fields.char('Name'),
	'mage_order_state': fields.char('Magento Order State'),
	'mage_order_status': fields.char('Magento Order Status'),
	'mage_order_status_name': fields.char('Magento Order Status Name'),
	'odoo_order_state': fields.selection([
		('draft', 'Draft Quotation'),
		('sent', 'Quotation Sent'),
		('cancel', 'Cancelled'),
		('waiting_date', 'Waiting Schedule'),
		('progress', 'Sales Order'),
		('manual', 'Sale to Invoice'),
		('shipping_except', 'Shipping Exception'),
		('invoice_except', 'Invoice Exception'),
		('done', 'Done')], 'Odoo Order Status'
	),
    }
