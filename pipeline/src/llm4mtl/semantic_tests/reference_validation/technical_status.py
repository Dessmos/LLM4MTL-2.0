"""Technical-validation CSV filtering for reference validation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from llm4mtl.semantic_tests.suites.models import CandidateSuite


SuiteKey = tuple[str, str, str, str]


def filter_technically_valid_suites(
    suites: list[CandidateSuite], args: argparse.Namespace
) -> list[CandidateSuite]:
    if args.include_unchecked:
        return suites

    valid_keys = load_valid_suite_keys(args.results_root.resolve())
    return [suite for suite in suites if suite_key(suite) in valid_keys]


def load_valid_suite_keys(results_root: Path) -> set[SuiteKey]:
    valid: set[SuiteKey] = set()
    for csv_path in sorted(results_root.glob("*/generated_suite_technical_validation.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("technically_valid") == "True":
                    valid.add(
                        (
                            row.get("task", ""),
                            row.get("llm", ""),
                            row.get("strategy", ""),
                            row.get("suite_id", ""),
                        )
                    )
    return valid


def suite_key(suite: CandidateSuite) -> SuiteKey:
    return (suite.task, suite.llm, suite.strategy, suite.suite_id)
