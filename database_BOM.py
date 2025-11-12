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
        parent_MO = str( input("Enter the parent MO: ") )
        child_MO = str( input("Enter the child MO or (B/F): ") )
        is_it_MO = True
        if child_MO.upper() == "B" or child_MO.upper() == "F":
            is_it_MO = False
        else:
            is_it_MO = True



        #authentication
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
        uid = common.authenticate(db, username, password, {})

        #calling methods
        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

        # testing reading the document inside
        # Step 1: Search for the manufacturing order with the name 'BM/MO/....'
        manufacturing_order_parent = models.execute_kw(db, uid, password, 'mrp.production', 'search', [[['name', '=', parent_MO]]], context )

        # Step 2: If the manufacturing order is found, get its move_raw_ids (raw materials)
        if manufacturing_order_parent:
            # Step 3: Read the move_raw_ids for the manufacturing order
            mo_details = models.execute_kw(db, uid, password, 'mrp.production', 'read', [manufacturing_order_parent, ['move_raw_ids']], context )
            
            # Extract the move_raw_ids
            move_raw_ids = mo_details[0]['move_raw_ids']
            #print('move_raw_ids', move_raw_ids)
            
            # Step 4: Read details about each stock move (raw material component)
            raw_material_details = models.execute_kw(db, uid, password, 'stock.move', 'read', [move_raw_ids, ['product_id', 'product_uom_qty', 'quantity', 'product_uom']], context )
            
            # Print the list of raw material components
            #print("Raw material components:", raw_material_details)

            #get the parent MO details
            # Read the product_id field (among others)
            mo_data = models.execute_kw(
                db, uid, password,
                'mrp.production', 'read',
                [manufacturing_order_parent],
                {'fields': ['product_id']}
            )

            # product_id is returned as a list: [id, display_name]
            product_display_name = mo_data[0]['product_id'][1]
            #print("Product being produced:", product_display_name)
        else:
            print("No manufacturing order found with the name BM/MO/......")


        if is_it_MO == True:
            manufacturing_order_child  = models.execute_kw(db, uid, password, 'mrp.production', 'search', [[['name', '=', child_MO]]], context )
            if manufacturing_order_child:
                mo_child_data = models.execute_kw(
                    db, uid, password,
                    'mrp.production', 'read',
                    [manufacturing_order_child],
                    {'fields': ['product_id']}
                )
                child_detail = mo_child_data[0]['product_id'][1]
                if any('fly' in word.lower() for word in child_detail.split()):
                    child_detail = "F"
                else:
                    child_detail = "B"
            else:
                print("No manufacturing order found with the name BM/MO/......")
        else: 
            child_detail = child_MO

        #print("the child detail", child_detail)


        return raw_material_details, parent_MO, product_display_name, child_detail






