#!/usr/bin/env python3
"""
Reads benchmark_results_detailed.csv, runs JUnit tests for each (model, strategy, file)
combination where parse_success=true, then outputs:
  1. qvto_test_results.csv       - full results with test_pass column
  2. qvto_pass_rate_summary.csv  - pass rate per model x strategy combination

Logic: test_pass = True  only if  parse_success=true AND JUnit test passes
       test_pass = False if parse_success=false OR JUnit test fails/errors
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
TRANSFORM_DIR = os.path.join(PROJECT_DIR, "transformation")
QVTO_TESTS_DIR = os.path.join(PROJECT_DIR, "qvto-tests")
QVTO_SRC_DIR = os.path.join(QVTO_TESTS_DIR, "src", "main", "resources", "transformations")
QVTO_TARGET_DIR = os.path.join(QVTO_TESTS_DIR, "target", "classes", "transformations")
INPUT_CSV = os.path.join(PROJECT_DIR, "benchmark_results_detailed.csv")
OUTPUT_CSV = os.path.join(PROJECT_DIR, "qvto_test_results.csv")
SUMMARY_CSV = os.path.join(PROJECT_DIR, "qvto_pass_rate_summary.csv")

# Mapping from QVTO file base name to JUnit test class (fully qualified)
FILE_TO_TEST = {
    "Constructors":              "org.eclipse.qvto.tests.ConstructorsTest",
    "MappingBody":               "org.eclipse.qvto.tests.MappingBodyTest",
    "MappingExtensionDisjuncts": "org.eclipse.qvto.tests.MappingExtensionDisjunctsTest",
    "MappingExtensionInherits":  "org.eclipse.qvto.tests.MappingExtensionInheritsTest",
    "MappingExtensionMerges":    "org.eclipse.qvto.tests.MappingExtensionMergesTest",
    "Mappings":                  "org.eclipse.qvto.tests.MappingsTest",
    "MappingsWhenClause":        "org.eclipse.qvto.tests.MappingsWhenClauseTest",
    "ModelExtents":              "org.eclipse.qvto.tests.ModelExtentsTest",
    "OverridingMappings":        "org.eclipse.qvto.tests.OverridingMappingsTest",
    "ResolveExpressions":        "org.eclipse.qvto.tests.ResolveExpressionsTest",
}


def run_test(test_class: str) -> tuple:
    """Run a single Maven test class. Returns (passed, error_detail)."""
    cmd = ["mvn", "test", f"-Dtest={test_class}", "-pl", ".", "--batch-mode"]
    try:
        result = subprocess.run(
            cmd,
            cwd=QVTO_TESTS_DIR,
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
                  or "Transformation failed" in line_stripped
                  or "AssertionError" in line_stripped):
                error_detail = line_stripped
                break
        return False, error_detail
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)


def copy_qvto(model: str, strategy: str, file_name: str) -> str | None:
    """
    Copy QVTO file from transformation/{model}/{strategy}/{file_name}
    to both src/main/resources/transformations/ and target/classes/transformations/.
    Returns the destination path if successful, None otherwise.
    """
    src = os.path.join(TRANSFORM_DIR, model, strategy, file_name)
    dst_src = os.path.join(QVTO_SRC_DIR, file_name)
    dst_target = os.path.join(QVTO_TARGET_DIR, file_name)
    if not os.path.exists(src):
        print(f"    WARNING: QVTO source not found: {src}")
        return None
    # Back up originals
    for dst in [dst_src, dst_target]:
        backup = dst + ".bak"
        if os.path.exists(dst) and not os.path.exists(backup):
            shutil.copy2(dst, backup)
    # Copy LLM-generated QVTO to both locations
    shutil.copy(src, dst_src)
    if os.path.exists(QVTO_TARGET_DIR):
        shutil.copy(src, dst_target)
    return dst_src


def restore_qvto(file_name: str):
    """Restore the original QVTO files from backups after testing."""
    for base_dir in [QVTO_SRC_DIR, QVTO_TARGET_DIR]:
        dst = os.path.join(base_dir, file_name)
        backup = dst + ".bak"
        if os.path.exists(backup):
            shutil.copy2(backup, dst)
            os.remove(backup)


def write_summary_csv(results):
    """Generate pass rate summary CSV grouped by model and strategy."""
    stats = defaultdict(lambda: {"passed": 0, "total": 0})
    for r in results:
        key = (r["model"], r["strategy"])
        stats[key]["total"] += 1
        if r["test_pass"] == "True":
            stats[key]["passed"] += 1

    sorted_keys = sorted(stats.keys())

    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "strategy", "total", "passed", "failed", "pass_rate"])
        for model, strategy in sorted_keys:
            s = stats[(model, strategy)]
            failed = s["total"] - s["passed"]
            rate = s["passed"] / s["total"] * 100 if s["total"] > 0 else 0.0
            writer.writerow([model, strategy, s["total"], s["passed"], failed, f"{rate:.1f}%"])

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
        model = row["model"]
        strategy = row["strategy"]
        file_name = row["file"]            # e.g. "Constructors.qvto"
        parse_success = row["parse_success"].strip().lower() == "true"
        file_base = file_name.replace(".qvto", "")

        print(f"[{i+1}/{total}] {model} | {strategy} | {file_name} | parse_success={parse_success}")

        # Determine test_pass
        if file_base not in FILE_TO_TEST:
            test_pass = "False"
            print(f"    -> False (no test class mapping)")
        elif not parse_success:
            test_pass = "False"
            print(f"    -> False (parser failed)")
        else:
            # parse_success=true and test class exists: copy QVTO and run the test
            if not copy_qvto(model, strategy, file_name):
                test_pass = "False"
                print(f"    -> False (QVTO file not found)")
            else:
                test_class = FILE_TO_TEST[file_base]
                print(f"    Running test: {test_class} ...")
                passed, error_detail = run_test(test_class)
                test_pass = "True" if passed else "False"
                print(f"    -> {test_pass}" + (f" ({error_detail})" if error_detail else ""))
                restore_qvto(file_name)

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
    print(f"  Pass Rate: {pass_count/total*100:.1f}%")
    print(f"\nResults written to: {OUTPUT_CSV}")

    # Write pass rate summary
    write_summary_csv(results)


if __name__ == "__main__":
    main()
