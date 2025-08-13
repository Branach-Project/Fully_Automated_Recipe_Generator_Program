import xmlrpc.client
import pandas as pd

# Odoo credentials
url = 'https://branacherp.odoo.com'
db = 'visionsolutions-branach21-staging-4070959'
username = 'harry@branach.com.au'
password = '0774228b8b3546a9ae49a3fb706f2067a60ebc0c'

# Setup XML-RPC endpoints
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})

if not uid:
    raise Exception("Authentication failed")

models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# Step 1: Find the product
product_ids = models.execute_kw(
    db, uid, password,
    'product.product', 'search',
    [[['name', '=', 'F-FCL DAVIT SYS KIT']]],
    {'limit': 1}
)

if not product_ids:
    raise Exception("Product not found.")

product_id = product_ids[0]

# Step 2: Find BOM for that product
bom_ids = models.execute_kw(
    db, uid, password,
    'mrp.bom', 'search',
    [[['product_tmpl_id', '=', product_id]]]
)

if not bom_ids:
    raise Exception("No BOM found for the product.")

bom_id = bom_ids[0]

# Step 3: Get BOM lines
bom_data = models.execute_kw(
    db, uid, password,
    'mrp.bom.line', 'search_read',
    [[['bom_id', '=', bom_id]]],
    {'fields': ['product_id', 'product_qty', 'product_uom_id', 'sequence']}
)

# Process and structure data
bom_list = []
for line in bom_data:
    bom_list.append({
        'Component': line['product_id'][1],
        'Quantity': line['product_qty'],
        'UoM': line['product_uom_id'][1],
        'Sequence': line['sequence']
    })

# Export to Excel
df = pd.DataFrame(bom_list)
df.sort_values(by='Sequence', inplace=True)
df.to_excel("F-FCL_DAVIT_SYS_KIT_BOM.xlsx", index=False)

print("✅ BOM exported successfully to F-FCL_DAVIT_SYS_KIT_BOM.xlsx")
