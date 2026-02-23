"""
File utilities for finding ground truth files and counting LOC.
"""

from pathlib import Path


def find_ground_truth_dir(repo_root):
    """
    Automatically find the ground truth directory containing .atl or .qvto files

    Args:
        repo_root: Repository root directory path

    Returns:
        Ground truth directory path, or None if not found
    """
    repo_path = Path(repo_root)

    # Possible ground truth directory patterns
    possible_patterns = [
        '**/other_references',
        '**/referenceATL',
        '**/reference',
        '**/src/main/resources/transformations',
    ]

    for pattern in possible_patterns:
        for gt_dir in repo_path.glob(pattern):
            if gt_dir.is_dir():
                # Check if it contains .atl or .qvto files
                atl_files = list(gt_dir.glob('*.atl'))
                qvto_files = list(gt_dir.glob('*.qvto'))
                if atl_files or qvto_files:
                    return str(gt_dir)

    # If not found, try searching for directories containing multiple .atl files
    for atl_file in repo_path.rglob('*.atl'):
        parent = atl_file.parent
        if len(list(parent.glob('*.atl'))) >= 5:
            return str(parent)

    # Try searching for directories containing multiple .qvto files
    for qvto_file in repo_path.rglob('*.qvto'):
        parent = qvto_file.parent
        if len(list(parent.glob('*.qvto'))) >= 5:
            return str(parent)

    return None


def count_loc(file_path):
    """
    Count LOC of an ATL or QVT-O file (excluding empty lines and pure comment lines)

    Args:
        file_path: ATL or QVT-O file path

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

    for gt_file in list(gt_path.glob('*.atl')) + list(gt_path.glob('*.qvto')):
        file_name = gt_file.stem  # Without extension
        loc = count_loc(gt_file)
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

    # Strip extension (.atl, .qvto) and try again
    stem = Path(file_name).stem
    if stem in file_to_loc:
        return file_to_loc[stem]

    # Try adding _All suffix
    if f"{stem}_All" in file_to_loc:
        return file_to_loc[f"{stem}_All"]

    # Try removing _All suffix
    if stem.endswith('_All'):
        base_name = stem[:-4]
        if base_name in file_to_loc:
            return file_to_loc[base_name]

    return None

