#!/bin/bash
import subprocess
import os
import glob
import csv
from pathlib import Path
from fastchrf import aggregate_chrf, pairwise_chrf
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import re



SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

JAR_PATH = os.path.join(
    SCRIPT_DIR,
    "../../../../../"
    "ReactionParser",
    "target",
    "reactionsparser.jar"
)
RESULT_RE = re.compile(r"^RESULT\s+(.*?)\s+(\d+)\s*$")

REACTIONS_RESPONSE_DIRECTORY = os.path.join(
    SCRIPT_DIR,
    "../../../",
    "mtl_snippets",
    "reactions_language",
    "responses"
)

REFERENCE_REACTIONS_DIRECTORY = os.path.join(
    SCRIPT_DIR,
    "../../../",
    "mtl_snippets",
    "reactions_language",
    "references"
)

ECORE_MODELS_DIRECTORY = os.path.join(
    SCRIPT_DIR,
    "../../../models/"
)

reactions_response_paths = []


def get_all_reactions_response():
    global reactions_response_paths
    search_path = REACTIONS_RESPONSE_DIRECTORY
    reactions_response_paths = [os.path.abspath(f) for f in glob.glob(os.path.join(search_path, '**/*.reactions'), recursive=True)]
    return reactions_response_paths

def check_parsed_rate(input_reactions):
    """
    Runs the reactions ANTLR parser JAR on one file.

    Returns:
        (parsed_ok, error_count)

    parsed_ok = True if exit code == 0
    error_count = number of syntax errors reported
    """
    if not os.path.isfile(JAR_PATH):
        raise FileNotFoundError(f"JAR not found: {JAR_PATH}")
    proc = subprocess.run(
        ["java", "-jar", JAR_PATH, input_reactions],
        capture_output=True,
        text=True,
    )
    parsed_ok = (proc.returncode == 0)
    output_lines = (proc.stdout + "\n" + proc.stderr).splitlines()
    error_count = None
    for line in output_lines:
        m = RESULT_RE.match(line.strip())
        if m:
            error_count = int(m.group(2))
            break
    if error_count is None:
        error_count = 0 if parsed_ok else -1

    return parsed_ok, error_count


def count_lines_of_code(file_path):
    """
    Count non-empty lines in the .reactions file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Count only non-empty lines
        loc = sum(1 for line in lines if line.strip() != "")
        return loc

    except Exception as e:
        print(f"Error counting LOC for {file_path}: {e}")
        return 0


def extract_metadata_from_path(file_path):
    """Extract LLM and Strategy from the file path."""
    path_parts = Path(file_path).parts
    # Find indices of 'responses' directory
    try:
        responses_idx = path_parts.index('responses')
        llm = path_parts[responses_idx + 1]
        strategy = path_parts[responses_idx + 2]
        return llm, strategy
    except (ValueError, IndexError):
        return None, None

def process_reaction_file(reaction_file):
    """Module-level function for parallel processing of reaction files."""
    llm, strategy = extract_metadata_from_path(reaction_file)
    parsed, error_count = check_parsed_rate(reaction_file, f'{llm}_{strategy}_output.xmi')
    print(f"Processed {reaction_file}: LLM={llm}, Strategy={strategy}, Parsed={parsed}")
    if llm and strategy:
        return {
            'ReactionFile': reaction_file,
            'LLM': llm,
            'Strategy': strategy,
            'Parsed': parsed,
            'Error_Count': error_count
        }
    return None

def create_csv_report(output_csv='./results/parsed_rate/parsed_rate_report.csv'):
    """Create CSV with LLM, Strategy, and parsed status for each reaction file."""
    get_all_reactions_response()
    
    csv_data = []
    for reaction_file in reactions_response_paths:
        llm, strategy = extract_metadata_from_path(reaction_file)
        parsed, error_count = check_parsed_rate(reaction_file)
        loc = count_lines_of_code(reaction_file)
        errors_per_loc = error_count / loc if loc > 0 else ""
        print(f"Processed {reaction_file}: LLM={llm}, Strategy={strategy}, Parsed={parsed}, Error_Count={error_count}, LinesOfCode={loc}, ErrorsPerLic={errors_per_loc}")
        if llm and strategy:
            # For now, we'll mark as 'unknown' - update with actual parsing results
            csv_data.append({
                'ReactionFile': reaction_file,
                'LLM': llm,
                'Strategy': strategy,
                'Parsed': parsed,
                'Error_Count': error_count,
                'NumberOfLinesOfCode': loc,
                'ErrorsPerLineOfCode': errors_per_loc
            })
    
    # Write to CSV
    if csv_data:
        with open(output_csv, 'w', newline='') as csvfile:
            fieldnames = ['ReactionFile', 'LLM', 'Strategy', 'Parsed', 'Error_Count', 'NumberOfLinesOfCode', 'ErrorsPerLineOfCode']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)
        print(f"CSV report created: {output_csv}")
        return output_csv
    else:
        print("No reaction files found")
        return None
    
def get_all_reactions_references():
    """Get all reference files from the references folder."""
    search_path = REFERENCE_REACTIONS_DIRECTORY
    references = [os.path.abspath(f) for f in glob.glob(os.path.join(search_path, '**/*.reactions'), recursive=True)]
    return references

def extract_filename_from_path(file_path):
    """Extract filename without extension from path."""
    return os.path.splitext(os.path.basename(file_path))[0]

# Global for similarity processing (accessed by process_response_file_parallel)
_reference_map = {}

def process_response_file_parallel(response_file):
    """Module-level function for parallel processing of response files."""
    llm, strategy = extract_metadata_from_path(response_file)
    response_filename = extract_filename_from_path(response_file)
    
    if llm and strategy and response_filename in _reference_map:
        ref_file = _reference_map[response_filename]
        
        # Read the content of both files
        try:
            with open(response_file, 'r', encoding='utf-8') as f:
                response_content = f.read()
            with open(ref_file, 'r', encoding='utf-8') as f:
                reference_content = f.read()
            
            # Calculate CHRF score
            scores = aggregate_chrf([[response_content]], [[reference_content]])
            score = float(scores[0][0])
                        
            print(f"Processed {response_filename}: LLM={llm}, Strategy={strategy}, Score={score:.4f}")
            return {
                'LLM': llm,
                'Strategy': strategy,
                'File': response_filename,
                'Score': score
            }
        except Exception as e:
            print(f"Error processing {response_file}: {e}")
            return None
    else:
        if response_filename not in _reference_map:
            print(f"Warning: No corresponding reference found for {response_filename}")
        return None

def create_similarity_report(output_csv='chrf_similarity_report.csv'):
    """Generate CHRF similarity scores between responses and references.
    
    Creates a CSV with columns: LLM, Strategy, File, Score
    """
    global _reference_map

    get_all_reactions_response()
    references = get_all_reactions_references()
    
    # Create a mapping of reference filenames to their full paths
    _reference_map = {}
    for ref_file in references:
        filename = extract_filename_from_path(ref_file)
        _reference_map[filename] = ref_file
    
    csv_data = []
    
    # Parallelize file I/O and CHRF calculation
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_response_file_parallel, response_file) for response_file in reactions_response_paths]
        for future in as_completed(futures):
            result = future.result()
            if result:
                csv_data.append(result)
    
    # Write to CSV
    if csv_data:
        with open(output_csv, 'w', newline='') as csvfile:
            fieldnames = ['LLM', 'Strategy', 'File', 'Score']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)
        print(f"CHRF similarity report created: {output_csv}")
        return output_csv
    else:
        print("No matching response-reference pairs found")
        return None
    
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "parsed":
            create_csv_report()
        elif command == "similarity":
            create_similarity_report()
        elif command == "all":
            create_csv_report()
            create_similarity_report()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: parsed, similarity, all")
    else:
        print("Usage: python testParsedRate.py [parsed|similarity|all]")
        print("  parsed    - Generate parsed rate report")
        print("  similarity - Generate CHRF similarity report")
        print("  all       - Generate both reports")