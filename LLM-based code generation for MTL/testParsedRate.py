#!/bin/bash
import subprocess
import os
import glob
import csv
from pathlib import Path
from fastchrf import aggregate_chrf

reactions_response_paths = []

def get_all_reactions_response():
    global reactions_response_paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_path = os.path.abspath(os.path.join(script_dir, 'Workflows/n8n-docker/mtl_snippets/reactions_language/responses'))
    reactions_response_paths = [os.path.abspath(f) for f in glob.glob(os.path.join(search_path, '**/*.reactions'), recursive=True)]
    return reactions_response_paths

def check_parsed_rate(input_reactions, output_xmi):
    result = subprocess.call(['java', '-jar', 'Reactions_Langauge_Parser/parser/target/tools.vitruv.reactionsparser.parser-0.1.0-SNAPSHOT-all.jar', input_reactions, output_xmi, 'Workflows/n8n-docker/models'])
    return result == 0  # Return True if successful (exit code 0), False otherwise

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

def create_csv_report(output_csv='parsed_rate_report.csv'):
    """Create CSV with LLM, Strategy, and parsed status for each reaction file."""
    get_all_reactions_response()
    
    csv_data = []
    for reaction_file in reactions_response_paths:
        llm, strategy = extract_metadata_from_path(reaction_file)
        parsed = check_parsed_rate(reaction_file, 'output.xmi')
        print(f"Processed {reaction_file}: LLM={llm}, Strategy={strategy}, Parsed={parsed}")
        if llm and strategy:
            # For now, we'll mark as 'unknown' - update with actual parsing results
            csv_data.append({
                'LLM': llm,
                'Strategy': strategy,
                'Parsed': parsed
            })
    
    # Write to CSV
    if csv_data:
        with open(output_csv, 'w', newline='') as csvfile:
            fieldnames = ['LLM', 'Strategy', 'Parsed']
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_path = os.path.abspath(os.path.join(script_dir, 'Workflows/n8n-docker/mtl_snippets/reactions_language/references'))
    references = [os.path.abspath(f) for f in glob.glob(os.path.join(search_path, '**/*.reactions'), recursive=True)]
    return references

def extract_filename_from_path(file_path):
    """Extract filename without extension from path."""
    return os.path.splitext(os.path.basename(file_path))[0]

def create_similarity_report(output_csv='chrf_similarity_report.csv'):
    """Generate CHRF similarity scores between responses and references.
    
    Creates a CSV with columns: LLM, Strategy, File, Score
    """
    get_all_reactions_response()
    references = get_all_reactions_references()
    
    # Create a mapping of reference filenames to their full paths
    reference_map = {}
    for ref_file in references:
        filename = extract_filename_from_path(ref_file)
        reference_map[filename] = ref_file
    
    csv_data = []
    
    # Process each response file
    for response_file in reactions_response_paths:
        llm, strategy = extract_metadata_from_path(response_file)
        response_filename = extract_filename_from_path(response_file)
        
        if llm and strategy and response_filename in reference_map:
            ref_file = reference_map[response_filename]
            
            # Read the content of both files
            try:
                with open(response_file, 'r', encoding='utf-8') as f:
                    response_content = f.read()
                with open(ref_file, 'r', encoding='utf-8') as f:
                    reference_content = f.read()
                
                # Calculate CHRF score
                scores = aggregate_chrf([[response_content]], [[reference_content]])
                score = float(scores[0][0])
                            
                csv_data.append({
                    'LLM': llm,
                    'Strategy': strategy,
                    'File': response_filename,
                    'Score': score
                })
                print(f"Processed {response_filename}: LLM={llm}, Strategy={strategy}, Score={score:.4f}")
            except Exception as e:
                print(f"Error processing {response_file}: {e}")
        else:
            if response_filename not in reference_map:
                print(f"Warning: No corresponding reference found for {response_filename}")
    
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