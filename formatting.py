import ast

class Formatting:
    def __init__(self):
        pass

    def format(self, component_list):
        # Get input from the user
        input_str = component_list.strip()
        
        # Convert the input string to a list of dictionaries
        try:
            input_data = ast.literal_eval(input_str)
        except (SyntaxError, ValueError):
            print("Invalid input format. Please provide a valid list of dictionaries.")
            return
        
        # Transform the data
        output_data = self.transform_data(input_data)
        
        # Print the output
        print(output_data)
        
        return output_data

    def transform_data(self, input_data):
        # Initialize an empty string for concatenated output
        transformed_data = ""

        for item in input_data:
            # Extract necessary fields
            product_code = item['product_id'][1]
            product_description = product_code.split('] ')[1] if '] ' in product_code else product_code
            product_quantity = item['product_uom_qty']
            unit = item['product_uom'][1]
            stock_type = 'BM/Stock'
            
            # Calculating the extended quantity (example logic used here, adjust as needed)
            extended_quantity = round(product_quantity * 1.0, 2) if unit == 'Units' else product_quantity
            
            # Format the output
            formatted_entry = f"{product_code}\t{stock_type}\t{product_quantity:.2f}\t{unit}\t{extended_quantity:.2f}"
            
            # Add to the concatenated output string (with no line breaks)
            transformed_data += formatted_entry

        return transformed_data
