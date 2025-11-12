from database_BOM import Database
from formatting import Formatting
from recipe_generator import RecipeGenerator
from bay_allocation import BayAllocation
import platform

if __name__ == "__main__":
    print(platform.architecture())

    loop = True
    while loop == True:
        # Class initialisation
        database = Database()
        formatting = Formatting()
        generator = RecipeGenerator()
        bay_allocation = BayAllocation()

        # Fetch data from database
        component_list, BoM_namem, product_display_name, child_detail = database.calling_database()

        # Format data
        formatted_componets = formatting.format(str(component_list))
        print("file ---------------------", formatted_componets)

        # Generate recipe
        execute_fly_or_base = generator.run(formatted_componets, product_display_name, child_detail)

        # Bay allocation (currently commented out)
        # bay_allocation.run(execute_fly_or_base, BoM_name)

        # Press Ctrl + C to break the loop
