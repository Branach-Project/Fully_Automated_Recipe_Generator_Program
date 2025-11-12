import os

# Define your path and file name
Path = r"A:\E091-01 Manufacturing Info System\CAM Output"
File_Name = "testFinal.txt"

# Join them into one full file path
file_path = os.path.join(Path, File_Name)

def count_lines(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return len(lines)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return 0

if __name__ == "__main__":
    line_count = count_lines(file_path)
    print(File_Name)
    print(f"Total number of lines: {line_count}")
