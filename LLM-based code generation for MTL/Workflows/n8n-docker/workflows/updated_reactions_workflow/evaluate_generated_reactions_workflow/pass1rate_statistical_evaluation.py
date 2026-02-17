from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Optional

from statsmodels.stats.contingency_tables import mcnemar


BASELINE_STRATEGY = "only_prompt"


def parse_bool(x) -> bool:
    s = (x or "").strip().lower()
    if s in {"true", "1"}:
        return True
    if s in {"false", "0"}:
        return False
    raise ValueError(f"Cannot parse boolean from: {x!r}")


def task_from_reaction_file(path: str) -> str:
    """
    ReactionFile is usually an absolute path to .../<Task>.reactions
    -> returns "<Task>" (without extension)
    """
    base = os.path.basename(path)
    return os.path.splitext(base)[0]


def tests_passed(row: dict) -> bool:
    """
    Define "tests passed" conservatively:
      - ExitCode == 0
      - Failures == 0
      - Errors == 0
    """
    try:
        exit_code = int((row.get("ExitCode") or "0").strip())
        failures = int((row.get("Failures") or "0").strip())
        errors = int((row.get("Errors") or "0").strip())
    except ValueError:
        return False
    return exit_code == 0 and failures == 0 and errors == 0


@dataclass(frozen=True)
class Row:
    llm: str
    strategy: str
    task_id: str
    success: bool  # Parsed AND tests passed


def load_parsed_map(parsed_csv: Path) -> Dict[Tuple[str, str, str], bool]:
    """
    Returns dict[(llm, strategy, task)] = parsed_bool
    Expects columns: ReactionFile, LLM, Strategy, Parsed
    """
    parsed_map: Dict[Tuple[str, str, str], bool] = {}
    with parsed_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"ReactionFile", "LLM", "Strategy", "Parsed"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Parsed CSV missing required columns: {sorted(missing)}")

        for r in reader:
            llm = (r.get("LLM") or "").strip()
            strategy = (r.get("Strategy") or "").strip()
            reaction_file = (r.get("ReactionFile") or "").strip()
            if not llm or not strategy or not reaction_file:
                continue

            task = task_from_reaction_file(reaction_file)
            parsed = parse_bool(r.get("Parsed", ""))
            parsed_map[(llm, strategy, task)] = parsed
    return parsed_map


def read_rows(parsed_csv: Path, test_csv: Path) -> List[Row]:
    """
    Join parsed report + test report by (LLM, Strategy, Task).

    - success = parsed AND tests_passed
    - we iterate over the test report rows (the evaluation ground truth for pass/fail)
      and look up parsed; missing parsed => treat as False.
    """
    parsed_map = load_parsed_map(parsed_csv)

    rows: List[Row] = []
    with test_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"LLM", "Strategy", "Task", "ExitCode", "Failures", "Errors"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Test CSV missing required columns: {sorted(missing)}")

        for r in reader:
            llm = (r.get("LLM") or "").strip()
            strategy = (r.get("Strategy") or "").strip()
            task = (r.get("Task") or "").strip()
            if not llm or not strategy or not task:
                continue

            passed = tests_passed(r)
            parsed = parsed_map.get((llm, strategy, task), False)

            success = parsed and passed
            rows.append(Row(llm=llm, strategy=strategy, task_id=task, success=success))

    return rows


def write_success_pivot_csv(rows: Iterable[Row], out_csv: Path) -> None:
    """
    (1) Summary pivot: success-rate (pass@1 proxy) per strategy x llm.

    Rows = strategy
    Cols = llm
    Cell = success_rate over all tasks present for that (llm,strategy)
    """
    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    trues: Dict[Tuple[str, str], int] = defaultdict(int)
    llms = set()
    strategies = set()

    for row in rows:
        key = (row.strategy, row.llm)
        counts[key] += 1
        trues[key] += int(row.success)
        llms.add(row.llm)
        strategies.add(row.strategy)

    llm_list = sorted(llms)
    strategy_list = sorted(strategies)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Strategy (SuccessRate)"] + llm_list)

        for strat in strategy_list:
            line = [strat]
            for llm in llm_list:
                key = (strat, llm)
                n = counts.get(key, 0)
                if n == 0:
                    line.append("")
                else:
                    rate = trues[key] / n
                    line.append(f"{rate:.10f}".rstrip("0").rstrip(".") if rate not in (0.0, 1.0) else str(rate))
            w.writerow(line)


def write_mcnemar_vs_baseline_csv(
    rows: Iterable[Row],
    out_csv: Path,
    baseline_strategy: str = BASELINE_STRATEGY,
) -> None:
    """
    (2) For each llm, compare each strategy vs baseline using paired task_id within that llm,
        using statsmodels' exact McNemar test on SUCCESS event.
    """
    # Map: llm -> strategy -> task_id -> success
    data: Dict[str, Dict[str, Dict[str, bool]]] = defaultdict(lambda: defaultdict(dict))
    llms = set()
    strategies = set()

    for row in rows:
        llms.add(row.llm)
        strategies.add(row.strategy)
        data[row.llm][row.strategy][row.task_id] = row.success

    llm_list = sorted(llms)
    strategy_list = sorted(strategies)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "LLM",
                "Strategy",
                "BaselineStrategy",
                "PairedN",
                "a_both_false",
                "b_baseline_true_strategy_false",
                "c_baseline_false_strategy_true",
                "d_both_true",
                "ExactMcNemarP",
            ]
        )

        for llm in llm_list:
            base_map = data[llm].get(baseline_strategy, {})
            if not base_map:
                for strat in strategy_list:
                    if strat == baseline_strategy:
                        continue
                    w.writerow([llm, strat, baseline_strategy, 0, 0, 0, 0, 0, ""])
                continue

            for strat in strategy_list:
                if strat == baseline_strategy:
                    continue
                strat_map = data[llm].get(strat, {})
                if not strat_map:
                    w.writerow([llm, strat, baseline_strategy, 0, 0, 0, 0, 0, ""])
                    continue

                common = sorted(set(base_map.keys()) & set(strat_map.keys()))
                if not common:
                    w.writerow([llm, strat, baseline_strategy, 0, 0, 0, 0, 0, ""])
                    continue

                a = b = c = d = 0
                for tid in common:
                    base_ok = base_map[tid]
                    strat_ok = strat_map[tid]

                    if (not base_ok) and (not strat_ok):
                        a += 1
                    elif base_ok and (not strat_ok):
                        b += 1
                    elif (not base_ok) and strat_ok:
                        c += 1
                    else:
                        d += 1

                table = [[a, c], [b, d]]

                try:
                    res = mcnemar(table, exact=True)
                    p_str = f"{float(res.pvalue):.12g}"
                except Exception:
                    p_str = ""

                w.writerow([llm, strat, baseline_strategy, len(common), a, b, c, d, p_str])


def write_llm_pairwise_within_strategy_mcnemar_csv(
    rows: Iterable[Row],
    out_csv: Path,
) -> None:
    """
    (3) For each strategy, compare LLMs pairwise on SUCCESS event,
        using exact McNemar on paired task_id.

    Rates are computed on the paired sample (common tasks) so they match the test.
    """
    # Map: strategy -> llm -> task_id -> success
    data: Dict[str, Dict[str, Dict[str, bool]]] = defaultdict(lambda: defaultdict(dict))
    strategies = set()
    llms = set()

    for row in rows:
        strategies.add(row.strategy)
        llms.add(row.llm)
        data[row.strategy][row.llm][row.task_id] = row.success

    strategy_list = sorted(strategies)
    llm_list = sorted(llms)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "Strategy",
                "LLM1",
                "SuccessRateLLM1",
                "LLM2",
                "SuccessRateLLM2",
                "PairedN",
                "a_both_false",
                "b_llm1_true_llm2_false",
                "c_llm1_false_llm2_true",
                "d_both_true",
                "ExactMcNemarP",
            ]
        )

        for strat in strategy_list:
            llms_here = sorted([llm for llm in llm_list if data[strat].get(llm)])
            if len(llms_here) < 2:
                continue

            for i in range(len(llms_here)):
                for j in range(i + 1, len(llms_here)):
                    llm1 = llms_here[i]
                    llm2 = llms_here[j]

                    m1 = data[strat][llm1]
                    m2 = data[strat][llm2]

                    common = sorted(set(m1.keys()) & set(m2.keys()))
                    if not common:
                        w.writerow([strat, llm1, "", llm2, "", 0, 0, 0, 0, 0, ""])
                        continue

                    a = b = c = d = 0
                    s1 = 0
                    s2 = 0
                    for tid in common:
                        ok1 = m1[tid]
                        ok2 = m2[tid]
                        s1 += int(ok1)
                        s2 += int(ok2)

                        if (not ok1) and (not ok2):
                            a += 1
                        elif ok1 and (not ok2):
                            b += 1
                        elif (not ok1) and ok2:
                            c += 1
                        else:
                            d += 1

                    rate1 = s1 / len(common)
                    rate2 = s2 / len(common)

                    table = [[a, c], [b, d]]

                    if (b + c) == 0:
                        p_str = "1"
                    else:
                        try:
                            res = mcnemar(table, exact=True)
                            p_str = f"{float(res.pvalue):.12g}"
                        except Exception:
                            p_str = ""

                    w.writerow(
                        [
                            strat,
                            llm1,
                            f"{rate1:.10f}".rstrip("0").rstrip(".") if rate1 not in (0.0, 1.0) else str(rate1),
                            llm2,
                            f"{rate2:.10f}".rstrip("0").rstrip(".") if rate2 not in (0.0, 1.0) else str(rate2),
                            len(common),
                            a,
                            b,
                            c,
                            d,
                            p_str,
                        ]
                    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Success = Parsed AND tests passed: summary + exact McNemar vs baseline + pairwise LLMs."
    )
    ap.add_argument("parsed_csv", type=Path, help="Parsed-rate report CSV (ReactionFile,LLM,Strategy,Parsed,...)")
    ap.add_argument("test_csv", type=Path, help="Test report CSV (LLM,Strategy,Task,ExitCode,Failures,Errors,...)")

    ap.add_argument(
        "--summary-out",
        type=Path,
        default=Path("success_rate_pivot.csv"),
        help="Output CSV: success-rate pivot (rows=strategy, cols=llm)",
    )

    ap.add_argument(
        "--mcnemar-vs-baseline-out",
        type=Path,
        default=Path("mcnemar_success_vs_baseline_within_llm.csv"),
        help="Output CSV: exact McNemar strategy vs baseline within each LLM",
    )

    ap.add_argument(
        "--mcnemar-llm-pairwise-out",
        type=Path,
        default=Path("mcnemar_success_llm_pairwise_within_strategy.csv"),
        help="Output CSV: exact McNemar LLM pairwise within each strategy",
    )

    ap.add_argument(
        "--baseline",
        type=str,
        default=BASELINE_STRATEGY,
        help='Baseline strategy name (default: "only_prompt")',
    )

    args = ap.parse_args(argv)

    rows = read_rows(args.parsed_csv, args.test_csv)

    write_success_pivot_csv(rows, args.summary_out)
    write_mcnemar_vs_baseline_csv(rows, args.mcnemar_vs_baseline_out, baseline_strategy=args.baseline)
    write_llm_pairwise_within_strategy_mcnemar_csv(rows, args.mcnemar_llm_pairwise_out)

    print(f"Wrote summary:  {args.summary_out}")
    print(f"Wrote baseline: {args.mcnemar_vs_baseline_out}")
    print(f"Wrote pairwise: {args.mcnemar_llm_pairwise_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
