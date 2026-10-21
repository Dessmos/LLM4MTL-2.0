#!/usr/bin/env python3
"""
Reads etl_parser_chrf_results.csv, runs JUnit tests for each (LLM, Strategy, File)
combination where Parsed=True, then outputs:
  1. etl_test_results.csv       - full results with test_pass column
  2. etl_pass_rate_summary.csv  - pass rate per LLM x Strategy combination

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
ETL_REF_DIR = os.path.join(PROJECT_DIR, "resources")
ETL_SRC_DIR = os.path.join(PROJECT_DIR, "src", "test", "resources", "transformations")
ETL_TARGET_DIR = os.path.join(PROJECT_DIR, "target", "test-classes", "transformations")
INPUT_CSV = os.path.join(PROJECT_DIR, "etl_parser_chrf_results.csv")
OUTPUT_CSV = os.path.join(PROJECT_DIR, "etl_test_results.csv")
SUMMARY_CSV = os.path.join(PROJECT_DIR, "etl_pass_rate_summary.csv")

# Mapping from ETL file base name to JUnit test class (fully qualified)
FILE_TO_TEST = {
    "OO2DB":            "org.eclipse.epsilon.examples.etl.OO2DBTest",
    "Tree2Graph":       "org.eclipse.epsilon.examples.etl.Tree2GraphTest",
    "rss2atom":         "org.eclipse.epsilon.examples.etl.Rss2AtomTest",
    "base":             "org.eclipse.epsilon.examples.etl.flowchart.BaseTest",
    "equivalent":       "org.eclipse.epsilon.examples.etl.flowchart.EquivalentTest",
    "greedy":           "org.eclipse.epsilon.examples.etl.flowchart.GreedyTest",
    "inheritance":      "org.eclipse.epsilon.examples.etl.flowchart.InheritanceTest",
    "lazy":             "org.eclipse.epsilon.examples.etl.flowchart.LazyTest",
    "multiple_targets": "org.eclipse.epsilon.examples.etl.flowchart.MultipleTargetsTest",
    "primary":          "org.eclipse.epsilon.examples.etl.flowchart.PrimaryTest",
}


def run_test(test_class: str) -> tuple[bool, str]:
    """Run a single Maven test class. Returns (passed, error_detail)."""
    cmd = ["mvn", "test", f"-Dtest={test_class}", "-pl", ".", "--batch-mode"]
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=120,
            shell=True,
        )
        if result.returncode == 0:
            return True, ""
        # Extract error detail from output
        output = result.stdout + result.stderr
        error_detail = ""
        for line in output.splitlines():
            line_stripped = line.strip()
            if "Errors:" in line_stripped or "Failures:" in line_stripped:
                if line_stripped not in ("Errors:", "Failures:"):
                    error_detail = line_stripped
            elif ("expected:" in line_stripped or "Expected" in line_stripped
                  or "NotFound" in line_stripped or "RuntimeException" in line_stripped
                  or "ETL parse errors" in line_stripped):
                error_detail = line_stripped
                break
        return False, error_detail
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)


def copy_etl(llm: str, strategy: str, file_name: str) -> str | None:
    """
    Copy ETL file from resources/{llm}/{strategy}/{file_name}.etl
    to both src/test/resources/transformations/ and target/test-classes/transformations/.
    Returns the destination path if successful, None otherwise.
    """
    src = os.path.join(ETL_REF_DIR, llm, strategy, f"{file_name}.etl")
    dst_src = os.path.join(ETL_SRC_DIR, f"{file_name}.etl")
    dst_target = os.path.join(ETL_TARGET_DIR, f"{file_name}.etl")
    if not os.path.exists(src):
        print(f"    WARNING: ETL source not found: {src}")
        return None
    # Back up originals
    for dst in [dst_src, dst_target]:
        backup = dst + ".bak"
        if os.path.exists(dst) and not os.path.exists(backup):
            shutil.copy2(dst, backup)
    # Copy LLM-generated ETL to both locations
    shutil.copy(src, dst_src)
    if os.path.exists(ETL_TARGET_DIR):
        shutil.copy(src, dst_target)
    return dst_src


def restore_etl(file_name: str):
    """Restore the original ETL files from backups after testing."""
    for base_dir in [ETL_SRC_DIR, ETL_TARGET_DIR]:
        dst = os.path.join(base_dir, f"{file_name}.etl")
        backup = dst + ".bak"
        if os.path.exists(backup):
            shutil.copy2(backup, dst)
            os.remove(backup)


def write_summary_csv(results):
    """Generate pass rate summary CSV grouped by LLM and Strategy."""
    stats = defaultdict(lambda: {"passed": 0, "total": 0})
    for r in results:
        key = (r["LLM"], r["Strategy"])
        stats[key]["total"] += 1
        if r["test_pass"] == "True":
            stats[key]["passed"] += 1

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
            # Parsed=True and test class exists: copy ETL and run the test
            if not copy_etl(llm, strategy, file_name):
                test_pass = "False"
                print(f"    -> False (ETL file not found)")
            else:
                test_class = FILE_TO_TEST[file_name]
                print(f"    Running test: {test_class} ...")
                passed, error_detail = run_test(test_class)
                test_pass = "True" if passed else "False"
                print(f"    -> {test_pass}" + (f" ({error_detail})" if error_detail else ""))
                restore_etl(file_name)

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
