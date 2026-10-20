from pydantic import BaseModel, field_validator, Field
from typing import List, Union, Optional, Any, ClassVar, Dict, Tuple
from dateutil import parser
import re
import os
import fnmatch
import concurrent.futures
from pathlib import Path
from . import helper
import platform

### Notes: 
# if there are multiple fields in the class, override init function to take an input str and process it to extract the required fields
# if there is only one field, use field_validator to extract the required fields

# @helper
def extract_numeric(value):
    if type(value) in [int, float]:
        return value
    # find all digits and decimal points in the value
    numeric_part = ''.join(re.findall(r'\d+\.?\d*', value))
    return float(numeric_part)

# @helper
def extract_string(value):
    str_part = ''.join(re.findall(r'[a-zA-Z]+', value))
    return str_part

# @helper
def extract_unit(value):
    unit_part = ''.join(re.findall(r'[^\d.]+', value)).strip()
    return unit_part


@helper
def get_common_directories():
    """
    Returns a list of common directories to prioritize in the search.
    """
    home = Path.home()
    common_dirs = [
        home / "Documents",
        home / "Downloads",
        home / "Desktop",
        home / "Pictures",
        home / "Videos",
        home / "Music",
    ]

    windows_specific_dirs = [
        home / "OneDrive",
        home / "Saved Games",
        home / "Favorites",
        home / "Links",
    ]

    mac_specific_dirs = [
        home / "Applications",
        home / "Library",
        home / "Movies",
        home / "Sites",
    ]

    linux_specific_dirs = [
        home / "bin",
        home / ".local" / "share",
        Path("/usr/local/bin"),
        Path("/etc"),
        home / "Templates",
    ]

    current_os = platform.system()
    if current_os == "Windows":
        common_dirs.extend(windows_specific_dirs) 
    elif current_os == "Darwin":
        common_dirs.extend(mac_specific_dirs)
    elif current_os == "Linux":
        common_dirs.extend(linux_specific_dirs)
    # Add more common directories as needed
    return [str(dir) for dir in common_dirs if dir.exists()]

@helper
def file_explorer(file_pattern, search_root='/', use_regex=False, case_sensitive=False, max_depth=None):
    """
    Searches for files matching a pattern, including partial paths, prioritizing common directories.
    """
    found_files = []
    search_root = os.path.expanduser(search_root)
    print(search_root)
    # Split the file_pattern into directory part and file part
    pattern_parts = file_pattern.split('/')
    dir_pattern = '/'.join(pattern_parts[:-1])
    file_pattern = pattern_parts[-1]

    if not case_sensitive and not use_regex:
        file_pattern = file_pattern.lower()
        dir_pattern = dir_pattern.lower()

    if use_regex:
        file_regex = re.compile(file_pattern, re.IGNORECASE if not case_sensitive else 0)
        dir_regex = re.compile(dir_pattern, re.IGNORECASE if not case_sensitive else 0) if dir_pattern else None
    else:
        if '.' not in file_pattern and '*' not in file_pattern:
            file_pattern = file_pattern + '.*'
        file_regex = re.compile(fnmatch.translate(file_pattern), re.IGNORECASE if not case_sensitive else 0)
        dir_regex = re.compile(fnmatch.translate(dir_pattern), re.IGNORECASE if not case_sensitive else 0) if dir_pattern else None

    def search_in_directory(root, current_depth=0):
        if max_depth is not None and current_depth > max_depth:
            return []

        local_found = []
        try:
            for entry in os.scandir(root):
                relative_path = os.path.relpath(entry.path, search_root)
                if not case_sensitive:
                    relative_path = relative_path.lower()

                if entry.is_file():
                    if (dir_regex is None or dir_regex.search(os.path.dirname(relative_path))) and \
                       file_regex.search(entry.name if case_sensitive else entry.name.lower()):
                        local_found.append(entry.path)
                elif entry.is_dir():
                    if dir_regex is None or dir_regex.search(relative_path):
                        local_found.extend(search_in_directory(entry.path, current_depth + 1))
        except PermissionError:
            print(f"Permission denied: {root}")
        except Exception as e:
            print(f"Error accessing {root}: {e}")

        return local_found

    # First, search in common directories
    common_dirs = get_common_directories()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        common_futures = [executor.submit(search_in_directory, dir) for dir in common_dirs]
        for future in concurrent.futures.as_completed(common_futures):
            found_files.extend(future.result())

    # If files are found in common directories, return them
    if found_files:
        return found_files

    # If no files found in common directories, search from the specified root
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(search_in_directory, os.path.join(search_root, dir))
                   for dir in os.listdir(search_root) if os.path.isdir(os.path.join(search_root, dir))]
        for future in concurrent.futures.as_completed(futures):
            found_files.extend(future.result())

    return found_files

@helper
def get_valid_path(path,search_root='/',**kwargs):
    """
    Returns the full path of the specified file or directory if it exists, otherwise tries to find it on device.

    Parameters:
    path (str): The path to the file or directory.

    Returns:
    str: The full path of the file or directory if it exists, otherwise None.

    """
    path = os.path.expanduser(path)
    if os.path.exists(path):
        return path
    else:
        found_paths = file_explorer(path,search_root,**kwargs)
        if found_paths:
            return found_paths[0]
        else:
            return None


class CARDINAL(BaseModel):
    """Numerals that do not fall under another type"""
    value: Any = Field(..., description="Value of cardinal numeral")
    description: ClassVar[str] = "Any cardinal numerals"

    @field_validator('value')
    @classmethod
    def get_numeric(cls,v):
        return extract_numeric(v)

class DATE(BaseModel):
    """Absolute or relative dates or periods"""
    date: str = Field(..., description="string value of date")
    description: ClassVar[str] = "Any absolute or relative dates or period in appropriate date format"

    @field_validator('date')
    @classmethod
    def check_date_format(cls, v):
        try:
            parsed_date = parser.parse(v, default=None)

            # Check specificity of the date and format accordingly
            if parsed_date.hour == 0 and parsed_date.minute == 0 and parsed_date.second == 0:
                # Date only
                return parsed_date.strftime('%Y%m%d')
            # Optionally, convert to a specific format, e.g., ISO 8601
            else:
                return parsed_date.strftime('%Y%m%dT%H')
        except ValueError:
            raise ValueError("Invalid date format")

class EVENT(BaseModel):
    """Named hurricanes, battles, wars, sports events, etc."""
    name: str = Field(..., description="Name of the event")
    description: ClassVar[str] = "Any named events"

class FAC(BaseModel):
    """Buildings, airports, highways, bridges, etc."""
    name: str = Field(..., description="Name of the facility")
    description: ClassVar[str] = "Any named facilities like buildings, airports, highways, bridges, etc."

class GPE(BaseModel):
    """Countries, cities, states"""
    name: str = Field(..., description="Name of the geographical location")
    description: ClassVar[str] = "Any named geographical locations like countries, cities, states"

class LANGUAGE(BaseModel):
    # LANGUAGE :  Any named language
    name: str = Field(..., description="Name of the language")
    description: ClassVar[str] = "Any named language"

class LAW(BaseModel):
    # LAW :  Named documents made into laws.
    name: str = Field(..., description="Name of the law")
    description: ClassVar[str] = "Any named documents made into laws"

class LOC(BaseModel):
    ## LOC :  Non-GPE locations, mountain ranges, bodies of water
    name: str = Field(..., description="Name of the location")
    description: ClassVar[str] = "Any named non-GPE locations like mountain ranges, bodies of water"

class MONEY(BaseModel):
    # MONEY :  Monetary values, including unit
    value: Union[float, int] = Field(..., gt=0,description="Value of the monetary amount")
    currency: Optional[str] = Field("USD", description="Currency of the monetary amount")
    description: ClassVar[str] = "Any monetary values, including unit (default: USD if not found.)"

    def __init__(self, input_string: str):
        numeric_part = extract_numeric(input_string)
        unit_part = extract_unit(input_string)
        super().__init__(value=numeric_part, currency=unit_part)

class NORP(BaseModel):
    # NORP :  Nationalities or religious or political groups
    name: str = Field(..., description="Name of the group")
    description: ClassVar[str] = "Any named nationalities or religious or political groups"

class ORDINAL(BaseModel):
    # ORDINAL :  "first", "second", etc.
    value: str = Field(..., description="Ordinal value")
    description: ClassVar[str] = "Any ordinal values like 'first', 'second', etc."

class ORG(BaseModel):
    # ORG :  Companies, agencies, institutions, etc.
    name: str = Field(..., description="Name of the organization")
    description: ClassVar[str] = "Any named organizations like companies, agencies, institutions, etc."

class PERCENT(BaseModel):
    # PERCENT :  Percentage, including "%"
    value: Union[float, int] = Field(..., gt=0, lt=100,description="Value of percentage")
    description: ClassVar[str] = "Any percentage values"

class PERSON(BaseModel):
    # PERSON :  People, including fictional
    name: str = Field(..., description="Name of the person")
    description: ClassVar[str] = "Any named persons, including fictional"

class PRODUCT(BaseModel):
    # PRODUCT :  Objects, vehicles, foods, etc. (not services)
    name: str = Field(..., description="Name of the product")
    description: ClassVar[str] = "Any named products like objects, vehicles, foods, etc."

class QUANTITY(BaseModel):
    # QUANTITY :  Measurements, as of weight or distance
    value: Union[float, int] = Field(...,description="Value of the quantity measurement")
    unit: Optional[str] = Field(None, description="Unit of quantity measurement")
    description: ClassVar[str] = "Any quantity measurements, as of weight or distance"

    def __init__(self, input_string: str=None, **kwargs):
        if input_string is None:
            super().__init__(**kwargs)
        else:
            numeric_part = extract_numeric(input_string)
            unit_part = extract_unit(input_string)
            super().__init__(value=numeric_part, unit=unit_part)

    
class TIME(BaseModel):
    # TIME :  Times smaller than a day
    time: str = Field(...,description="Value of time") # Assuming HH:MM:SS format
    description: ClassVar[str] = "Any time values in HH:MM:SS like format"

    @field_validator('time')
    @classmethod
    def check_time_format(cls, v):
        try:
            # Parse the string to datetime object
            parsed_time = parser.parse(v)
            # Extract the time part
            extracted_time = parsed_time.time()
            # Optionally, convert to a specific string format if needed
            return extracted_time.strftime('%H:%M:%S')
        except ValueError:
            raise ValueError("Invalid time format")

class WORK_OF_ART(BaseModel):
    # WORK_OF_ART :  Titles of books, songs, etc.
    name: str = Field(..., description="Name of the work of art")
    description: ClassVar[str] = "Any named works of art like titles of books, songs, etc."

class FilePath(BaseModel):
    path: str = Field(..., description="File or folder path")
    description: ClassVar[str] = "File or folder path"

    def __init__(self, path: str, **kwargs):
        """
        kwargs: dict-> search_root='/', use_regex=False, case_sensitive=False, max_depth=None
        """
        path = get_valid_path(path, **kwargs)
        super().__init__(path=path)

# class CustomList(BaseModel):
#     item_type: Union[str, type]
#     items: List[Any]
#     description: ClassVar[str] = f"A list of items of type {item_type}. The description of the item type is as follows: {item_type.description}"
# class CustomDict(BaseModel):
#     items: Dict[str, Any] = Field(..., description="A dictionary of key-value pairs")

# class CustomTuple(BaseModel):
#     items: Tuple[Any, ...] = Field(..., description="A tuple of items")