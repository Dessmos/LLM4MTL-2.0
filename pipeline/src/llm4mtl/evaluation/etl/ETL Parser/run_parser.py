#!/usr/bin/env python3
"""
ETL Transformation Evaluation Script

Evaluates LLM-generated ETL transformation files:
1. ETL Parsed Rate - uses Eclipse Epsilon ETL Parser to check syntax validity
2. ETL CHRF Similarity - compares with reference ETL files

Directory structure:
- src/main/resources/<LLM>/<Strategy>/*.etl  -> LLM generated ETL transformations
- src/main/resources/transformations/*.etl   -> Reference ETL transformations
"""
import subprocess
import os
import glob
import csv
from collections import defaultdict

# Optional dependencies
try:
    from fastchrf import aggregate_chrf
    FASTCHRF_AVAILABLE = True
except ImportError:
    FASTCHRF_AVAILABLE = False

# Configuration
LLM_DIRS = ['claude-sonnet-4', 'gemini-2-5-pro', 'gpt-5']
STRATEGY_DIRS = ['few_shot', 'few_shots_AND_grammar', 'grammar', 'only_prompt']

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ETL_RESOURCES_PATH = os.path.join(SCRIPT_DIR, 'src', 'main', 'resources')
ETL_REFERENCES_PATH = os.path.join(ETL_RESOURCES_PATH, 'transformations')


def get_llm_generated_etl_files():
    """Get all LLM-generated ETL transformation files.

    Scans: src/main/resources/<LLM>/<Strategy>/*.etl

    Returns:
        list of dict: path, llm, strategy, filename
    """
    etl_files = []

    for llm in LLM_DIRS:
        for strategy in STRATEGY_DIRS:
            etl_dir = os.path.join(ETL_RESOURCES_PATH, llm, strategy)
            if os.path.exists(etl_dir):
                for etl_path in glob.glob(os.path.join(etl_dir, '*.etl')):
                    filename = os.path.splitext(os.path.basename(etl_path))[0]
                    etl_files.append({
                        'path': os.path.abspath(etl_path),
                        'llm': llm,
                        'strategy': strategy,
                        'filename': filename
                    })

    return etl_files


def get_etl_reference_files():
    """Get reference ETL transformation files.

    Scans: src/main/resources/transformations/*.etl

    Returns:
        dict: filename -> absolute path
    """
    references = {}

    if os.path.exists(ETL_REFERENCES_PATH):
        for etl_path in glob.glob(os.path.join(ETL_REFERENCES_PATH, '*.etl')):
            filename = os.path.splitext(os.path.basename(etl_path))[0]
            references[filename] = os.path.abspath(etl_path)

    return references


def check_etl_syntax(etl_file_path):
    """Check ETL syntax using Eclipse Epsilon ETL Parser.

    Uses ETLParserMain which outputs RESULT:OK:0 or RESULT:FAIL:N.

    Args:
        etl_file_path: Absolute path to ETL file

    Returns:
        tuple: (is_valid: bool, problem_count: int)
    """
    try:
        use_shell = os.name == 'nt'
        mvn_cmd = 'mvn.cmd' if os.name == 'nt' else 'mvn'

        # Use relative path to avoid spaces in path on Windows
        rel_path = os.path.relpath(etl_file_path, SCRIPT_DIR)

        result = subprocess.run(
            [mvn_cmd, '-q', 'exec:java',
             '-Dexec.mainClass=com.example.etlparser.ETLParserMain',
             f'-Dexec.args={rel_path}'],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=60,
            shell=use_shell
        )

        # Parse output: RESULT:OK:0 or RESULT:FAIL:N
        problem_count = 0
        for line in result.stdout.split('\n'):
            if line.startswith('RESULT:'):
                parts = line.split(':')
                if len(parts) >= 3:
                    problem_count = int(parts[2])
                break

        return (result.returncode == 0 and problem_count == 0, problem_count)
    except subprocess.TimeoutExpired:
        return (False, -1)
    except Exception as e:
        print(f"Error: {e}")
        return (False, -1)


def generate_etl_parsed_rate_csv(output_csv='etl_parsed_rate.csv'):
    """Generate ETL parsed rate CSV.

    Uses Eclipse Epsilon ETL Parser to validate ETL syntax.
    Output: LLM, Strategy, File, Parsed, ProblemCount
    """
    etl_files = get_llm_generated_etl_files()

    if not etl_files:
        print("Error: No ETL files found")
        return None

    print(f"Checking ETL syntax for {len(etl_files)} files...\n")

    csv_data = []
    total = len(etl_files)

    for idx, etl in enumerate(etl_files, 1):
        is_valid, problem_count = check_etl_syntax(etl['path'])

        csv_data.append({
            'LLM': etl['llm'],
            'Strategy': etl['strategy'],
            'File': etl['filename'],
            'Parsed': is_valid,
            'ProblemCount': problem_count
        })

        status = "OK" if is_valid else f"FAIL({problem_count})"
        print(f"[{idx}/{total}] [{status}] {etl['llm']}/{etl['strategy']}/{etl['filename']}.etl")

    # Write CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['LLM', 'Strategy', 'File', 'Parsed', 'ProblemCount'])
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\nCSV: {output_csv}")
    print_etl_parsed_rate_summary(csv_data)

    return output_csv


def print_etl_parsed_rate_summary(csv_data):
    """Print ETL parsed rate summary."""
    stats = defaultdict(lambda: {'total': 0, 'valid': 0, 'problems': 0})

    for row in csv_data:
        key = (row['LLM'], row['Strategy'])
        stats[key]['total'] += 1
        if row['Parsed']:
            stats[key]['valid'] += 1
        if row['ProblemCount'] > 0:
            stats[key]['problems'] += row['ProblemCount']

    print("\n" + "=" * 85)
    print("ETL PARSED RATE SUMMARY")
    print("=" * 85)
    print(f"{'LLM':<20} {'Strategy':<25} {'Parsed Rate':<20} {'Total Problems':<15}")
    print("-" * 85)

    for (llm, strategy), s in sorted(stats.items()):
        rate = s['valid'] / s['total'] * 100 if s['total'] > 0 else 0
        print(f"{llm:<20} {strategy:<25} {rate:>6.1f}% ({s['valid']}/{s['total']})      {s['problems']:>5}")

    total_valid = sum(s['valid'] for s in stats.values())
    total_files = sum(s['total'] for s in stats.values())
    total_problems = sum(s['problems'] for s in stats.values())
    overall = total_valid / total_files * 100 if total_files > 0 else 0
    print("-" * 85)
    print(f"{'OVERALL':<46} {overall:>6.1f}% ({total_valid}/{total_files})      {total_problems:>5}")


def generate_etl_chrf_csv(output_csv='etl_chrf_similarity.csv'):
    """Generate ETL CHRF similarity CSV.

    Compares LLM ETL with reference ETL in transformations/.
    Output: LLM, Strategy, File, CHRF_Score
    """
    if not FASTCHRF_AVAILABLE:
        print("Error: pip install fastchrf")
        return None

    etl_files = get_llm_generated_etl_files()
    references = get_etl_reference_files()

    if not etl_files:
        print("Error: No ETL files found")
        return None

    if not references:
        print("Error: No reference ETL files in transformations/")
        return None

    print(f"CHRF: {len(etl_files)} ETL files vs {len(references)} references\n")

    csv_data = []

    for etl in etl_files:
        if etl['filename'] not in references:
            print(f"Warning: No reference for {etl['filename']}.etl")
            continue

        try:
            with open(etl['path'], 'r', encoding='utf-8') as f:
                generated = f.read()
            with open(references[etl['filename']], 'r', encoding='utf-8') as f:
                reference = f.read()

            score = float(aggregate_chrf([[generated]], [[reference]])[0][0])

            csv_data.append({
                'LLM': etl['llm'],
                'Strategy': etl['strategy'],
                'File': etl['filename'],
                'CHRF_Score': round(score, 4)
            })

            print(f"{etl['llm']}/{etl['strategy']}/{etl['filename']}.etl: {score:.2f}")

        except Exception as e:
            print(f"Error: {etl['filename']}: {e}")

    if not csv_data:
        print("No CHRF scores")
        return None

    # Write CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['LLM', 'Strategy', 'File', 'CHRF_Score'])
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\nCSV: {output_csv}")
    print_etl_chrf_summary(csv_data)

    return output_csv


def print_etl_chrf_summary(csv_data):
    """Print ETL CHRF summary."""
    stats = defaultdict(list)

    for row in csv_data:
        stats[(row['LLM'], row['Strategy'])].append(row['CHRF_Score'])

    print("\n" + "=" * 75)
    print("ETL CHRF SIMILARITY SUMMARY")
    print("=" * 75)
    print(f"{'LLM':<20} {'Strategy':<25} {'Avg':<10} {'Min':<10} {'Max':<10}")
    print("-" * 75)

    all_scores = []
    for (llm, strategy), scores in sorted(stats.items()):
        avg = sum(scores) / len(scores)
        all_scores.extend(scores)
        print(f"{llm:<20} {strategy:<25} {avg:>8.2f}   {min(scores):>8.2f}   {max(scores):>8.2f}")

    if all_scores:
        print("-" * 75)
        print(f"{'OVERALL':<46} {sum(all_scores)/len(all_scores):>8.2f}   {min(all_scores):>8.2f}   {max(all_scores):>8.2f}")


def generate_combined_csv(parsed_csv='etl_parsed_rate.csv',
                          chrf_csv='etl_chrf_similarity.csv',
                          output_csv='etl_parser_chrf_results.csv'):
    """Merge parsed rate and CHRF into a single CSV.

    Output: LLM, Strategy, File, Parsed, ProblemCount, CHRF_Score
    """
    # Load parsed rate data
    parsed_data = {}
    if os.path.exists(parsed_csv):
        with open(parsed_csv, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                key = (row['LLM'], row['Strategy'], row['File'])
                parsed_data[key] = {
                    'Parsed': row['Parsed'],
                    'ProblemCount': row['ProblemCount']
                }

    # Load CHRF data
    chrf_data = {}
    if os.path.exists(chrf_csv):
        with open(chrf_csv, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                key = (row['LLM'], row['Strategy'], row['File'])
                chrf_data[key] = row['CHRF_Score']

    # Merge
    all_keys = sorted(set(parsed_data.keys()) | set(chrf_data.keys()))
    csv_rows = []
    for key in all_keys:
        llm, strategy, filename = key
        parsed_info = parsed_data.get(key, {'Parsed': '', 'ProblemCount': ''})
        chrf_score = chrf_data.get(key, '')
        csv_rows.append({
            'LLM': llm,
            'Strategy': strategy,
            'File': filename,
            'Parsed': parsed_info['Parsed'],
            'ProblemCount': parsed_info['ProblemCount'],
            'CHRF_Score': chrf_score
        })

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['LLM', 'Strategy', 'File', 'Parsed', 'ProblemCount', 'CHRF_Score'])
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\nCombined CSV: {output_csv} ({len(csv_rows)} rows)")
    return output_csv


if __name__ == "__main__":
    import sys

    HELP = """
ETL Transformation Evaluation Tool

Usage: python run_parser.py <command>

Commands:
  parsed  - ETL syntax check (Eclipse Epsilon ETL Parser)
            Output: etl_parsed_rate.csv

  chrf    - ETL CHRF similarity with references
            Output: etl_chrf_similarity.csv

  all     - Both reports + combined CSV
            Output: etl_parser_chrf_results.csv
"""

    if len(sys.argv) < 2:
        print(HELP)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "parsed":
        generate_etl_parsed_rate_csv()
    elif cmd == "chrf":
        generate_etl_chrf_csv()
    elif cmd == "all":
        print("=" * 70)
        print("ETL PARSED RATE")
        print("=" * 70)
        generate_etl_parsed_rate_csv()

        print("\n\n" + "=" * 70)
        print("ETL CHRF SIMILARITY")
        print("=" * 70)
        generate_etl_chrf_csv()

        print("\n\n" + "=" * 70)
        print("COMBINED RESULTS")
        print("=" * 70)
        generate_combined_csv()
    else:
        print(f"Unknown: {cmd}")
        print(HELP)
