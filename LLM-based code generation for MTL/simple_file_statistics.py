import os
import sys

def count_number_of_lines_for_file(file_path, comment):
    """
    Opens the file under file_path and returns the number of lines in it.
    Does not count lines starting with comment.
    """
    with open(file_path, 'r', newline=None) as file:
        lines = file.readlines()
        # Skip emptylines
        lines = filter(lambda line: not line.isspace(), lines)
        # Skip comments, if there are any
        # Single-Line comments only
        if comment != None:
            lines = filter(lambda line: not line.lstrip().startswith(comment), lines)
        return len(list(lines))
    return -1

def count_lines_for_directory(path, comment=None):
    """
    Opens path as directory, iterates over all files, and maps them to the number of lines.
    When ending is set, only iterates over all files whose file name ends in ending.
    """
    entries = os.scandir(path)
    files   = filter(lambda entry: os.DirEntry.is_file(entry), entries)
    lines   = map(lambda entry: count_number_of_lines_for_file(entry.path, comment), files)
    return lines

def statistics_for_files_in(path, comment=None):
    """
    Counts # of lines, min, max, mean and median in path.
    Asserts that count_lines_for_directory returns line counts.
    Prints these values to the console.
    """
    lines = sorted(count_lines_for_directory(path, comment))
    n = len(lines)
    if n == 0:
        raise ValueError(f"No files exist to count lines for under {path}!")

    min_lines, max_lines = min(lines), max(lines)
    # Compute Mean
    mean = sum(lines) / n
    # Compute Median
    median = (lines[n // 2] + lines[n // 2 - 1]) / 2 if n % 2 == 0 else lines[n // 2]
    print(f"Statistics for {path}:")
    print(f"n = {n}, all_lines = {sum(lines)}")
    print(f"min = {min_lines}, median = {median}, max = {max_lines}")
    print(f"avg = {mean}")

if __name__ == "__main__":
    if len(sys.argv) == 2:
        statistics_for_files_in(sys.argv[1])
    elif len(sys.argv) == 3:
        statistics_for_files_in(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python simple_file_statistics.py [input] [comment]?")
        print("  input  - Path to MTL files")
        print("  comment - Starts of comment lines that should be ignored")