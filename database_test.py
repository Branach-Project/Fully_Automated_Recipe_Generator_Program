import xmlrpc.client


url = 'https://branacherp.odoo.com'
db = 'visionsolutions-branach21-staging-4070959'
username = 'harry@branach.com.au'
password = '0774228b8b3546a9ae49a3fb706f2067a60ebc0c'

# Create the context with the language setting
context = {'context': {'lang': "en_AU"}}

# What BoM we want to fetch
#test 8.8 = BM/MO/11794-011
#test child = BM/MO/11797-005
BoM_name = str( input("Enter the name of the BoM: ") )

#authentication
common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})

#calling methods
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))


child_MO = models.execute_kw(
    db, uid, password,
    'mrp.production', 'search_read',
    [[['name', '=', BoM_name]]],  # Search criteria
    {
        'fields': ['source_mo_id'],  # Field that links to the parent MO, e.g., 'source_mo_id'
        'context': context
    }
)


manufacturing_order = models.execute_kw(db, uid, password, 'mrp.production', 'search', [[['name', '=', BoM_name]]], context )
mo_details = models.execute_kw(db, uid, password, 'mrp.production', 'read', [manufacturing_order, ['move_raw_ids']], context )
print("mo_details----------------------", child_MO)
