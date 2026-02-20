import os
import sys

def count_number_of_lines_for_file(file_path):
    """Opens the file under file_path and returns the number of lines in it."""
    with open(file_path, 'r', newline=None) as file:
        return len(file.readlines())
    return -1

def count_lines_for_directory(path, ending=None):
    """
    Opens path as directory, iterates over all files, and maps them to the number of lines.
    When ending is set, only iterates over all files whose file name ends in ending.
    """
    entries = os.scandir(path)
    files   = filter(lambda entry: os.DirEntry.is_file(entry), entries)
    lines   = map(lambda entry: count_number_of_lines_for_file(entry.path), files)
    return lines

def statistics_for_files_in(path, ending=None):
    """
    Counts # of lines, min, max, mean and median in path.
    Asserts that count_lines_for_directory returns line counts.
    Prints these values to the console.
    """
    lines = sorted(count_lines_for_directory(path, ending))
    n = len(lines)
    if n == 0:
        raise ValueError(f"No files exists to count lines for under {path}!")

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
    else:
        print("Usage: python simple_file_statistics.py [input]")
        print("  input  - Path to MTL files")
        # print("  output - Path to the folder where the results will be written")
        # print("Please provide exactly two arguments")