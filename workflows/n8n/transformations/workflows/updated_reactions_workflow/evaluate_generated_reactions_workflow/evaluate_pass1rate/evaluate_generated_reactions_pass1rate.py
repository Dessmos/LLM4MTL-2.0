#!/usr/bin/env python3
import subprocess
import os
import glob
import csv
import shutil
import time
import json
from pathlib import Path
import xml.etree.ElementTree as ET


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Root directory, where the response files are with the folder structure LLM/strategy/*.reactions
RESPONSES_ROOT = os.path.abspath(
    os.path.join(SCRIPT_DIR, "../../../../mtl_snippets/reactions_language/responses")
)

REFERENCE_REACTIONS_ROOT = os.path.abspath(
    os.path.join(SCRIPT_DIR, "../../../../mtl_snippets/reactions_language/references")
)

TESTCASES_POOL_ROOT = os.path.abspath(
    os.path.join(SCRIPT_DIR, "resources/test_cases")
)

CONFIG_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "task_to_test_cases_mapping_reactions.json")
)

PROJECT_ROOT = os.path.abspath(os.path.join(
    SCRIPT_DIR,
    "../../../../../../",
    "Reactions_Language_Evaluate_Tests",
))

# Directory where the reactions are copied per candidate (will be cleared + overwritten per candidate set).
# One candidate for this analysis is the pair <LLM, strategy>
TARGET_REACTIONS_DIR = os.path.abspath(os.path.join(
    SCRIPT_DIR,
    "../../../../../../",
    "Reactions_Language_Evaluate_Tests",
    "consistency",
    "src/main/reactions/tools/vitruv/methodologisttemplate"
    ))

TARGET_TESTS_ROOT = os.path.abspath(os.path.join(
    SCRIPT_DIR,
    "../../../../../../",
    PROJECT_ROOT,
    "vsum",
    "src",
    "test",
    "java/tools/vitruv/methodologisttemplate/vsum"
))

# Surefire reports from vsum tests
SUREFIRE_DIR = os.path.abspath(os.path.join(
    SCRIPT_DIR,
    "../../../../../../",
    "Reactions_Language_Evaluate_Tests",
    "vsum",
    "target",
    "surefire-reports"
    ))

# Maven command => Reference the maven-wrapper inside the methodologist-template incl. fallback
MVNW = os.path.join(PROJECT_ROOT, "mvnw")
MAVEN_BIN = MVNW if os.path.isfile(MVNW) else "mvn"

# Utility functions

def ensure_dir(dir_path):
    os.makedirs(dir_path, exist_ok=True)

def clear_dir(dir_path):
    """Remove all contents of a directory (but keep the directory)."""
    ensure_dir(dir_path)
    for name in os.listdir(dir_path):
        p = os.path.join(dir_path, name)
        if os.path.isfile(p) or os.path.islink(p):
            os.remove(p)
        else:
            shutil.rmtree(p)


def find_unique_file(root_dir, filename):
    """
    Find a file named `filename` under root_dir recursively.
    - returns absolute path if exactly one match
    - returns None if no match
    - raises if multiple matches
    """
    matches = glob.glob(os.path.join(root_dir, "**", filename), recursive=True)
    matches = [os.path.abspath(m) for m in matches if os.path.isfile(m)]
    if len(matches) == 0:
        return None
    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous file '{filename}' under '{root_dir}'. Matches:\n  " + "\n  ".join(matches))
    return matches[0]


def lower_first_char(s):
    return s[:1].lower() + s[1:] if s else s


def safe_name(*parts):
    raw = "__".join(parts)
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in raw)


def write_text_file(path, content):
    Path(path).write_text(content, encoding="utf-8")


def write_log(name, output_text):
    logs_dir = os.path.join(SCRIPT_DIR, "logs")
    ensure_dir(logs_dir)
    log_path = os.path.join(logs_dir, f"{name}.log")
    Path(log_path).write_text(output_text, encoding="utf-8")
    return log_path


def first_error_line(maven_output):
    for line in maven_output.splitlines():
        if line.startswith("[ERROR]"):
            return line
    return None


# Candidates

def get_all_reactions_candidates():
    """
    Returns list of candidate .reactions files:
      responses/<LLM>/<Strategy>/*.reactions
    """
    if not os.path.isdir(RESPONSES_ROOT):
        raise FileNotFoundError(f"Responses root not found: {RESPONSES_ROOT}")

    candidates = glob.glob(os.path.join(RESPONSES_ROOT, "*", "*", "*.reactions"))
    candidates = [os.path.abspath(p) for p in candidates if os.path.isfile(p)]
    return sorted(candidates)


def extract_metadata_from_path(file_path):
    """
    Extract LLM and Strategy from a directory path like:
      .../responses/<LLM>/<Strategy>
    """
    parts = Path(file_path).parts
    try:
        responses_idx = parts.index("responses")
        llm = parts[responses_idx + 1]
        strategy = parts[responses_idx + 2]
        return llm, strategy
    except (ValueError, IndexError):
        return None, None

# Load the config file.

def load_config(config_path):
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Config must be a JSON list of objects.")

    required_keys = {
        "reaction_under_test",
        "required_correct_reactions_from_references",
        "testcases",
        "required_imports_path_alias",
        "name_of_generated_reaction",
    }
    for i, entry in enumerate(data):
        missing = [k for k in required_keys if k not in entry]
        if missing:
            raise ValueError(f"Config entry #{i} missing keys: {missing}")
    return data


# Prepare Reactions

def copy_reaction_under_test(candidate_file_path):
    """
    Copy the candidate .reactions file into TARGET_REACTIONS_DIR.
    """
    if not os.path.isfile(candidate_file_path):
        raise FileNotFoundError(f"Candidate reactions file not found: {candidate_file_path}")

    destination = os.path.join(TARGET_REACTIONS_DIR, os.path.basename(candidate_file_path))
    shutil.copy2(candidate_file_path, destination)
    return destination



def copy_reference_reactions(required_reference_reactions):
    """
    Copy each <ReferenceReaction>.reactions from REFERENCE_REACTIONS_ROOT into TARGET_REACTIONS_DIR.
    """
    copied = []
    for required_reference_reaction in required_reference_reactions:
        filename = f"{required_reference_reaction}.reactions"
        src = find_unique_file(REFERENCE_REACTIONS_ROOT, filename)
        if not src:
            raise FileNotFoundError(f"Missing reference reaction '{filename}' under: {REFERENCE_REACTIONS_ROOT}")

        destination = os.path.join(TARGET_REACTIONS_DIR, os.path.basename(src))
        shutil.copy2(src, destination)
        copied.append(destination)
    return copied


def build_combined_reactions_content(entry):
    """
    Generates the combined reactions file content, e.g.:

    import "..." as families
    import "..." as persons

    reactions: combinedReactions
    in reaction to changes in families
    execute actions in persons

    import familiesToPersons using qualified names
    import familiesToPersons_InsertedFamilyRegister using qualified names
    ...

    Does not work with Reactions within the same model!
    """
    imports = entry["required_imports_path_alias"]

    import_lines = []
    aliases = []
    for item in imports:
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError("Each required_imports_path_alias element must be a dict with exactly 1 {uri: alias} pair")
        uri, alias = next(iter(item.items()))
        import_lines.append(f'import "{uri}" as {alias}')
        aliases.append(alias)

    changes_alias = aliases[0]
    actions_alias = aliases[1]

    llm_reaction_name = entry["name_of_generated_reaction"]
    ref_files = entry["required_correct_reactions_from_references"]
    reference_reaction_names = [lower_first_char(name) for name in ref_files]

    lines = []
    lines.extend(import_lines)
    lines.append("")
    lines.append("reactions: combinedReactions")
    lines.append(f"in reaction to changes in {changes_alias}")
    lines.append(f"execute actions in {actions_alias}")
    lines.append("")
    lines.append("// The first imported reaction is the llm-generated task")
    lines.append(f"import {llm_reaction_name} using qualified names")
    lines.append("")
    lines.append("// The reactions below are the correct reactions from the references to test the reaction_under_test")
    for reaction_name in reference_reaction_names:
        lines.append(f"import {reaction_name} using qualified names")
    lines.append("")
    return "\n".join(lines)


def write_combined_reactions_file(entry):
    reaction_under_test = entry["reaction_under_test"]
    combined_filename = f"CombinedReactions.reactions"
    combined_path = os.path.join(TARGET_REACTIONS_DIR, combined_filename)
    write_text_file(combined_path, build_combined_reactions_content(entry))
    return combined_path


def prepare_reactions_for_task(candidate_file_path, entry):
    """
    1) Clear reactions dir
    2) Copy reaction_under_test from candidate
    3) Copy required correct reactions from references
    4) Write combined reactions file
    """
    clear_dir(TARGET_REACTIONS_DIR)
    copy_reaction_under_test(candidate_file_path)
    copy_reference_reactions(entry["required_correct_reactions_from_references"])
    write_combined_reactions_file(entry)


# Prepare the respective test cases.

def clear_all_project_tests():
    clear_dir(TARGET_TESTS_ROOT)


def copy_testcases_into_place(testcase_names):
    """
    Clears TARGET_TESTS_ROOT and copies <Test>.java into TARGET_TESTS_ROOT.
    """
    clear_all_project_tests()
    ensure_dir(TARGET_TESTS_ROOT)

    copied = []
    for test_case in testcase_names:
        filename = f"{test_case}.java"
        src = find_unique_file(TESTCASES_POOL_ROOT, filename)
        if not src:
            raise FileNotFoundError(f"Missing testcase source '{filename}' under: {TESTCASES_POOL_ROOT}")

        destination = os.path.join(TARGET_TESTS_ROOT, filename)
        shutil.copy2(src, destination)
        copied.append(destination)
    return copied


# Parse the results

def remove_surefire_reports():
    if os.path.isdir(SUREFIRE_DIR):
        shutil.rmtree(SUREFIRE_DIR, ignore_errors=True)


def parse_surefire_xml():
    """
    Sums TEST-*.xml files in SUREFIRE_DIR.
    Returns dict with: tests, failures, errors, skipped, passed
    """
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "passed": 0}

    if not os.path.isdir(SUREFIRE_DIR):
        return totals

    xml_files = glob.glob(os.path.join(SUREFIRE_DIR, "TEST-*.xml"))
    for xf in xml_files:
        try:
            root = ET.parse(xf).getroot()
        except Exception:
            continue

        if root.tag.endswith("testsuite"):
            totals["tests"] += int(root.attrib.get("tests", "0"))
            totals["failures"] += int(root.attrib.get("failures", "0"))
            totals["errors"] += int(root.attrib.get("errors", "0"))
            totals["skipped"] += int(root.attrib.get("skipped", "0"))

    totals["passed"] = max(
        totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"],
        0
    )
    return totals



def run_maven(clean=False, verify=False):
    """
    Runs Maven for vsum tests. Returns (exit_code, combined_output, duration_s).
    """
    goal = "verify" if verify else "test"

    cmd = [MAVEN_BIN,]
    if clean:
        cmd.append("clean")
    cmd.append(goal)

    start = time.time()
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    duration_s = time.time() - start
    return proc.returncode, proc.stdout, duration_s

# Generate the report:

def create_test_matrix_report(output_csv="test_matrix_report.csv", clean=False, verify=False):
    if not os.path.isfile(os.path.join(PROJECT_ROOT, "pom.xml")):
        raise FileNotFoundError(f"No pom.xml in PROJECT_ROOT: {PROJECT_ROOT}")

    ensure_dir(TARGET_REACTIONS_DIR)
    ensure_dir(TARGET_TESTS_ROOT)

    config_entries = load_config(CONFIG_PATH)
    candidates = get_all_reactions_candidates()

    csv_rows = []

    config_by_task = {e["reaction_under_test"]: e for e in config_entries}

    for candidate_path in candidates:
        llm, strategy = extract_metadata_from_path(candidate_path)
        if not llm or not strategy:
            print(f"Skipping (could not extract LLM/Strategy): {candidate_path}")
            continue

        task = os.path.splitext(os.path.basename(candidate_path))[0]
        entry = config_by_task.get(task)
        if not entry:
            print(f"Skipping (no config entry for task '{task}'): {candidate_path}")
            continue


        testcases = entry["testcases"]

        print(f"\n=== Running: LLM={llm}, Strategy={strategy}, Task={task} ===")
        print(f"Candidate path: {candidate_path}")

        remove_surefire_reports()

        # Step 1/2/4: reactions
        try:
            prepare_reactions_for_task(candidate_path, entry)
        except Exception as e:
            name = safe_name(llm, strategy, task)
            log_path = write_log(name, f"[SCRIPT ERROR] prepare_reactions_failed: {e}\n")
            print(f"[SCRIPT ERROR] prepare_reactions_failed: {e}")
            csv_rows.append({
                "LLM": llm,
                "Strategy": strategy,
                "Task": task,
                "ExitCode": 1,
                "Tests": 0,
                "Passed": 0,
                "Failures": 0,
                "Errors": 0,
                "Skipped": 0,
                "DurationSeconds": "0.00",
                "Stage": "prepare_reactions_failed",
                "FirstError": str(e),
                "Log": log_path
            })
            continue

        # tests
        try:
            copy_testcases_into_place(testcases)
        except Exception as e:
            name = safe_name(llm, strategy, task)
            log_path = write_log(name, f"[SCRIPT ERROR] prepare_tests_failed: {e}\n")
            print(f"[SCRIPT ERROR] prepare_tests_failed: {e}")
            csv_rows.append({
                "LLM": llm,
                "Strategy": strategy,
                "Task": task,
                "ExitCode": 1,
                "Tests": 0,
                "Passed": 0,
                "Failures": 0,
                "Errors": 0,
                "Skipped": 0,
                "DurationSeconds": "0.00",
                "Stage": "prepare_tests_failed",
                "FirstError": str(e),
                "Log": log_path
            })
            continue

        # Maven build + run tests
        exit_code, out, duration_s = run_maven(clean=clean, verify=verify)
        totals = parse_surefire_xml()
        err_line = first_error_line(out) or ""

        name = safe_name(llm, strategy, task)
        log_path = write_log(name, out)

        print(
            f"Result {llm}/{strategy} | {task}: exit={exit_code}, "
            f"tests={totals['tests']}, passed={totals['passed']}, "
            f"failures={totals['failures']}, errors={totals['errors']}, skipped={totals['skipped']}, "
            f"duration_s={duration_s:.2f}"
        )

        csv_rows.append({
            "LLM": llm,
            "Strategy": strategy,
            "Task": task,
            "ExitCode": exit_code,
            "Tests": totals["tests"],
            "Passed": totals["passed"],
            "Failures": totals["failures"],
            "Errors": totals["errors"],
            "Skipped": totals["skipped"],
            "DurationSeconds": f"{duration_s:.2f}",
            "Stage": "ok" if exit_code == 0 else "maven_failed",
            "FirstError": err_line,
            "Log": log_path
        })

    if csv_rows:
        out_path = os.path.join(SCRIPT_DIR, output_csv)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "LLM", "Strategy", "Task",
                "ExitCode", "Tests", "Passed", "Failures", "Errors", "Skipped",
                "DurationSeconds", "Stage", "FirstError", "Log"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

        print(f"\nCSV report created: {out_path}")
        return out_path

    print("No candidates/tasks found.")
    return None

# CLI

if __name__ == "__main__":
    import sys

    # Usage:
    #   python evaluate_generated_reactions_pass1rate.py run
    #   python evaluate_generated_reactions_pass1rate.py run clean
    #   python evaluate_generated_reactions_pass1rate.py run verify
    #   python evaluate_generated_reactions_pass1rate.py run clean verify
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "run"
    flags = [a.lower() for a in sys.argv[2:]]

    if cmd != "run":
        print(f"Unknown command: {cmd}")
        print("Available commands: run")
        sys.exit(1)

    clean = "clean" in flags
    verify = "verify" in flags

    create_test_matrix_report(
        output_csv="test_matrix_report.csv",
        clean=clean,
        verify=verify
    )