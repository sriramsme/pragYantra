import os
import platform
import subprocess
import shutil
import json
import csv
from .. import helper
from ..entity_models import FilePath

@helper 
def get_dest_from_src(src:FilePath, dest=None):
    """
    Generates a destination path based on the source path if not provided.
    If a file with the same name exists, appends a number to the filename.

    Parameters:
    src (str): The source file path.
    dest (str): The destination file path (optional).

    Returns:
    str: The destination path.
    """
    if dest is None:
        # Use the same directory as the source file
        src_dir = os.path.dirname(src.path)
        src_name, src_ext = os.path.splitext(os.path.basename(src.path))
        dest = os.path.join(src_dir, src_name + src_ext)
        
        # Check if the file already exists and append a number if it does
        counter = 1
        while os.path.exists(dest):
            dest = os.path.join(src_dir, f"{src_name}_{counter}{src_ext}")
            counter += 1
    
    return dest

def file_explorer(path:FilePath):
    """
    Searches for files matching a pattern, including partial paths, prioritizing common directories.
    """
    return path.path

def open_location(path:FilePath):
    """
    Opens the specified path location. The function is device-independent 
    and works on Windows, macOS, and Linux.

    Parameters:
    path (str): The path to the directory or file to be opened in the file explorer. 
                The path can include the user directory symbol (~) which will be expanded 
                to the full path.
    
    """
    
    # Identify the operating system
    current_os = platform.system()
    
    try:
        if current_os == "Windows":
            subprocess.run(["explorer", path.path])
        elif current_os == "Darwin":  # macOS
            subprocess.run(["open", path.path])
        elif current_os == "Linux":
            subprocess.run(["xdg-open", path.path])
        else:
            raise OSError(f"Unsupported operating system: {current_os}")
    except Exception as e:
        print(f"Failed to open file explorer: {e}")

def create_directory(path:FilePath):
    """
    Creates a directory at the specified path.

    Parameters:
    path (str): The path where the directory should be created.

    """
    try:
        os.makedirs(path.path, exist_ok=True)
        print(f"Directory created at: {path.path}")
    except OSError as e:
        print(f"Failed to create directory: {e}")

def delete_file(path:FilePath):
    """
    Deletes the file at the specified path.

    Parameters:
    path (str): The path to the file to be deleted.

    """
    try:
        os.remove(path.path)
        print(f"File deleted: {path.path}")
    except OSError as e:
        print(f"Failed to delete file: {e}")

def copy_file(src:FilePath, dest=None):
    """
    Copies a file from the source path to the destination path.

    Parameters:
    src (str): The source file path.
    dest (str): The destination file path.

    """
    dest = get_dest_from_src(src,dest)

    try:
        shutil.copy(src.path, dest)
        print(f"File copied from {src.path} to {dest}")
    except OSError as e:
        print(f"Failed to copy file: {e}")

def move_file(src:FilePath, dest):
    """
    Moves a file from the source path to the destination path.

    Parameters:
    src (str): The source file path.
    dest (str): The destination file path.

    """
    dest = get_dest_from_src(src,dest)
    try:
        shutil.move(src.path, dest)
        print(f"File moved from {src.path} to {dest}")
    except OSError as e:
        print(f"Failed to move file: {e}")

def rename_file(src:FilePath, new_name):
    """
    Renames a file to the new specified name.

    Parameters:
    src (str): The current file path.
    new_name (str): The new name for the file.

    """
    new_name = os.path.expanduser(new_name)
    try:
        os.rename(src.path, new_name)
        print(f"File renamed from {src.path} to {new_name}")
    except OSError as e:
        print(f"Failed to rename file: {e}")

def list_files(directory:FilePath):
    """
    Lists all files and directories in the specified directory.

    Parameters:
    directory (str): The path to the directory to be listed.

    """
    try:
        files = os.listdir(directory.path)
        print(f"Files in {directory.path}: {files}")
        return files
    except OSError as e:
        print(f"Failed to list files: {e}")
        return []

def read_file(path:FilePath):
    """
    Reads and returns the contents of the specified file.

    Parameters:
    path (str): The path to the file to be read.

    """
    try:
        with open(path.path, 'r') as file:
            contents = file.read()
            print(f"Contents of {path.path}: {contents}")
            return contents
    except OSError as e:
        print(f"Failed to read file: {e}")
        return None

def write_to_file(path:FilePath, content):
    """
    Writes the specified content to the file at the given path. Creates the file if it does not exist.

    Parameters:
    path (str): The path to the file to be written to.
    content (str): The content to be written to the file.

    """
    try:
        with open(path.path, 'w') as file:
            file.write(content)
            print(f"Written to {path.path}: {content}")
    except OSError as e:
        print(f"Failed to write to file: {e}")

# def convert_file(input_path, output_path, input_format, output_format):
#     """
#     Converts a file from one format to another.

#     Parameters:
#     input_path (str): The path to the input file.
#     output_path (str): The path to the output file.
#     input_format (str): The format of the input file ('text', 'json', 'csv').
#     output_format (str): The format of the output file ('text', 'json', 'csv').

#     """

#     # Read the input file
#     try:
#         if input_format == 'text':
#             with open(input_path, 'r') as file:
#                 data = file.readlines()
#         elif input_format == 'json':
#             with open(input_path, 'r') as file:
#                 data = json.load(file)
#         elif input_format == 'csv':
#             with open(input_path, 'r') as file:
#                 reader = csv.reader(file)
#                 data = list(reader)
#         else:
#             raise ValueError(f"Unsupported input format: {input_format}")
#     except OSError as e:
#         print(f"Failed to read input file: {e}")
#         return

#     # Write the output file
#     try:
#         if output_format == 'text':
#             with open(output_path, 'w') as file:
#                 if isinstance(data, list):
#                     file.writelines(data)
#                 else:
#                     file.write(str(data))
#         elif output_format == 'json':
#             with open(output_path, 'w') as file:
#                 json.dump(data, file, indent=4)
#         elif output_format == 'csv':
#             with open(output_path, 'w', newline='') as file:
#                 writer = csv.writer(file)
#                 if isinstance(data, list):
#                     for row in data:
#                         writer.writerow(row)
#                 else:
#                     writer.writerow([data])
#         else:
#             raise ValueError(f"Unsupported output format: {output_format}")
#         print(f"File converted from {input_format} to {output_format} and saved to {output_path}")
#     except OSError as e:
#         print(f"Failed to write output file: {e}")

# def merge_files(file_paths, output_path):
#     """
#     Merges the contents of multiple files into a single file.

#     Parameters:
#     file_paths (list): A list of file paths to be merged.
#     output_path (str): The path to the output file where merged content will be saved.

#     """
#     output_path = os.path.expanduser(output_path)
#     try:
#         with open(output_path, 'w') as outfile:
#             for file_path in file_paths:
#                 file_path = os.path.expanduser(file_path)
#                 try:
#                     with open(file_path, 'r') as infile:
#                         outfile.write(infile.read() + '\n')
#                     print(f"File {file_path} merged.")
#                 except OSError as e:
#                     print(f"Failed to read file {file_path}: {e}")
#         print(f"All files merged into {output_path}")
#     except OSError as e:
#         print(f"Failed to write to output file {output_path}: {e}")


def main():
    """
    Main function to provide a command-line interface for searching a file by name.
    """
    print("File Search")

    file_name = input("Enter the file name to search for: ")
    search_root = input("Enter the root directory to start the search (leave empty to search from root): ")

    file_name = FilePath(file_name,search_root=search_root)
    # FilePath("*.txt", search_root="/home/user/documents")
    # FilePath("log_\d{4}-\d{2}-\d{2}", use_regex=True, search_root="/var/log")

    open_location(file_name)

if __name__ == "__main__":
    main()