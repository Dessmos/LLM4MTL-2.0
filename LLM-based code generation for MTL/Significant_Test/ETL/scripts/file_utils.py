"""
File utilities for finding ground truth files and counting LOC.
"""

from pathlib import Path


def find_ground_truth_dir(repo_root):
    """
    Automatically find the ground truth directory containing .etl files
    
    Args:
        repo_root: Repository root directory path
        
    Returns:
        Ground truth directory path, or None if not found
    """
    repo_path = Path(repo_root)
    
    # Possible ground truth directory patterns
    possible_patterns = [
        '**/transformations',
        '**/other_references',
        '**/referenceATL',
        '**/reference',
    ]
    
    for pattern in possible_patterns:
        for atl_dir in repo_path.glob(pattern):
            if atl_dir.is_dir():
                # Check if it contains .etl files
                atl_files = list(atl_dir.glob('*.etl'))
                if atl_files:
                    return str(atl_dir)
    
    # If not found, try searching the entire repo for directories containing .etl files
    for atl_file in repo_path.rglob('*.etl'):
        parent = atl_file.parent
        # Check if parent directory looks like a ground truth directory (contains multiple .etl files)
        if len(list(parent.glob('*.etl'))) >= 5:  # At least 5 files to be considered a ground truth directory
            return str(parent)
    
    return None


def count_loc_atl(file_path):
    """
    Count LOC of an ATL file (excluding empty lines and pure comment lines)
    
    Args:
        file_path: ATL file path
        
    Returns:
        LOC count
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        loc_count = 0
        for line in lines:
            stripped = line.strip()
            # Exclude empty lines
            if not stripped:
                continue
            # Exclude pure comment lines (starting with --)
            if stripped.startswith('--'):
                continue
            loc_count += 1
        
        return loc_count
    except Exception as e:
        print(f"Warning: Cannot read file {file_path}: {e}")
        return 0


def build_file_to_loc_mapping(gt_dir):
    """
    Build File -> reference_LOC mapping
    
    Args:
        gt_dir: Ground truth directory path
        
    Returns:
        dict: {File name (without extension): LOC count}
    """
    gt_path = Path(gt_dir)
    file_to_loc = {}
    
    for atl_file in gt_path.glob('*.etl'):
        file_name = atl_file.stem  # Without extension
        loc = count_loc_atl(atl_file)
        if loc > 0:
            file_to_loc[file_name] = loc
    
    return file_to_loc


def match_file_to_ground_truth(file_name, file_to_loc):
    """
    Try to match CSV File field to ground truth file name
    
    Args:
        file_name: File field in CSV
        file_to_loc: Ground truth file to LOC mapping
        
    Returns:
        Matched LOC count, or None if not found
    """
    # Direct match
    if file_name in file_to_loc:
        return file_to_loc[file_name]
    
    # Try adding _All suffix
    if f"{file_name}_All" in file_to_loc:
        return file_to_loc[f"{file_name}_All"]
    
    # Try removing _All suffix
    if file_name.endswith('_All'):
        base_name = file_name[:-4]
        if base_name in file_to_loc:
            return file_to_loc[base_name]
    
    return None

