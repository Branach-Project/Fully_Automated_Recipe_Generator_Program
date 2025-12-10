import os
import time
import ast
import re
import sys
import numpy as np
import pyodbc

class RecipeGenerator:
    def __init__(self):
        # Initialize default values and configuration parameters
        self.RungCount = 13
        self.Pitch = 305
        # DistEndToLastRungCut differs depending on whether the ladder section is base (B) or fly (F)
        self.DistEndToLastRungCut = {"F": 305, "B": 305}
        self.StileLength = 3555
        self.DistEndToFirstRungRaw = 290
        self.SectionWidth = 450

        self.StileWidth = 30
        self.StileHeight = 76
        self.cursor = None  # Cursor to interact with the Access database; initialized after connection
        self.ITEM = ""      # Item name/description of the ladder or section
        self.LadderFoot = "TM"
        self.LatchType = ""

        # Expected "plane" setup for validation: Defines reference coordinates or offsets that 
        # certain holes must align to, depending on whether the section is 'B' (base) or 'F' (fly)
        self.expected_plane = {
            'F': [
                [0, 0],
                [2, self.StileHeight / 2],
                [1, 183.5],
                [1, 183.5 - self.StileWidth],
                [2, -self.StileHeight / 2],
                [2, self.StileHeight / 2],
                [1, -183.5],
                [1, -183.5 + self.StileWidth],
                [2, -self.StileHeight / 2]
            ],
            'B': [
                [0, 0],
                [2, self.StileHeight / 2],
                [1, 195 + self.StileWidth],
                [1, 195],
                [2, -self.StileHeight / 2],
                [2, self.StileHeight / 2],
                [1, -195 - self.StileWidth],
                [1, -195],
                [2, -self.StileHeight / 2]
            ]
        }

        # Expected range checks for validation: ensures holes are within a valid range
        # to confirm no out-of-bound drilling locations.
        self.expected_range = {
            'F': [
                [0, 0],
                [1, 183.5 - self.StileWidth, 183.5],
                [2, -self.StileHeight / 2, self.StileHeight / 2],
                [2, -self.StileHeight / 2, self.StileHeight / 2],
                [1, 183.5 - self.StileWidth, 183.5],
                [1, -183.5, -183.5 + self.StileWidth],
                [2, -self.StileHeight / 2, self.StileHeight / 2],
                [2, -self.StileHeight / 2, self.StileHeight / 2],
                [1, -183.5, -183.5 + self.StileWidth]
            ],
            'B': [
                [0, 0],
                [1, 195, 195 + self.StileWidth],
                [2, -self.StileHeight / 2, self.StileHeight / 2],
                [2, -self.StileHeight / 2, self.StileHeight / 2],
                [1, 195, 195 + self.StileWidth],
                [1, -195 - self.StileWidth, -195],
                [2, -self.StileHeight / 2, self.StileHeight / 2],
                [2, -self.StileHeight / 2, self.StileHeight / 2],
                [1, -195 - self.StileWidth, -195]
            ]
        }

        # Section data: Provides mapping between section characteristics and ladder parameters such as stile length and rung count.
        self.section_data = [
            [3.9, 'B', 2065, 6], [3.9, 'F', 2403, 8], [4.0, 'B', 2380, 7], [4.0, 'F', 2455, 7],
            [5.1, 'B', 2665, 8], [5.1, 'F', 3003, 10], [5.2, 'B', 2990, 9], [5.2, 'F', 3065, 9],
            [6.3, 'B', 3265, 10], [6.3, 'F', 3603, 12], [6.4, 'B', 3600, 11], [6.4, 'F', 3675, 11],
            [7.5, 'B', 3865, 12], [7.5, 'F', 4203, 14], [7.6, 'B', 4210, 13], [7.6, 'F', 4285, 13],
            [8.7, 'B', 4465, 14], [8.7, 'F', 4803, 16], [8.8, 'B', 4820, 15], [8.8, 'F', 4895, 15],
            [9.4, 'B', 5430, 17], [9.4, 'F', 5505, 17], [9.6, 'B', 5430, 17], [9.6, 'F', 5505, 17], [9.8, 'B', 5430, 17], [9.8, 'F', 5505, 17]
        ]
        self.ladder_end_caliberation_offset = 0

    def connect_to_MSaccess_DB(self):
        """
        Attempts to establish a connection to the Microsoft Access database.
        If successful, returns the connection object and sets the cursor for further SQL operations.
        """
        #print("Attempting to connect to Access Database...")

        conn_str = (
            r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
            r"DBQ=A:\E091-01 Manufacturing Info System\PythonDB.accdb;"
        )

        try:
            conn = pyodbc.connect(conn_str)
            self.cursor = conn.cursor()

            # Test the connection with a simple query
            self.cursor.execute("SELECT 1")
            #print("Connection successful!")
            return conn
        except pyodbc.Error as ex:
            # Print error if connection fails
            sqlstate = ex.args[1]
            #print("Connection failed:", sqlstate)

    def is_valid_formula(self, formula):
        """
        Validates if a formula string consists only of allowed variables and arithmetic operations.
        This is a precaution before using eval to ensure no malicious code injection is possible.
        """
        formula = formula.replace(" ", "").replace("()", "")
        # Allowed operations and variables
        pattern = r"|".join([re.escape(op) for op in ['+', '-', '*', '/']] + 
                            ['DistEndToLastRungCut', 'RungCount', 'Pitch', 'SectionWidth', 'DistEndToFirstRungRaw', 'StileLength'])
        # Strip allowed patterns and check if any alphabetic char remains
        result = re.sub(pattern, "", formula)
        return not bool(re.search(r"[a-zA-Z]", result))

    def safe_eval(self, expr, key='B'):
        """
        Safely evaluates a formula (expr) from the database, calculating offsets or hole coordinates.
        Uses restricted local variables and no builtins to prevent code injection.
        
        Args:
            expr (str): Expression to evaluate
            key (str): Section type 'B' or 'F' to handle DistEndToLastRungCut indexing.
        
        Returns:
            int or None: Evaluated result or None if invalid or error occurs.
        """
        if self.is_valid_formula(expr):
            try:
                # Prepare local variables used in formulas
                local_vars = {
                    'RungCount': self.RungCount,
                    'Pitch': self.Pitch,
                    'SectionWidth': self.SectionWidth,
                    'DistEndToFirstRungRaw': self.DistEndToFirstRungRaw,
                    'StileLength': self.StileLength,
                    'DistEndToLastRungCut': self.DistEndToLastRungCut
                }

                # Replace the DistEndToLastRungCut variable call with the correct dictionary key
                expr = expr.replace(" ", "").replace("()", "").replace("DistEndToLastRungCut", f"DistEndToLastRungCut['{key}']")
                print("Check valid variables in formula:", local_vars)
                # Evaluate safely using restricted environment
                return eval(expr, {"__builtins__": None}, local_vars)
            except (SyntaxError, ValueError, NameError) as e:
                print(f"Error in calculating/evaluating hole coordinates: {e}")
                return None
        else:
            return None


    def filter_and_separate(self, array):
        """
        Filters out unwanted parts (like 'RIV', 'LBL') and splits remaining parts into base and fly categories.
        For each part, queries the database (posData table) to find matches for 'F' and 'B', 
        and stores them in separated dict for later processing.
        """
        # Filter out certain parts like 'RIV' and 'LBL'
        filtered = [item for item in array if "RIV" not in item and "LBL" not in item]
        separated = {'F': [], 'B': []}

        # Duplicate EXL parts into both 'F' and 'B' keys with empty sub-lists
        for part in filtered:
            if 'EXL' in part:
                separated['F'].append([part, []])
                separated['B'].append([part, []])

        # For each part, fetch from database and update separated lists with data from posData
        for part in filtered:
            for FB in ['F', 'B']:
                self.cursor.execute("SELECT * FROM posData WHERE PartNo LIKE ? AND FBDesignation LIKE ?", (part + '%', FB))
                rows = self.cursor.fetchall()
                #print("posData in filter and separate ----------------", rows)

                if rows:
                    temp = [instance[0] for instance in rows]
                    separated[FB].append([part, temp])
        return separated

    def extract_partID(self, text):
        """
        Extracts part IDs enclosed in square brackets from a string.
        For example: "This is a [PartID] in a string" -> ["PartID"]
        """
        pattern = r"\[(.*?)\]"
        matches = re.findall(pattern, text)
        for i in range(len(matches)):
            if matches[i].split()[0] == 'Build':
                matches[i] = matches[i][7:]
        #print("Here are the matches", matches)
        return matches

    def get_section_info(self, array, section_type):
        """
        Retrieves and updates ladder parameters (like StileLength, Pitch, RungCount) based on 
        the section ID found in the database. Uses the 'Sections' table to find matching sections
        and updates class attributes accordingly.
        If no matching section data is found in self.section_data, it prints a message and exits.
        """
        # Extract sections that contain 'EXL'
        sections = [ID[0] for ID in array[section_type] if 'EXL' in ID[0]]
        updated_vals = False
        for ID in sections:
            #print("Here is ID and sections", ID, "Sections", sections)
            self.cursor.execute("SELECT * FROM Sections WHERE ID LIKE ?", (ID + '%',))
            row = self.cursor.fetchone()
            #print("Sections in get section info ----------------", row)
            if section_type == "B" and "BASE" in row[1] or (section_type == "F" and "FLY" in row[1]):
                global ITEM
                ITEM = row[1]
                #print("ITEM is here", ITEM)
                self.ITEM = ITEM
                num = self.extract_number(row[1])
                #print("Here is num in get_section_info", num)
                if num not in (i[0] for i in self.section_data):
                    print("Section Info Not Found / Implemented")
                else:
                    # Update ladder parameters based on matching section_data entry
                    for index, sublist in enumerate(self.section_data):
                        if sublist[0] == float(num) and section_type == sublist[1]:
                            self.StileLength = sublist[2]
                            # Adjust pitch and DistEndToFirstRungRaw if FEU is found in the item name
                            if "FEU" in row[1]:
                                self.Pitch = 300
                                self.DistEndToFirstRungRaw = 260 if section_type == "F" else 300
                            self.RungCount = sublist[3]
                            #print("stile length", self.StileLength)
                            #print("rung count: ", self.RungCount)
                            updated_vals = True
        #find the typ of ladder foot
        #print("components ladder foot", array)
        terrain_master_components = {"BP-LEV-8609-01", "BP-LEV-8700-01", "BP-LEV-8606-01"}
        swivel_feet = {"BP-EXF-8090-01","BP-EXF-0094-01", "BP-EXF-8091-01"}
        swivel_no_ice_pick = {"BP-EXF-8009-01"}
        swivel_grab_bar = {"NNN"}
        rubber_feet = {"BP-EXF-0161-03"}
        rubber_north_power = {"BK-EXF-9044-01"}
        
        if any(sublist[0] in terrain_master_components for sublist in array[section_type]) and section_type == "B": #if it is terrain master
            self.LadderFoot = "TM"
        if any(sublist[0] in swivel_feet for sublist in array[section_type]) and section_type == "B":
            self.LadderFoot = "SF"
        if any(sublist[0] in swivel_no_ice_pick for sublist in array[section_type]) and section_type == "B":
            self.LadderFoot = "SN"
        if any(sublist[0] in swivel_grab_bar for sublist in array[section_type]) and section_type == "B":
            self.LadderFoot = "SG"
        if any(sublist[0] in rubber_feet for sublist in array[section_type]) and section_type == "B":
            self.LadderFoot = "RF"
        if any(sublist[0] in rubber_north_power for sublist in array[section_type]) and section_type == "B":
            self.LadderFoot = "RN"
        
        #print("2 ladder foot type", self.LadderFoot)

        #find the type of latch
        branach_latch = [ "BP-EXF-8101-03" ]
        conventional_latch = [ "BP-EXF-8011-01" ]
        if any(sublist[0] in branach_latch for sublist in array[section_type]):
            self.LatchType = "Branach"
        elif any(sublist[0] in conventional_latch for sublist in array[section_type]):
            self.LatchType = "Conventional"
        #print("The latch type is", self.LatchType)


        # Update the length of the ladder if it is TM and Branach latch
        if section_type == "F" and self.LatchType == "Branach" and self.LadderFoot == "TM":
            print("the lenght of the ladder hasbeen updated")
            self.StileLength -= self.StileLength - self.Pitch
            self.RungCount -= 1
        
        
        if not updated_vals:
            print("Stile not found on B.O.M")
            exit()

    def dynamic_select(self, split_BF, key, product_display_name):
        #print('this is what the dynamic select picks', split_BF)
        #print('key here', key)
        terrain_master_components = {"BP-LEV-8609-01", "BP-LEV-8700-01", "BP-LEV-8606-01"}
        t3 = {"BP-TOP-0001-01", "BP-TOP-8001-01", "BK-EXF-9510-01"}
        contains_t3 = any(sublist[0] in t3 for sublist in split_BF[key])

        for i in range(len(split_BF[key]) - 1, -1, -1):
            if split_BF[key][i][0] == "BP-EXF-8161-01":
                #check if it is terrain master
                if any(sublist[0] in terrain_master_components for sublist in split_BF[key]): #if it is terrain master
                    # if it is a terrrain master
                    #check if it is a 9.8
                    if ITEM == "S-LAD FED BASE 9.8":
                        split_BF[key][i][1] = [202]
                    else:
                        split_BF[key][i][1] = [201]
                    
                else: # if it is not a terrain master
                    if ITEM == "S-LAD FED BASE 9.8":
                        split_BF[key][i][1] = [197]
                    else:
                        split_BF[key][i][1] = [134]
                #print("did the stopper bracket change", split_BF[key][i][1])

            # or (contains_t3 and split_BF[key][i][0] == "BP-EXF-0110-02-TEMP")
            if (contains_t3 and split_BF[key][i][0] == "BP-EXF-0110-02"):
                print(f"Removing {split_BF[key][i][0]} because BP-EXF-0030-02 exists")
                del split_BF[key][i]

            #print("after the data type of the fly looks like this", split_BF)

        
        #print("ITEM split is here", ITEM.split())
        utility = ""
        if product_display_name.strip().lower().endswith('utility'):
            utility = "Y"
        else:
            utility = "N"

        if utility == "Y":
            for i in range(len(split_BF[key]) - 1, -1, -1):
                if (split_BF[key][i][0] == "BP-FCL-0023-01" or split_BF[key][i][0] == "BP-FCL-0041-01") and key == "B":
                    del split_BF[key][i]
            
            print("This is an utility ladder")

        #get rid of holes that the base won't drill properly
        # for i in range(len(split_BF[key]) - 1, -1, -1):
        #         if (split_BF[key][i][0] == "BP-EXF-0032-02" ) and key == "B":
        #             del split_BF[key][i]
        
        return split_BF
                

    def generate_coords(self, separated, key):
        """
        Generates coordinates for holes by querying compData and posData tables.
        Calculates offsets, updates DistEndToLastRungCut if necessary, and then merges all
        coordinate and component data into a single list.
        """
        coords = []
        #print("generated coordinates separated", separated)
        for i in range(len(separated)):
            for ID in separated[i][1]:
                raw_coords = []
                # Fetch component details from compData
                self.cursor.execute("SELECT * FROM compData WHERE LinkID LIKE ?", (str(ID),))
                rows = self.cursor.fetchall()
                #print("compData in generate coords ----------------", rows)
                for point in rows:
                    raw_coords.append([point[3], point[4], point[5], point[2], point[9]])

                # Fetch position details from posData
                self.cursor.execute("SELECT * FROM posData WHERE ID LIKE ?", (str(ID),))
                row = self.cursor.fetchone()
                # Evaluate end cut offset if provided
                if row[18] != None:
                    endCut = self.safe_eval(row[18], key)
                    #print("endcut in generate coord", endCut)
                    #print("The ladder foot type is", self.LadderFoot)
                    if endCut < self.DistEndToLastRungCut[key]:
                        self.DistEndToLastRungCut[key] = endCut
                    #dynamic for fly
                    #print("2 the latch type" , self.LatchType)
                    #print("key", key)
                    if self.LadderFoot != "TM" and key == "F" and self.LatchType == "Conventional":
                        self.DistEndToLastRungCut[key] = self.Pitch
                    if (self.LadderFoot == "SF" or self.LadderFoot == "SN" or self.LadderFoot == "SG") and key == "F":
                        self.DistEndToLastRungCut[key] = self.Pitch
                    if self.LadderFoot == "RF" and key == "F":
                        self.DistEndToLastRungCut[key] = self.Pitch
                    #dynamic for base
                    if (self.LadderFoot == "SF" or self.LadderFoot == "SN" or self.LadderFoot == "SG") and key == "B":
                        self.DistEndToLastRungCut[key] = 232.5 #232.5
                    if self.LadderFoot == "RF" and key == "B":
                        self.DistEndToLastRungCut[key] = self.Pitch
                    
                    
                # Calculate offsets
                #print("hre is row", row)
                x_formula = self.safe_eval(row[13], key) if row[13] else 0
                y_fomrula = self.safe_eval(row[14], key) if row[14] else 0
                Z_formula = row[9] if row[9] else 0

                #raw coordinates before
                #print("raw coordinates before offset", row)
                # Update coordinates with offsets and additional data
                for i in range(len(raw_coords)):
                    #Don't need hole base offset
                    raw_coords[i][0] += x_formula + row[10] + rows[i][6] # orginal coord + component base offset + hole base offset
                    raw_coords[i][1] += y_fomrula + row[11] + rows[i][7]
                    raw_coords[i][2] += Z_formula + row[12] + rows[i][8]
                    # raw_coords[i][0] += x_offset + row[10] # orginal coord + component base offset + hole base offset
                    # raw_coords[i][1] += y_offset + row[11]
                    # raw_coords[i][2] += row[12]
                    # Insert part code and description before hole diameter and face
                    raw_coords[i].insert(-2, row[1])
                    raw_coords[i].insert(-2, row[6])
                coords += raw_coords
                #print("here is the offset")
                #print(row[12])
                #print("check if the offset is working", raw_coords)
                #print(coords)
        return coords

    def extract_number(self, text):
        """
        Extracts the first floating-point number from a given string.
        Returns the number as a float or None if not found.
        Used to determine ladder length from the section name.
        """
        pattern = r"\b\d+\.\d+\b"
        match = re.search(pattern, text)
        if match:
            return float(match.group(0))
        else:
            return None

    def sort_by_x_and_face(self, coordinates):
        """
        Sorts the coordinates first by a custom face order, then by x-coordinate in descending order.
        ["0", "LU", "LO", "LI", "LD", "RU", "RO", "RI", "RD"] L = Left R = Right I = Inside O = Outer D = Down U = Up
        Faces refer to drilling surfaces of the ladder, and 'x' is the primary reference axis.
        """
        #(custom_order[x[-1]], -x[0])
        custom_order = [0, 5, 4, 6, 7, 2, 3, 1, 8]
        sorted_coordinates = sorted(coordinates, key=lambda x: (custom_order[x[-1]], -x[0]))
        return sorted_coordinates

    def validate_and_correct_coordinates(self, coords, expected_plane, expected_range):
        """
        Validates that each hole coordinate matches the expected plane and lies within the expected range.
        If mismatches occur, they are corrected and a warning is printed.
        """
        for coord in coords:
            last_index = coord[-1]
            if last_index < len(expected_plane):
                # Validate against expected plane
                plane_rules = expected_plane[last_index]
                array_index = plane_rules[0]
                expected_value = plane_rules[1]

                # If coordinate doesn't match the expected plane, correct it
                if coord[array_index] != expected_value:
                    #print(f"Coordinate mismatch at {['x-coord ','y-coord ','z-coord '][array_index]}: {coord[array_index]} replaced with {expected_value} - {coord[-3]}")
                    coord[array_index] = expected_value

                # Validate against expected range
                plane_rules = expected_range[last_index]
                array_index = plane_rules[0]
                # Check if coordinate is within the provided range
                if not (plane_rules[1] < coord[array_index] < plane_rules[2]):
                    #print(f"Coordinate out of range at {['x-coord ','y-coord ','z-coord '][array_index]}: {coord[array_index]} please validate - {coord[-3]}")
                    pass
        return coords

    def terrain_master_offset(self, coords):
        """
        Adjusts x-coordinates for holes in parts affected by the terrain master offset.
        Some parts rely on a rung count calculation that includes the terrain master as a rung. 
        This adjustment ensures correct hole placement for those parts.
        """
        affected_parts = ['BP-FCL-0023-01', 'BP-FCL-8050-01','BP-FCL-0041-01', 'BP-FCL-0016-01']

        for i in range(len(coords)):
            if coords[i][3] in affected_parts:
                coords[i][0] -= self.Pitch

        coords = self.sort_by_x_and_face(coords)
        return coords

    def remove_unreachable_holes(self, coords):
        """
        Removes holes from the coordinate list that are deemed unreachable by the robot.
        Holes too close to rungs (within 6cm) are currently removed.
        Conditions:
            When x is negative, x it will contact the rung. 
        """

        #print("---------- Unreachable Holes ----------")
        #print("remove unreachable holes debug", coords)
        remove_array = []
        for i in range(len(coords) - 1, -1, -1):
            
            #0:x 1:y 2:z 3:component index 4:component name 5:diameter 6:faces
           
            if coords[i][-1] == 3:# LI should notice the box for the front side
                if(coords[i][0] < 0) and (coords[i][2] < -10) and ((abs(coords[i][0]) % self.Pitch) < 120) :
                    print("LI",(coords[i][0] % self.Pitch))
                    remove_array.append(coords.pop(i))
                    continue
            if coords[i][-1] == 7: # RI should notice the box for the back side.
                if(coords[i][0] < 0) and (coords[i][2] < -10) and  ((self.Pitch - (abs(coords[i][0]) % self.Pitch)) < 120):
                    print("RI",self.Pitch - (coords[i][0] % self.Pitch))
                    remove_array.append(coords.pop(i))
                    continue
            # if ((coords[i][0] % self.Pitch) < 80 or ((self.Pitch - 80) < (coords[i][0] % self.Pitch))) and (coords[i][2] < 0 or ((coords[i][0] % self.Pitch) < 40 or ((self.Pitch - 40) < (coords[i][0] % self.Pitch)))) and ( (coords[i][0] < 0) and (coords[i][0] > -(self.RungCount-1)*self.Pitch) ):
            #     if coords[i][-1] == 3:
            #         remove_array.append(coords.pop(i))
            #         continue
            # #125.5
            # # means robot will do short swap
            # if coords[i][-1] == 7:
            #     if (coords[i][0] % self.Pitch < 125.5)
            # if ((coords[i][0] % self.Pitch) < 40 or ((self.Pitch - 40) < (coords[i][0] % self.Pitch))) and (coords[i][2] < 0 or ((coords[i][0] % self.Pitch) < 40 or ((self.Pitch - 40) < (coords[i][0] % self.Pitch)))) and ( (coords[i][0] < 0) and (coords[i][0] > -(self.RungCount-1)*self.Pitch) ):
            #     if coords[i][-1] == 7:
            #         remove_array.append(coords.pop(i))
            #         continue

        print("---------- Unreachable Holes ----------")
        print(remove_array)

        return coords

    def remove_duplicate_holes(self, coords):
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


    def format_and_save_coordinates(self, coords, filename, key, ITEM):
        """
        Formats final coordinates into a text file for the robot. Each line contains hole coordinates, 
        drilling properties, and reference codes. The header includes ladder parameters for use by the robot.
        
        Args:
            coords (list): Final list of coordinates.
            filename (str): Output filename.
            key (str): 'B' or 'F' indicating base or fly section.
            ITEM (str): Ladder item description.
        """
        position_identifiers = ["0", "LU", "LO", "LI", "LD", "RU", "RO", "RI", "RD"]
        

        # If the ladder stilelength changes, change holes position according at the end of the ladder as well
        # Calculate x-position of the last rung
        last_rung_x = -(self.DistEndToFirstRungRaw + self.Pitch * (self.RungCount - 1))


        # Open file to write final recipe
        path = r"A:\E091-01 Manufacturing Info System\CAM Output"
        with open(rf"{path}\{filename}.txt", 'w') as file:
            # Write header information
            #print("distendtolastrung is here", self.DistEndToLastRungCut)
            #print("ladder length before moderation", self.DistEndToFirstRungRaw + self.Pitch * (self.RungCount - 1) + min(self.DistEndToLastRungCut[key], self.Pitch))
            #print("her is the ladder end calibration", self.ladder_end_calibration_offset)
            file.write(
                f"ID:{'empty'}   ITEM: {ITEM}    TYPE:{'EXTENSION'}     "
                f"FBDESIGNATION:{key}     OUTSIDEWIDTH:{self.SectionWidth}     "
                f"PITCH:{self.Pitch}    FIRSTOFRUNGOFFSET:{self.DistEndToFirstRungRaw}  "
                f"STILELENGHT:{self.DistEndToFirstRungRaw + self.Pitch * (self.RungCount - 1) + min(self.DistEndToLastRungCut[key], self.Pitch)}   "
                f"DOCKANGBOT:{'0'}   DOCKANGTOP:{'0'}   "
                f"RUNGNO:{self.RungCount}   DOCKING:{'true' if self.DistEndToLastRungCut[key] < self.Pitch else 'false'}     "
            )

            # Write each hole coordinate with associated data
            for item in coords:
                x, y, z, code, description, d, p = item
                #print("type of x", type(p))
                #print(x, y, z, code, description, d, p)
                position_label = position_identifiers[p] if p < len(position_identifiers) else "Unknown"
                formatted_line = f"X{x} Y{y} Z{z} D{d} P:{position_label} - ({code} - {description})"
                file.write('\n' + formatted_line)

        #print(f"Data has been formatted and saved to {filename}.")

    def run(self, formatted_componets, product_display_name, child_detail):
        """
        Main execution flow:
        1. Asks user to specify section type (F or B).
        2. Connects to the DB.
        3. Extracts product IDs from the given components string.
        4. Filters & substitutes part IDs.
        5. Splits parts into 'F' and 'B', retrieves section info, generates coordinates, and validates them.
        6. Removes unreachable holes and saves final coordinates.
        """

        execute_fly_or_base = child_detail
        conn = self.connect_to_MSaccess_DB()

        # Extract part IDs enclosed in brackets
        test_array = formatted_componets
        test_array = self.extract_partID(test_array)
        test_array.append('BP-EXF-0110-02-TEMP')

        # Remove certain IDs
        remove = ["BP-EXF-0094-01111", "BP-FCL-0016-01", "BP-EXF-0010-02"]
        product_id_list = [x for x in test_array if x not in remove]

        # Substitution rules if certain parts are replaced by others
        substitute = [
            ["BP-EXF-8090-01", "BP-EXF-0094-01"],
            ["BP-EXF-8091-01", "BP-EXF-0094-01"],
            ["BP-FCL-8030-01", ["BP-FCL-8002-01", "BP-FCL-0016-01-remove"]],
            ["BP-EXF-0231-01", "BP-EXF-0010-02-remove"],
            ["BP-TOP-8000-02", "BP-TOP-0001-01"],
            ["BP-TOP-8000-01", "BP-TOP-0001-01"],
            ["BK-EXF-9087-01", "BP-TOP-0001-01"]
        ]
        substitute_dict = {item[0]: item[1] for item in substitute}
        main_list = [substitute_dict[item] if item in substitute_dict else item for item in product_id_list]

        # Flatten the list in case substitutions added nested lists
        flat_list_ID = []
        for i in range(len(main_list)):
            if isinstance(main_list[i], str):
                flat_list_ID.append(main_list[i])
            else:
                flat_list_ID.extend(main_list[i])

        # Filter and separate parts based on F/B designation
        split_BF = self.filter_and_separate(flat_list_ID)
        #print("Here is the result after filter and separate", split_BF)

        for key in list(split_BF.keys())[::-1]: #list is reversed because we need base first for the foot type
            # Set SectionWidth and DistEndToFirstRungRaw depending on section type
            self.SectionWidth = 450 if key == "B" else 367
            self.DistEndToFirstRungRaw = 290 if key == "B" else 305

            # Get section details from DB and update class attributes
            #print("Here is the inputs to get_section_info", split_BF, "here is the key", key)
            self.get_section_info(split_BF, key)
            # dynamic selection
            #print("input to dynamic select",split_BF,"here is the key", key)
            #print("Here is the product display name", product_display_name)
            split_BF_withkey = self.dynamic_select(split_BF, key, product_display_name)
            split_BF = split_BF_withkey
            #print("Here is the split_BF after dynamic select", split_BF)

            # Remove EXL parts from the main list after processing section info
            for i in range(len(split_BF[key]) - 1, -1, -1):
                if "EXL" in split_BF[key][i][0]:
                    split_BF[key].pop(i)

            # Generate hole coordinates
            if key == "F":
                #print("Here is what the split_BF looks like before generate coords", split_BF[key])
                pass
            coords = self.generate_coords(split_BF[key], key)
            # Sort and validate coordinates
            sorted_coordinates = self.sort_by_x_and_face(coords)
            validated_coordinates = self.validate_and_correct_coordinates(
                sorted_coordinates, 
                self.expected_plane[key], 
                self.expected_range[key]
            )

            # Check if Terrain Master exists in the parts; if yes, apply offset
            terrain_master_components = ['BP-LEV-8700-01', "BP-LEV-8606-01", "BP-LEV-8609-01", "BP-LEV-0056-01"]
            our_list_of_components = [item for row in split_BF[key] for item in row]
            if any(terrain_components in our_list_of_components for terrain_components in terrain_master_components):
                #print("\nTerrain Master Detected: Adding relevant Offsets\n")
                validated_coordinates = self.terrain_master_offset(validated_coordinates)

            # Remove unreachable holes
            unreachable_removed = self.remove_unreachable_holes(validated_coordinates)

            # Remove duplicate holes
            unreachable_removed = self.remove_duplicate_holes(unreachable_removed)

            # Save the final coordinates to a text file
            self.format_and_save_coordinates(unreachable_removed, "test" + key, key, ITEM)

            # If the user specifically requested to finalize a 'B' or 'F' section, save again under "testFinal"
            print("execute fly or base" , execute_fly_or_base)
            if execute_fly_or_base == "B" and key == "B":
                self.format_and_save_coordinates(unreachable_removed, "test" + "Final", key, ITEM)
            elif execute_fly_or_base == "F" and key == "F":
                self.format_and_save_coordinates(unreachable_removed, "test" + "Final", key, ITEM)

            #display whether the ladder needs to be docked or not
            if self.DistEndToLastRungCut[execute_fly_or_base] == self.Pitch:
                print("Docking for the ladder not needed")
            else:
                print("Docking for the ladder needed")

        # Close database connections
        self.cursor.close()
        conn.close()
        return execute_fly_or_base
