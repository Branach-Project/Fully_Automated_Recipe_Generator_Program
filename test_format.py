""" Working for structured input """

def transform_data(input_data):
    transformed_data = []

    for item in input_data:
        # Extract necessary fields
        product_code = item['product_id'][1]
        product_description = product_code.split('] ')[1] if '] ' in product_code else product_code
        product_quantity = item['product_uom_qty']
        unit = item['product_uom'][1]
        stock_type = 'BM/Stock'
        
        # Calculating the extended quantity (example logic used here, adjust as needed)
        extended_quantity = round(product_quantity * 1.0, 2) if unit == 'Unit' else product_quantity
        
        # Format the output
        formatted_entry = f"{product_code}\t{product_description}\t{stock_type}\t{product_quantity:.2f}\t{unit}\t{extended_quantity:.2f}"
        
        # Add to the transformed data list
        transformed_data.append(formatted_entry)

    return transformed_data


# Example input
input_data = [
    {'id': 247091, 'product_id': [15860, '[BP-LBL-0050-01] C-LBL PLT DONT CLIMB'], 'product_uom_qty': 13.0, 'reserved_availability': 0.0, 'product_uom': [1, 'Units']},
    {'id': 247092, 'product_id': [16059, '[BP-LEV-8001-02] F-ACC LRG SWL FOOT ASS'], 'product_uom_qty': 4.0, 'reserved_availability': 0.0, 'product_uom': [1, 'Units']},
    {'id': 247093, 'product_id': [16012, '[BP-LEV-0012-04] C-ACC LS CONN PIN'], 'product_uom_qty': 4.0, 'reserved_availability': 0.0, 'product_uom': [1, 'Units']},
]


# Transforming data
output_data = transform_data(input_data)

# Printing the output
for line in output_data:
    print(line)
