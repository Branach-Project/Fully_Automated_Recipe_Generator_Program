from database_BOM import Database
from formatting import Formatting
from docking import Docking
from bay_allocation import BayAllocation
import platform
print(platform.architecture())

loop = True
while loop == True:
    #class initialisation
    #AU batch
    #BM/MO/11794-011
    #BM/MO/14385-001
    #BM/MO/14524-001
    #EU Batch
    # F-LAD FEU 3.9 UTILITY = BM/MO/09544-002
    # F-LAD FEU 5.1 UTILITY = BM/MO/05600-001
    # F-LAD FEU 6.3 UTILITY = BM/MO/05808-002
    # F-LAD FEU 3.9 EN795 FC = BM/MO/06207-001
    # F-LAD FEU 5.1 EN795 FC = BM/MO/06208-001
    # F-LAD FEU 6.3 EN795 FC = BM/MO/06209-001 or BM/MO/13604-004
    # F-LAD FEU 8.7 EN795 FC = BM/MO/06211-001
    database = Database()
    formatting = Formatting()
    generator_docking = Docking()
    bay_allocation = BayAllocation()



    component_list, BoM_name = database.calling_database()
    formatted_componets = formatting.format(str(component_list))
    print("file ---------------------", formatted_componets)

    #fetch position from database
    execute_fly_or_base = generator_docking.run(formatted_componets)

    #bay_allocation.run(execute_fly_or_base, BoM_name)

    






    # press Ctrl + C to break the loop






#test 8.8 = BM/MO/11794-011