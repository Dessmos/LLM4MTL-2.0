#!/usr/bin/env python3
"""
ATL Transformation Evaluation Script

Evaluates LLM-generated ATL transformation files:
1. ATL Parsed Rate - uses Eclipse ATL Parser to check syntax validity
2. ATL CHRF Similarity - compares with reference ATL files

Directory structure:
- src/test/resources/<LLM>/<Strategy>/*.atl  -> LLM generated ATL transformations
- src/test/resources/other_references/*.atl  -> Reference ATL transformations
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
ATL_RESOURCES_PATH = os.path.join(SCRIPT_DIR, 'src', 'test', 'resources')
ATL_REFERENCES_PATH = os.path.join(ATL_RESOURCES_PATH, 'other_references')


def get_llm_generated_atl_files():
    """Get all LLM-generated ATL transformation files.

    Scans: src/test/resources/<LLM>/<Strategy>/*.atl

    Returns:
        list of dict: path, llm, strategy, filename
    """
    atl_files = []

    for llm in LLM_DIRS:
        for strategy in STRATEGY_DIRS:
            atl_dir = os.path.join(ATL_RESOURCES_PATH, llm, strategy)
            if os.path.exists(atl_dir):
                for atl_path in glob.glob(os.path.join(atl_dir, '*.atl')):
                    filename = os.path.splitext(os.path.basename(atl_path))[0]
                    atl_files.append({
                        'path': os.path.abspath(atl_path),
                        'llm': llm,
                        'strategy': strategy,
                        'filename': filename
                    })

    return atl_files


def get_atl_reference_files():
    """Get reference ATL transformation files.

    Scans: src/test/resources/other_references/*.atl

    Returns:
        dict: filename -> absolute path
    """
    references = {}

    if os.path.exists(ATL_REFERENCES_PATH):
        for atl_path in glob.glob(os.path.join(ATL_REFERENCES_PATH, '*.atl')):
            filename = os.path.splitext(os.path.basename(atl_path))[0]
            references[filename] = os.path.abspath(atl_path)

    return references


def check_atl_syntax(atl_file_path):
    """Check ATL syntax using Eclipse ATL Parser (org.eclipse.m2m.atl.engine.parser.AtlParser).

    Uses ATLParserMain which follows the same pattern as AtlParserTest.

    Args:
        atl_file_path: Absolute path to ATL file

    Returns:
        tuple: (is_valid: bool, problem_count: int)
    """
    try:
        use_shell = os.name == 'nt'
        mvn_cmd = 'mvn.cmd' if os.name == 'nt' else 'mvn'

        result = subprocess.run(
            [mvn_cmd, '-q', 'exec:java',
             '-Dexec.mainClass=com.example.atlparser.ATLParserMain',
             f'-Dexec.args={atl_file_path}'],
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

        return (result.returncode == 0, problem_count)
    except subprocess.TimeoutExpired:
        return (False, -1)
    except Exception as e:
        print(f"Error: {e}")
        return (False, -1)


def generate_atl_parsed_rate_csv(output_csv='atl_parsed_rate.csv'):
    """Generate ATL parsed rate CSV.

    Uses Eclipse ATL Parser to validate ATL syntax.
    Output: LLM, Strategy, File, Parsed, ProblemCount
    """
    atl_files = get_llm_generated_atl_files()

    if not atl_files:
        print("Error: No ATL files found")
        return None

    print(f"Checking ATL syntax for {len(atl_files)} files...\n")

    csv_data = []
    total = len(atl_files)

    for idx, atl in enumerate(atl_files, 1):
        is_valid, problem_count = check_atl_syntax(atl['path'])

        csv_data.append({
            'LLM': atl['llm'],
            'Strategy': atl['strategy'],
            'File': atl['filename'],
            'Parsed': is_valid,
            'ProblemCount': problem_count
        })

        status = "OK" if is_valid else f"FAIL({problem_count})"
        print(f"[{idx}/{total}] [{status}] {atl['llm']}/{atl['strategy']}/{atl['filename']}.atl")

    # Write CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['LLM', 'Strategy', 'File', 'Parsed', 'ProblemCount'])
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\nCSV: {output_csv}")
    print_atl_parsed_rate_summary(csv_data)

    return output_csv


def print_atl_parsed_rate_summary(csv_data):
    """Print ATL parsed rate summary."""
    stats = defaultdict(lambda: {'total': 0, 'valid': 0, 'problems': 0})

    for row in csv_data:
        key = (row['LLM'], row['Strategy'])
        stats[key]['total'] += 1
        if row['Parsed']:
            stats[key]['valid'] += 1
        if row['ProblemCount'] > 0:
            stats[key]['problems'] += row['ProblemCount']

    print("\n" + "=" * 85)
    print("ATL PARSED RATE SUMMARY")
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


def generate_atl_chrf_csv(output_csv='atl_chrf_similarity.csv'):
    """Generate ATL CHRF similarity CSV.

    Compares LLM ATL with reference ATL in other_references/.
    Output: LLM, Strategy, File, CHRF_Score
    """
    if not FASTCHRF_AVAILABLE:
        print("Error: pip install fastchrf")
        return None

    atl_files = get_llm_generated_atl_files()
    references = get_atl_reference_files()

    if not atl_files:
        print("Error: No ATL files found")
        return None

    if not references:
        print("Error: No reference ATL files in other_references/")
        return None

    print(f"CHRF: {len(atl_files)} ATL files vs {len(references)} references\n")

    csv_data = []

    for atl in atl_files:
        if atl['filename'] not in references:
            print(f"Warning: No reference for {atl['filename']}.atl")
            continue

        try:
            with open(atl['path'], 'r', encoding='utf-8') as f:
                generated = f.read()
            with open(references[atl['filename']], 'r', encoding='utf-8') as f:
                reference = f.read()

            score = float(aggregate_chrf([[generated]], [[reference]])[0][0])

            csv_data.append({
                'LLM': atl['llm'],
                'Strategy': atl['strategy'],
                'File': atl['filename'],
                'CHRF_Score': round(score, 4)
            })

            print(f"{atl['llm']}/{atl['strategy']}/{atl['filename']}.atl: {score:.2f}")

        except Exception as e:
            print(f"Error: {atl['filename']}: {e}")

    if not csv_data:
        print("No CHRF scores")
        return None

    # Write CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['LLM', 'Strategy', 'File', 'CHRF_Score'])
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\nCSV: {output_csv}")
    print_atl_chrf_summary(csv_data)

    return output_csv


def print_atl_chrf_summary(csv_data):
    """Print ATL CHRF summary."""
    stats = defaultdict(list)

    for row in csv_data:
        stats[(row['LLM'], row['Strategy'])].append(row['CHRF_Score'])

    print("\n" + "=" * 75)
    print("ATL CHRF SIMILARITY SUMMARY")
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


if __name__ == "__main__":
    import sys

    HELP = """
ATL Transformation Evaluation Tool

Usage: python testATLParsedRate.py <command>

Commands:
  parsed  - ATL syntax check (Eclipse ATL Parser)
            Output: atl_parsed_rate.csv

  chrf    - ATL CHRF similarity with references
            Output: atl_chrf_similarity.csv

  all     - Both reports
"""

    if len(sys.argv) < 2:
        print(HELP)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "parsed":
        generate_atl_parsed_rate_csv()
    elif cmd == "chrf":
        generate_atl_chrf_csv()
    elif cmd == "all":
        print("=" * 70)
        print("ATL PARSED RATE")
        print("=" * 70)
        generate_atl_parsed_rate_csv()

        print("\n\n" + "=" * 70)
        print("ATL CHRF SIMILARITY")
        print("=" * 70)
        generate_atl_chrf_csv()
    else:
        print(f"Unknown: {cmd}")
        print(HELP)
