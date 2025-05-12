"""
This python script generates the 'recipe' files, which are taken by the TM12 Robot Arm so that it knows where to drill holes
Input: Copy paste list of branach parts in Manufacturing Order BOM (Odoo>Operations>Manufacturing Orders)

Output: Generates 'testB' and 'testF' recipe files. Because we are generating extention ladder drill recipes, there is always a base and a fly
"""




import os
import time
import ast
import re
import sys
import numpy as np


# venv_path = os.path.abspath("dir X:\\CAD\\E091-01 Manufacturing Info System\\.venv\\Scripts")
# print('wefwefwfewfwefwefwe')
# os.system("dir X:\CAD\E091-01 Manufacturing Info System")
# os.system(os.path.join(venv_path, "activate.bat"))


# venv_scripts_path = "X:\CAD\E091-01 Manufacturing Info System\.venv\Scripts"  # Adjust if necessary
# os.chdir(venv_scripts_path)  # Change the working directory
# os.system("activate.bat")


import pyodbc


# You can ignore the initial values, these are all usually inferred later from parts IDs
global RungCount
RungCount = 13
global Pitch
Pitch = 305
global DistEndToLastRungCut
DistEndToLastRungCut = {
    "F": 305,
    "B": 305
} 
global StileLength
StileLength = 3555
global DistEndToFirstRungRaw
DistEndToFirstRungRaw = 290
global SectionWidth
SectionWidth = 450

global StileWallThickness


# These are constant
global StileWidth
StileWidth = 30
global StileHeight
StileHeight = 76

# we expect coordinates on specific faces to lay on a specific plane. The stile 76 tall in the z direction when flat
# Base section is 450 mm wide and Fly section is 367 mm wide. each stile is 30mm thick (y direction)
# ORDER LU LO LI LD RU RO RI RD
expected_plane = {
        'F': [[0,0] , [ 2 , StileHeight/2], [ 1 , 183.5 ], [ 1 , 183.5 - StileWidth], [ 2 , -StileHeight/2], [ 2 , StileHeight/2], [1, -183.5], [ 1, -183.5 + StileWidth], [2 , -StileHeight/2 ]],
        'B': [[0,0] , [ 2 , StileHeight/2], [ 1 , 195 + StileWidth], [ 1 , 195], [ 2 , -StileHeight/2], [ 2 , StileHeight/2], [1, -195 - StileWidth], [ 1, -195], [2 , -StileHeight/2 ]]
    }

# Next check if the coordinate is within a certain range
# RU and RD y in range(-sectionwidth/2 , -sectionwidth/2 + stilewidth)
# LU and LD y in range(sectionwidth/2 - stilewidth, sectionwidth/2)
# RI and RO and LI and RI in z range(-stileHeight/2, stileHeight/2)
# first element is the axis x = 0 , y = 1, z = 2
expected_range = {
        'F': [[0,0] , [ 1, 183.5 - StileWidth, 183.5 ], [ 2 , -StileHeight/2, StileHeight/2 ], [ 2 , -StileHeight/2, StileHeight/2 ], [ 1, 183.5 - StileWidth, 183.5], [ 1, - 183.5, -183.5 + StileWidth], [ 2 , -StileHeight/2, StileHeight/2 ], [ 2 , -StileHeight/2, StileHeight/2 ], [1, - 183.5, -183.5 + StileWidth]],
        'B': [[0,0] , [ 1, 195 , 195 + StileWidth], [ 2 , -StileHeight/2, StileHeight/2 ], [ 2 , -StileHeight/2, StileHeight/2 ], [ 1, 195, 195 + StileWidth], [ 1, - 195 - StileWidth, -195 ], [ 2 , -StileHeight/2, StileHeight/2 ], [ 2 , -StileHeight/2, StileHeight/2 ], [1, - 195 - StileWidth, -195]]
}


# need to verify lengths of EU sections. They seem wrong
# The EU sections are the ones that are 0.1 smaller. 3.8, 5.1 etc
section_data = [
    [3.9, 'B', 2065, 6],
    [3.9, 'F', 2403, 8],
    [4.0, 'B', 2380, 7],
    [4.0, 'F', 2455, 7],
    [5.1, 'B', 2665, 8],
    [5.1, 'F', 3003, 10],
    [5.2, 'B', 2990, 9],
    [5.2, 'F', 3065, 9],
    [6.3, 'B', 3265, 10],
    [6.3, 'F', 3603, 12],
    [6.4, 'B', 3600, 11],
    [6.4, 'F', 3675, 11],
    [7.5, 'B', 3865, 12],
    [7.5, 'F', 4203, 14],
    [7.6, 'B', 4210, 13],
    [7.6, 'F', 4285, 13],
    [8.7, 'B', 4465, 14],
    [8.7, 'F', 4803, 16],
    [8.8, 'B', 4820, 15],
    [8.8, 'F', 4895, 15],
    [9.4, 'B', 5430, 17],
    [9.4, 'F', 5505, 17],
    [9.8, 'B', 5430, 17],
    [9.8, 'F', 5505, 17]
]



# Because all of the formulas are written in the MSaccess database as a string, we need to be able to safely execute that string
# Essentially, we don't want any unexpected functions to run, and want to limit the operations that can be done.
allowed_operations = ['+', '-', '*', '/']
allowed_functions = ['DistEndToLastRungCut', 'RungCount', 'Pitch', 'SectionWidth', 'DistEndToFirstRungRaw', 'StileLength'] 

def is_valid_formula(formula):
  """Checks if a formula is valid based on allowed operations, functions, and parentheses.
  Input: String (formula)
  
  Returns: Boolean (true/false)

  """

  # 1. Remove spaces and empty brackets
  formula = formula.replace(" ", "").replace("()", "")

  # 2. Build a regular expression pattern
  pattern = r"|".join([re.escape(op) for op in allowed_operations] +  allowed_functions)
  #print(pattern)
  # 3. Remove allowed elements
  result = re.sub(pattern, "", formula)

  # 4. Check if anything remains
  return not bool(re.search(r"[a-zA-Z]", result))  # True if the formula is invalid (contains disallowed characters)


def safe_eval(expr, key = 'B'):
    """Safely evaluates any formula in the MSaccess database. This is where X and Y offsets are usually calculated
    
    Args:
    expr (str) - the expression that needs to be evaluated
    key (str) - defaults as B, because only a base section is usually docked. Used for distEndToLastRungCut as docking varies between base and fly

    Returns:
    int - results of evaluated expression
    """
    if is_valid_formula(expr):
        try:
            # gets rid of brackets and replaces "DistEndToLastRungCut" with "DistEndToLastRungCut[key]: because docking is different for base vs fly
            # Fly is almost never docked but robot is capable of doing so
            return eval(expr.replace(" ", "").replace("()", "").replace("DistEndToLastRungCut", f"DistEndToLastRungCut['{key}']"))
        except (SyntaxError, ValueError):
            print("Error in calculating/evaluating hole coordinates")
            return None 
    else:
        return None 
    

def filter_and_seperate(array):
    """Takes an array of strings of all of the part numbers. Purges all of the parts that don't require holes, and then seperates into fly, base, etc
    In the database, each part is designated to be either 'F' or 'B', this way we can seperate based on the table and generate two different recipe files.

    Args:
    array - arrray of strings of part numbers eg: [BP-AF-0180-01, BP-RIV-0180-123, BP-RSDF-02342340-0123]

    returns:
    dict - for base and fly sections
    """
    filtered = []
    for i in range(len(array)):
        # Removing anything that is a rivet or a label. These do not have holes anyway.
        if "RIV" in array[i] or "LBL" in array[i] or array[i] in filtered:
            continue
        else: filtered.append(array[i])


    seperated = {
        'F': [],
        'B': []
    }
    for part in filtered:
        if 'EXL' in part:
            # Making that the section (Raw ladder section part ID) is in both lists for later logic
            seperated['F'].append([part, []])
            seperated['B'].append([part, []])


    for part in filtered:
        # Each part can have multiple instances (ie left vs right stile), and can have a different F/B Designation
        for FB in ['F','B']:
            cursor.execute("SELECT * FROM posData WHERE PartNo LIKE ? AND FBDesignation LIKE ?", 
                                (part + '%',FB)) 

            rows = cursor.fetchall()
            temp = []
            full_list = []
            if len(rows) != 0:
                
                for i in range(len(rows)):
                    instance = rows[i]
                    temp.append(instance[0])
                seperated[instance[4]].append([part, temp])
    return seperated

def extract_number(text):
    """
    Extracts the first floating-point number from a given text string.
    Used currently to extract the length of the section from the name of the section (ie S-LAD FEU BASE 3.9 --> 3.9)

    Args:
    text (str): The string from which to extract the number.

    Returns:
    float or None: The first floating-point number found in the text, or None if no number is found.
    """
    # Regular expression pattern to find floating-point numbers
    pattern = r"\b\d+\.\d+\b"

    # Search for the pattern
    match = re.search(pattern, text)
    if match:
        # Convert the matched string to a float and return
        return float(match.group(0))
    else:
        # Return None if no number is found
        return None
    
def get_section_info(array, type):
    """
    Exracts section info from the part IDs from the bill of materials. Takes account for EU type sections as well.

    Args:
    array - our array/list of all of the different part IDs/codes in our BOM
    type (str) - same as key. determines if we are currently generating for base or for fly

    returns:
    None (updates global values to do with our section instead)
    
    """
    sections = []
    for ID in array[type]:
        if 'EXL' in ID[0]:
            sections.append(ID[0])
    updated_vals = False
    for ID in sections:        
        cursor.execute("SELECT * FROM Sections WHERE ID LIKE ?", 
                                (ID + '%',)) 
        row = cursor.fetchone()
        if type == "B" and "BASE" in row[1] or (type == "F" and "FLY" in row[1]):
            global ITEM
            ITEM = row[1]
            num = extract_number(row[1])
            if num not in (i[0] for i in section_data):
                print("Section Info Not Found / Implemented")
            else:
                
                for index, sublist in enumerate(section_data):
                    
                    if sublist[0] == float(num) and type == sublist[1]:
                        global StileLength
                        StileLength = sublist[2]
                        global Pitch
                        global DistEndToFirstRungRaw

                        if "FEU" in row[1]:
                            # FEU is a european ladder section. The distance between the rungs (PITCH) for EU ladders is 300mm, vs 305 for AU/NZ
                            Pitch = 300

                            if type == "F":
                                DistEndToFirstRungRaw = 260
                            else:
                                DistEndToFirstRungRaw = 300

                        global RungCount
                        RungCount = sublist[3]
                        print("stile length:" , StileLength)
                        print("rung count: ", RungCount)
                        updated_vals = True
                        # NOW MPLEMENT EU LOGIC,  RUNG COUNT and RUNG PITCH
    if updated_vals == False:
        print("Stile not found on B.O.M")
        exit()            

def generate_coords(seperated):
    """takes 'F'or 'B' part of the output of the filter_and_seperate() function and returns a sorted nested array of coords and other information that goes into the recipe file

    Args:
    seperated - an array with a nested array containing partNo and unique position IDs

    returns:
    list/array - all of the coordinates of all of the holes with all other relevant information
    [x, y, z, part#, part name, hole diameter, face]
    [-1441.5, 195.0, -26.0, 'BP-FCL-0016-01', 'Tether lower rope mount - Left', 4.3, 3]
    """

    # fetchall holes with LinkID.
    coords = []
    #print(seperated)
    for i in range(len(seperated)):
        for ID in seperated[i][1]:
            raw_coords = []
            cursor.execute("SELECT * FROM compData WHERE LinkID LIKE ?", (str(ID),)) 

            rows = cursor.fetchall()
            for point in rows:
                #raw_coords.append([point[3]+point[6], point[4]+point[7], point[5]+point[8], point[2], point[9]]) #this includes henry offsets
                raw_coords.append([point[3], point[4], point[5], point[2], point[9]]) # [x, y, z, hole diameter 4.3/5, face (RU, LI etc)]
            
            cursor.execute("SELECT * FROM posData WHERE ID LIKE ?", 
               (str(ID)))

            row = cursor.fetchone()
            #print(row)

            if row[18] != None:
                endCut = safe_eval(row[18], key)
                #print("\n dist end cut raw",row[18],'\n')
                if endCut < DistEndToLastRungCut[key]:
                    DistEndToLastRungCut[key] = endCut


            x_offset = 0
            if row[13]:
                x_offset = safe_eval(row[13],key)
            y_offset = 0
            if row[14]:
                y_offset = safe_eval(row[14],key)
            
            for i in range(len(raw_coords)):
                raw_coords[i][0] += x_offset
                raw_coords[i][0] += row[10]
                raw_coords[i][1] += y_offset
                raw_coords[i][1] += row[11]
                raw_coords[i][2] += row[12]
                raw_coords[i].insert(-2, row[1]) # part ID
                raw_coords[i].insert(-2, row[6]) # part description
            coords += raw_coords

            

            


    return coords

    # apply offset/formula


    # add to coords list with additional data (face, diameter, etc)


def format_and_save_coordinates(coords, filename):
    """
    Creates the final recipe text file to be fed into the robot for both base and fly
    """
    # Position identifiers based on the index
    position_identifiers = ["0", "LU", "LO", "LI", "LD", "RU", "RO", "RI", "RD"]
    
    # Open the file in write mode
    with open('../CAM Output/' + filename + '.txt', 'w') as file:
        # Process each item in the data list
        # Ensure ITEM and key are defined before this line
        file.write(f"ID: {'empty'}   ITEM: {ITEM}    TYPE: {'EXTENSION'}     "
                   f"FBDESIGNATION: {key}     OUTSIDEWIDTH: {SectionWidth}     "
                   f"PITCH: {Pitch}    FIRSTOFRUNGOFFSET: {DistEndToFirstRungRaw}  "
                   f"STILELENGHT: {DistEndToFirstRungRaw + Pitch * (RungCount - 1) + min(DistEndToLastRungCut[key], Pitch)}   "
                   f"DOCKANGBOT: {'0'}   DOCKANGTOP: {'0'}   "
                   f"RUNGNO: {RungCount}   DOCKING: {'true' if DistEndToLastRungCut[key] < 305 else 'false'}\n")

        for item in coords:
            x, y, z, code, description, d, p = item
            # Ensure p index is valid for the position_identifiers list
            position_label = position_identifiers[p] if p < len(position_identifiers) else "Unknown"
            # Format the string as specified
            formatted_line = f"X{x} Y{y} Z{z} D{d} P:{position_label} - ({code} - {description})"
            # Write the formatted string to the file
            file.write(formatted_line + '\n')  # Add a newline character to separate each entry

    print(f"Data has been formatted and saved to {filename}.")


def sort_by_x_and_face(coordinates):
    """
    Sort a list of coordinate data based on two criteria. Initially, they are sorted
    according to the face. Then the list is sorted in descending order
    by the first element (x-coordinate). 
    ["0", "LU", "LO", "LI", "LD", "RU", "RO", "RI", "RD"] L = Left R = Right I = Inside O = Outer D = Down U = Up

    Parameters:
    coords (list of lists): A list where each inner list contains elements with the structure:
                             [x-coordinate, y-coordinate, z-coordinate, hole_diameter, face]
                             Here, `face` is an integer that represents the face of the ladder we are drilling

    Returns:
    list of lists: The input list sorted first by the face value according to the predefined custom order [7, 5, 6, 2, 1, 3, 4, 8] where
                   these integers represent different faces (for drilling). Then sorted by the x-coordinate in descending order.
                    If a face value does not match any in the custom order, it is placed at the end of the group.

    """
    custom_order = [0, 5, 4, 6, 7, 2, 3, 1, 8]
    # order_dict = {key: i for i, key in enumerate(custom_order)}

    # sort by face
    sorted_coordinates = sorted(coordinates, key=lambda x: (custom_order[x[-1]], -x[0]))
    # sort by the first element in reverse order
    # sorted_coordinates = sorted(sorted_coordinates, key=lambda x: x[0], reverse=True)

    return sorted_coordinates


def validate_and_correct_coordinates(coords, expected_plane, expected_range):
    """
    Validates and corrects a list of coordinates based on the expected_plane array and expected range. Each coordinate's
    validation and correction is dependent on its last term, which references indices in the expected_plane.
    The index refers the specific face of the ladder that the hole should lay. This means that there should be constraints to where the holes can be located.
    We use this info to validate that are holes are in the correct location and to check for any inconsistancies in the hole information.


    Parameters:
    coords (list of lists): List of coordinates where each list item includes [x, y, z, value, index]
                            with 'index' used to refer to validation rules in expected_plane.
    expected_plane (list of lists): Each sub-list contains [array_index, expected_value] where
                                    'array_index' is the index of the element in coords to compare,
                                    and 'expected_value' is the value to be matched.

    Returns:
    list of lists: The corrected list of coordinates, with modifications printed if any corrections are made.
    [x, y, z, part#, part name, hole diameter, face]
    [-1441.5, 195.0, -26.0, 'BP-FCL-0016-01', 'Tether lower rope mount - Left', 4.3, 3]
    """
    for coord in coords:
        last_index = coord[-1]  # Get the last term of the coordinate, which is the FACE (LI, LO, LU etc )
        if last_index < len(expected_plane):
            plane_rules = expected_plane[last_index]  # Get specific rules for this coordinate

            array_index = plane_rules[0]  # Index in coord to check
            expected_value = plane_rules[1]  # Expected plane coordinate

            if coord[array_index] != expected_value:  # Validation check #we are checking if point lays on plane
                print(f"Coordinate mismatch at {['x-coord ','y-coord ','z-coord '][array_index]}: {coord[array_index]} replaced with {expected_value} - {coord[-3]}")
                coord[array_index] = expected_value  # Replace with the expected value

            
            plane_rules = expected_range[last_index]  # Get specific rules for this coordinate

            array_index = plane_rules[0]  # Index in coord to check

            if plane_rules[1] < coord[array_index] < plane_rules[2]:
                pass
            else:
                print(f"Coordinate out of range at {['x-coord ','y-coord ','z-coord '][array_index]}: {coord[array_index]} please validate - {coord[-3]}")

    return coords


def extract_partID(text):
    """
    Extracts all substrings enclosed in square brackets from the given text and returns them as a list.

    Args:
    text (str): The text from which to extract the substrings.

    Returns:
    list: A list containing all substrings that were found within square brackets in the input text.

    Example:
    input_text = "[BP-EXL-0172-01] S-LAD FED BASE 6.4 TM\tBM/Stock\t0.00 / 1.00\tUnit\t1.00\t0.00\t\n[BP-EXL-0009-01] S-LAD FED FLY 6.4"
    extracted_strings = extract_bracketed_strings(input_text)
    print(extracted_strings)  # Output: ['BP-EXL-0172-01', 'BP-EXL-0009-01']
    """
    # Regular expression to find all substrings within square brackets
    pattern = r"\[(.*?)\]"
    # Find all occurrences of the pattern
    matches = re.findall(pattern, text)

    return matches

def filter_nested_list(nested_list, codes):
    # nested list is your nested list of all of the different part numbers in the ladder
    # codes is the list of verified codes/part IDs
    # removes part IDs that have not been verified
    # Create a set from the codes for faster lookup
    codes_set = set(codes)
    
    # Filter the nested list
    filtered_list = [item for item in nested_list if item[0] in codes_set]
    
    return filtered_list


def remove_unreachable_holes(coords):
    """
    Removes holes that are likely unreachable by the robot based on given criteria.
    The criteria is based on the fact that the hole might be too close to a rung.
    Currently, if a hole is within 7cm of a rung, it will not be drilled/ will be removed from the list. 
    The robot does usually account for unreachable holes but sometimes it can cause issues, so it is best to remove the holes here.

    Args:
    - coords (list of tuples): List of coordinates where each coordinate is represented as a tuple (x, y).

    Returns:
    - list: Purged list of holes after removing unreachable ones.
    """
    print("---------- Unreachable Holes ----------")
    for i in range(len(coords) - 1, -1, -1):
        if ((coords[i][0] % Pitch) < 70 or ((Pitch - 70) < (coords[i][0] % Pitch))) and (coords[i][0] < 0) and (coords[i][0] > -(RungCount-1)*Pitch):
            
            if coords[i][-1] == 3 or coords[i][-1] == 7: #this is the face
                print(coords.pop(i))
    print("---------- Unreachable Holes ----------")
    return coords


def remove_duplicate_holes(coords):
    """
    Removes all of the duplicate holes which can come from multiple parts having the same hole location.
    Parts have a form of heirarchy (Parts are used to make parts). Such as having a particular coating. This would have a different ID but same holes.
    We check if hole coordinate and hole size are all the samee, if they are, then we do not include it. This will save time during drilling.


    Parameters:
    coords (list of lists): A list where each inner list contains elements with the structure:
                             [x-coordinate, y-coordinate, z-coordinate, hole_diameter, face]
                             Here, `face` is an integer that represents the face of the ladder we are drilling
    
                             
    Returns: Coords(list of lists)
    """
    seen = set()
    new_list = []

    for item in coords:
        t = tuple(item[0:3])
        if t not in seen:
            new_list.append(item)
            seen.add(t)

    return new_list


def terrain_master_offset(coords):
    """This function subtracts pitch*1 from x-coordinate of holes for specific parts. This is because the terrain master
    counts as an extra rung. Therefore anything that uses rung count * pitch in the calculation should be subtracted by pitch.
    (Usually some jigs are placed X rungs from the bottom, the terrain master counts as a rung)
    
    Input: Coords list of lists
    ([x, y, z, part#, part name, hole diameter, face]
    [-1441.5, 195.0, -26.0, 'BP-FCL-0016-01', 'Tether lower rope mount - Left', 4.3, 3])

    Returns: Coords
    """
    affected_parts = ['BP-FCL-0023-01', 'BP-FCL-8050-01','BP-FCL-0041-01', 'BP-FCL-0016-01']


    for i in range(len(coords)):
        if coords[i][3] in affected_parts:
            coords[i][0] -= Pitch

    coords = sort_by_x_and_face(coords)

    return coords

def global_init(IDs):
    ZeroDivisionError

def connect_to_MSaccess_DB():
    # HERE WE ARE CONNECTING TO MICROSOFT ACCESS FOR INFORMATION
    # it is crucial that your python is a 32 bit version because MS Access is a 32 bit version, therefore needs to run with virtual environment.
    print("Attempting to connect to Access Database...")

    conn_str = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        r"DBQ=X:\CAD\E091-01 Manufacturing Info System\testPythonDB.accdb;"  # Replace with your database path
    )

    # Connect to the database
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Optional: Try executing a simple query to further verify
        cursor.execute("SELECT 1")

        print("Connection successful!")

    except pyodbc.Error as ex:
        sqlstate = ex.args[1]
        print("Connection failed:", sqlstate)
    

    time.sleep(0.1)
    # Example: Read data from a table
    # cursor.execute("SELECT * FROM [compData]")

    # for row in cursor.fetchall():
    #     print(row)

    return conn, cursor

if __name__ == '__main__':
    print("running...")
    
    # Majority of information is stored in an SQL database running on microsoft Access.
    # therefore we need to connect to this database to extract any and all information about Part IDs and hole coordinates. 
    conn, cursor = connect_to_MSaccess_DB()
    
    # test_array = [
    #     "BP-EXL-0100-01",
    #     "BP-EXL-0001-01",
    #     "BP-EXF-0110-02"
    # ]

    
    # here we ask for the user to input a copy paste of the BOM from odoo, under manufacturing orders
    test_array = input("Provide BOM: ")
    test_array = extract_partID(test_array)
    

    # This needs to be removed if we are not docking the fly. This auto docks the fly such that distance from center  of last rung to end is 40mm
    test_array.append('BP-EXF-0110-02-TEMP')
    
    # copy paste a BOM from MANUFACTURING > OPERATIONS > MANUFACTURING ORDERS


    # this removes certain parts which are hard to include, or have lead to unecessary holes
    remove = ["BP-EXF-0110-02", "BP-EXF-0094-01111", "BP-FCL-0016-01", "BP-EXF-0010-02"]
    product_id_list = [x for x in test_array if x not in remove]

    # some parts have subparts that are associated with them. We only have the holes/coordinates for these sub parts
    # therefore we need to substitute the parts with the sub-parts so that they are recognised and present in the SQL/accesss Database
    substitute = [["BP-EXF-8090-01","BP-EXF-0094-01"], ["BP-EXF-8091-01","BP-EXF-0094-01"], ["BP-FCL-8030-01",["BP-FCL-0023-01", "BP-FCL-0016-01-remove"]], ["BP-EXF-0231-01","BP-EXF-0010-02-remove"], ["BP-TOP-8000-02","BP-TOP-0001-01"]]
    substitute_dict = {item[0]: item[1] for item in substitute}

#    Perform substitution
    main_list = [substitute_dict[item] if item in substitute_dict else item for item in product_id_list]
    
    #Flattening the list
    flat_list_ID = []
    for i in range(len(main_list)):
        if type(main_list[i]) == str:
            flat_list_ID.append(main_list[i])
        else:
            for j in range(len(main_list[i])):
                flat_list_ID.append(main_list[i][j])

 
    # this removes any parts that are not present in the SQL/access DB and seperates them into fly and base holes
    split_BF = filter_and_seperate(flat_list_ID)

    print("\n\n\n\n\n",split_BF)
    for key in split_BF.keys():
        print("\n \n \n \n \n ",key, " PRINTING RECIPE ---> \n")
        if key == "B":
            SectionWidth = 450
            DistEndToFirstRungRaw = 290
        elif key == "F":
            SectionWidth = 367
            
            DistEndToFirstRungRaw = 305

        # based on the section in the BOM, we can identify key information that needs to be provided to the robot, such as rung count and length
        get_section_info(split_BF, key)
        for i in range(len(split_BF[key]) - 1, -1, -1):
            if "EXL" in split_BF[key][i][0]:
                split_BF[key].pop(i)

        #split_kept = filter_nested_list(split_BF[key], verified)

        # this is the main function which goes through all of the parts one by one and generates all of the coordinates of the holes to be drilled
        coords = generate_coords(split_BF[key])


        # sorts the coords in terms of x coordinates and by face to be drilled, see function for more info
        sorted_coordinates = sort_by_x_and_face(coordinates = coords)
        

        # checks all of the holes and makes sure that it is logical for them to be where they are, cross checks with the face that the hole needs to be drilled
        validated_coordinates = validate_and_correct_coordinates(sorted_coordinates, expected_plane[key], expected_range[key])



        #all of the following are variations of the terrain master. If any of them are present, then we know to simulate an extra rung and add offsets.
        if 'BP-LEV-8700-01' in [item for row in split_BF[key] for item in row]:
            print("\nTerrain Master Detected: Adding relevant Offsets\n")
            validated_coordinates = terrain_master_offset(validated_coordinates)
        elif 'BP-LEV-8606-01' in [item for row in split_BF[key] for item in row]:
            print("\nTerrain Master Detected: Adding relevant Offsets\n")
            validated_coordinates = terrain_master_offset(validated_coordinates)
        elif 'BP-LEV-8609-01' in [item for row in split_BF[key] for item in row]:
            print("\nTerrain Master Detected: Adding relevant Offsets\n")
            validated_coordinates = terrain_master_offset(validated_coordinates)


        # some holes are unreachable by the robot. Most of the time the robot just skips these holes, but sometimes it leads to an error which I do not know how to fix
        # thus, i am just removing these holes here, so that an issue does not occur when the robot is running
        validated_coordinates = remove_unreachable_holes(validated_coordinates)
        

        # sometimes there is overlap in the parts because some parts have holes for both sides of the ladder even though they may only be placed on one side
        # this just removes any duplicate holes which would cause delays when the robot is running.
        validated_coordinates = remove_duplicate_holes(validated_coordinates)
        
        format_and_save_coordinates(validated_coordinates, "test"+key)
    
    
    # this is what the distance from the centre of the last rung to the end of the docked ladder should be. Measure the distance, it should be the same.
    print("Distance From Last Rung to End: ",DistEndToLastRungCut)

    # Close the connection

    cursor.close()
    conn.close()

    
    
