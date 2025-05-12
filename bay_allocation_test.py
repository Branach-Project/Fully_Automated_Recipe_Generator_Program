class LadderAllocator:
    def __init__(self, num_bays=5):
        # Initialize bays as a list of empty dictionaries
        self.bays = [{} for _ in range(num_bays)]

    def allocate_ladder(self, ladder_type, mo_number):
        """
        Allocates a ladder to a bay based on the MO number.
        """
        # Check if the MO number already exists in any bay
        for i, bay in enumerate(self.bays):
            if mo_number in bay:
                # Add the ladder type to the existing MO in the bay
                bay[mo_number].add(ladder_type)
                print(f"Allocated {ladder_type} with MO {mo_number} to Bay {i + 1}.")
                return

        # If MO number not found, allocate to a new bay
        for i, bay in enumerate(self.bays):
            if not bay:  # Find the first empty bay
                bay[mo_number] = {ladder_type}
                print(f"Allocated {ladder_type} with MO {mo_number} to new Bay {i + 1}.")
                return

        print("Error: No empty bays available for allocation.")

    def clear_bays(self, bays_to_clear):
        """
        Clears the specified bays based on user input.
        """
        for bay_index in bays_to_clear:
            if 0 <= bay_index < len(self.bays):
                self.bays[bay_index] = {}
                print(f"Cleared Bay {bay_index + 1}.")
            else:
                print(f"Error: Bay {bay_index + 1} does not exist.")

    def display_bays(self):
        """
        Displays the current state of all bays.
        """
        print("\nCurrent Bay Allocations:")
        for i, bay in enumerate(self.bays):
            if bay:
                print(f"Bay {i + 1}: {bay}")
            else:
                print(f"Bay {i + 1}: Empty")

# Example usage
allocator = LadderAllocator()

while True:
    print("\nMenu:")
    print("1. Allocate Ladder")
    print("2. Clear Bays")
    print("3. Display Bays")
    print("4. Exit")

    choice = input("Enter your choice: ")

    if choice == "1":
        ladder_type = input("Enter ladder type (fly/base): ").strip().lower()
        mo_number = input("Enter Manufacturing Order (MO) number: ").strip()
        allocator.allocate_ladder(ladder_type, mo_number)
    elif choice == "2":
        bays_to_clear = input("Enter bay numbers to clear (comma-separated): ")
        bays_to_clear = [int(x) - 1 for x in bays_to_clear.split(",")]
        allocator.clear_bays(bays_to_clear)
    elif choice == "3":
        allocator.display_bays()
    elif choice == "4":
        print("Exiting...")
        break
    else:
        print("Invalid choice. Please try again.")
