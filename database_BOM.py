import xmlrpc.client

class Database:
    def __init__(self):
        pass
        
    def calling_database(self):
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

        # testing reading the document inside
        # Step 1: Search for the manufacturing order with the name 'BM/MO/....'
        manufacturing_order = models.execute_kw(db, uid, password, 'mrp.production', 'search', [[['name', '=', BoM_name]]], context )

        # Step 2: If the manufacturing order is found, get its move_raw_ids (raw materials)
        if manufacturing_order:
            # Step 3: Read the move_raw_ids for the manufacturing order
            mo_details = models.execute_kw(db, uid, password, 'mrp.production', 'read', [manufacturing_order, ['move_raw_ids']], context )
            
            # Extract the move_raw_ids
            move_raw_ids = mo_details[0]['move_raw_ids']
            print('move_raw_ids', move_raw_ids)
            
            # Step 4: Read details about each stock move (raw material component)
            raw_material_details = models.execute_kw(db, uid, password, 'stock.move', 'read', [move_raw_ids, ['product_id', 'product_uom_qty', 'reserved_availability', 'product_uom']], context )
            
            # Print the list of raw material components
            print("Raw material components:", raw_material_details)
        else:
            print("No manufacturing order found with the name BM/MO/......")

        return raw_material_details, BoM_name






