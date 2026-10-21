#!/usr/bin/env python3
"""
Reads atl_parser_chrf_results.csv, runs JUnit tests for each (LLM, Strategy, File)
combination where Parsed=True, then outputs:
  1. atl_test_results.csv       - full results with test_pass column
  2. atl_pass_rate_summary.csv  - pass rate per LLM x Strategy combination

Logic: test_pass = True  only if  Parsed=True AND JUnit test passes
       test_pass = False if Parsed=False OR JUnit test fails/errors
"""

import csv
import os
import shutil
import subprocess
import sys
from collections import defaultdict

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ATL_SRC_DIR = os.path.join(PROJECT_DIR, "src", "main", "atl")
ATL_REF_DIR = os.path.join(ATL_SRC_DIR, "reference")
INPUT_CSV = os.path.join(PROJECT_DIR, "atl_parser_chrf_results.csv")
OUTPUT_CSV = os.path.join(PROJECT_DIR, "atl_test_results.csv")
SUMMARY_CSV = os.path.join(PROJECT_DIR, "atl_pass_rate_summary.csv")

# Mapping from ATL file base name to JUnit test class (fully qualified)
FILE_TO_TEST = {
    "AmaltheaToAscet_All":  "org.example.AmaltheaToAscetAllExecutionTest",
    "BibTeX2DocBook_All":   "org.example.BibTeX2DocBookAllExecutionTest",
    "CPL2SPL_All":          "org.example.CPL2SPLAllExecutionTest",
    "Class2Interface_All":  "org.example.Class2InterfaceAllExecutionTest",
    "DSL2KM3_All":          "org.example.DSL2KM3AllExecutionTest",
    "Document2Report_All":  "org.example.Document2ReportAllExecutionTest",
    "FamiliesToPersons_All":"org.example.FamiliesToPersonsAllExecutionTest",
    "Grafcet2PetriNet_All": "org.example.Grafcet2PetriNetAllExecutionTest",
    "IEEE1471_2_MoDAF_All": "org.example.IEEE1471_2_MoDAFAllExecutionTest",
    "Item2Product_All":     "org.example.Item2ProductAllExecutionTest",
    "Make2Ant_All":         "org.example.Make2AntAllExecutionTest",
    "NetworkToGraph_All":   "org.example.NetworkToGraphAllExecutionTest",
    "PetriNet2Grafcet_All": "org.example.PetriNet2GrafcetAllExecutionTest",
    "User2Account_All":     "org.example.User2AccountAllExecutionTest",
    "XML2DSL_All":          "org.example.XML2DSLAllExecutionTest",
}


def run_test(test_class: str) -> bool:
    """Run a single Maven test class. Returns True if the test passes."""
    cmd = ["mvn", "test", f"-Dtest={test_class}", "-pl", ".", "-q", "--batch-mode"]
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=120,
            shell=True,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT for {test_class}")
        return False
    except Exception as e:
        print(f"    ERROR running {test_class}: {e}")
        return False


def copy_atl(llm: str, strategy: str, file_name: str) -> bool:
    """Copy ATL file from reference/{llm}/{strategy}/ to src/main/atl/. Returns True if successful."""
    src = os.path.join(ATL_REF_DIR, llm, strategy, f"{file_name}.atl")
    dst = os.path.join(ATL_SRC_DIR, f"{file_name}.atl")
    if not os.path.exists(src):
        print(f"    WARNING: ATL source not found: {src}")
        return False
    shutil.copy2(src, dst)
    return True


def cleanup_atl(file_name: str):
    """Remove the copied ATL file after testing."""
    dst = os.path.join(ATL_SRC_DIR, f"{file_name}.atl")
    if os.path.exists(dst):
        os.remove(dst)


def write_summary_csv(results):
    """Generate pass rate summary CSV grouped by LLM and Strategy."""
    # Collect stats: (LLM, Strategy) -> {passed, total}
    stats = defaultdict(lambda: {"passed": 0, "total": 0})
    for r in results:
        key = (r["LLM"], r["Strategy"])
        stats[key]["total"] += 1
        if r["test_pass"] == "True":
            stats[key]["passed"] += 1

    # Sort by LLM then Strategy
    sorted_keys = sorted(stats.keys())

    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["LLM", "Strategy", "total", "passed", "failed", "pass_rate"])
        for llm, strategy in sorted_keys:
            s = stats[(llm, strategy)]
            failed = s["total"] - s["passed"]
            rate = s["passed"] / s["total"] * 100 if s["total"] > 0 else 0.0
            writer.writerow([llm, strategy, s["total"], s["passed"], failed, f"{rate:.1f}%"])

    print(f"\nPass rate summary written to: {SUMMARY_CSV}")


def main():
    # Read input CSV
    with open(INPUT_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    results = []

    print(f"Processing {total} combinations...")
    print("=" * 70)

    for i, row in enumerate(rows):
        llm = row["LLM"]
        strategy = row["Strategy"]
        file_name = row["File"]
        parsed = row["Parsed"].strip() == "True"

        print(f"[{i+1}/{total}] {llm} | {strategy} | {file_name} | Parsed={parsed}")

        # Determine test_pass
        if file_name not in FILE_TO_TEST:
            test_pass = "False"
            print(f"    -> False (no test class mapping)")
        elif not parsed:
            test_pass = "False"
            print(f"    -> False (parser failed)")
        else:
            # Parsed=True and test class exists: run the test
            if not copy_atl(llm, strategy, file_name):
                test_pass = "False"
                print(f"    -> False (ATL file not found)")
            else:
                test_class = FILE_TO_TEST[file_name]
                print(f"    Running test: {test_class} ...")
                passed = run_test(test_class)
                test_pass = "True" if passed else "False"
                print(f"    -> {test_pass}")
                cleanup_atl(file_name)

        result_row = dict(row)
        result_row["test_pass"] = test_pass
        results.append(result_row)

    # Write output CSV
    fieldnames = list(rows[0].keys()) + ["test_pass"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    pass_count = sum(1 for r in results if r["test_pass"] == "True")
    fail_count = sum(1 for r in results if r["test_pass"] == "False")
    print(f"  Total:    {total}")
    print(f"  Passed:   {pass_count}")
    print(f"  Failed:   {fail_count}")
    print(f"\nResults written to: {OUTPUT_CSV}")

    # Write pass rate summary
    write_summary_csv(results)


if __name__ == "__main__":
    main()
