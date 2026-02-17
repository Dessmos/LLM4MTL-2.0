from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, List, Tuple, Optional

import numpy as np
from scipy.stats import wilcoxon


BASELINE_STRATEGY = "only_prompt"


def derive_llm_and_strategy(reaction_file: str) -> Tuple[str, str, str]:
    """
    Returns (llm, strategy, task_id)

    llm      = segment before first '/'
    strategy = segment between first and second '/'
    task_id  = remainder after second '/' (used for pairing)
    """
    parts = (reaction_file or "").split("/")
    if len(parts) < 3:
        raise ValueError(f"CSV report must contain at least two '/' separators: {reaction_file!r}")
    llm = parts[0]
    strategy = parts[1]
    task_id = parts[2]
    return llm, strategy, task_id


def parse_float(x) -> float:
    if x is None:
        raise ValueError("Missing float value")
    s = str(x).strip()
    if s == "":
        raise ValueError("Empty float value")
    return float(s)


@dataclass(frozen=True)
class Row:
    reaction_file: str
    llm: str
    strategy: str
    task_id: str
    errors_per_loc: float


def read_rows(input_csv: Path) -> List[Row]:
    with input_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"ReactionFile", "ErrorsPerLineOfCode"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        rows: List[Row] = []
        for r in reader:
            rf = r.get("ReactionFile", "") or ""
            llm, strategy, task_id = derive_llm_and_strategy(rf)

            eloc = parse_float(r.get("ErrorsPerLineOfCode", ""))

            rows.append(Row(reaction_file=rf, llm=llm, strategy=strategy, task_id=task_id, errors_per_loc=eloc))
    return rows


def write_eloc_summary_csv(rows: Iterable[Row], out_csv: Path) -> None:
    """
    1) CSV with per llm-strategy combination the average and median ErrorsPerLineOfCode.
    """
    vals: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    llms = set()
    strategies = set()

    for row in rows:
        vals[(row.strategy, row.llm)].append(row.errors_per_loc)
        llms.add(row.llm)
        strategies.add(row.strategy)

    llm_list = sorted(llms)
    strategy_list = sorted(strategies)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Strategy", "LLM", "N", "MeanErrorsPerLOC", "MedianErrorsPerLOC"])

        for strategy in strategy_list:
            for llm in llm_list:
                xs = vals.get((strategy, llm), [])
                if not xs:
                    continue
                mean = float(np.mean(xs))
                med = float(np.median(xs))
                w.writerow([strategy, llm, len(xs), f"{mean:.12g}", f"{med:.12g}"])


def write_wilcoxon_vs_baseline_csv(
    rows: Iterable[Row],
    out_csv: Path,
    baseline_strategy: str = BASELINE_STRATEGY,
) -> None:
    """
    2) CSV comparing each strategy vs baseline within one LLM using paired Wilcoxon signed-rank test.

    Pairing:
      - fixed LLM
      - paired by task_id
    """
    # Map: llm -> strategy -> task_id -> errors_per_loc
    data: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    llms = set()
    strategies = set()

    for row in rows:
        llms.add(row.llm)
        strategies.add(row.strategy)
        data[row.llm][row.strategy][row.task_id] = row.errors_per_loc

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
                "MeanBaseline",
                "MeanStrategy",
                "MedianBaseline",
                "MedianStrategy",
                "WilcoxonP_TwoSided",
            ]
        )

        for llm in llm_list:
            base_map = data[llm].get(baseline_strategy, {})
            if not base_map:
                # No baseline for this llm
                for strat in strategy_list:
                    if strat == baseline_strategy:
                        continue
                    w.writerow([llm, strat, baseline_strategy, 0, "", "", "", "", ""])
                continue

            for strat in strategy_list:
                if strat == baseline_strategy:
                    continue
                strat_map = data[llm].get(strat, {})
                if not strat_map:
                    w.writerow([llm, strat, baseline_strategy, 0, "", "", "", "", ""])
                    continue

                common = sorted(set(base_map.keys()) & set(strat_map.keys()))
                if not common:
                    w.writerow([llm, strat, baseline_strategy, 0, "", "", "", "", ""])
                    continue

                base_vals = np.array([base_map[tid] for tid in common], dtype=float)
                strat_vals = np.array([strat_map[tid] for tid in common], dtype=float)

                diffs = strat_vals - base_vals
                if np.allclose(diffs, 0.0):
                    p_str = "1"
                else:
                    try:
                        res = wilcoxon(strat_vals, base_vals, alternative="two-sided", zero_method="pratt")
                    except TypeError:
                        res = wilcoxon(strat_vals, base_vals, alternative="two-sided")
                    p_str = f"{float(res.pvalue):.12g}"

                w.writerow(
                    [
                        llm,
                        strat,
                        baseline_strategy,
                        len(common),
                        f"{float(np.mean(base_vals)):.12g}",
                        f"{float(np.mean(strat_vals)):.12g}",
                        f"{float(np.median(base_vals)):.12g}",
                        f"{float(np.median(strat_vals)):.12g}",
                        p_str,
                    ]
                )


def write_llm_pairwise_within_strategy_wilcoxon_csv(
    rows: Iterable[Row],
    out_csv: Path,
) -> None:
    """
    3) CSV comparing LLMs pairwise within a fixed strategy (including only_prompt),
       using paired Wilcoxon signed-rank test on ErrorsPerLineOfCode.

    Pairing:
      - fixed strategy
      - paired by task_id
    """
    # Map: strategy -> llm -> task_id -> errors_per_loc
    data: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    strategies = set()
    llms = set()

    for row in rows:
        strategies.add(row.strategy)
        llms.add(row.llm)
        data[row.strategy][row.llm][row.task_id] = row.errors_per_loc

    strategy_list = sorted(strategies)
    llm_list = sorted(llms)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "Strategy",
                "LLM1",
                "LLM2",
                "PairedN",
                "MeanLLM1",
                "MeanLLM2",
                "MedianLLM1",
                "MedianLLM2",
                "WilcoxonP_TwoSided",
            ]
        )

        for strategy in strategy_list:
            llms_here = sorted([llm for llm in llm_list if data[strategy].get(llm)])
            if len(llms_here) < 2:
                continue

            for i in range(len(llms_here)):
                for j in range(i + 1, len(llms_here)):
                    llm1 = llms_here[i]
                    llm2 = llms_here[j]

                    m1 = data[strategy][llm1]
                    m2 = data[strategy][llm2]

                    common = sorted(set(m1.keys()) & set(m2.keys()))
                    if not common:
                        w.writerow([strategy, llm1, llm2, 0, "", "", "", "", ""])
                        continue

                    v1 = np.array([m1[tid] for tid in common], dtype=float)
                    v2 = np.array([m2[tid] for tid in common], dtype=float)

                    diffs = v2 - v1
                    if np.allclose(diffs, 0.0):
                        p_str = "1"
                    else:
                        try:
                            res = wilcoxon(v2, v1, alternative="two-sided", zero_method="pratt")
                        except TypeError:
                            res = wilcoxon(v2, v1, alternative="two-sided")
                        p_str = f"{float(res.pvalue):.12g}"

                    w.writerow(
                        [
                            strategy,
                            llm1,
                            llm2,
                            len(common),
                            f"{float(np.mean(v1)):.12g}",
                            f"{float(np.mean(v2)):.12g}",
                            f"{float(np.median(v1)):.12g}",
                            f"{float(np.median(v2)):.12g}",
                            p_str,
                        ]
                    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Errors-per-LOC summaries + paired Wilcoxon tests vs baseline and pairwise across LLMs."
    )
    ap.add_argument("input_csv", type=Path, help="Input CSV (must include ReactionFile, ErrorsPerLineOfCode)")

    ap.add_argument(
        "--eloc-summary-out",
        type=Path,
        default=Path("errors_per_loc_summary.csv"),
        help="Output CSV: per (llm,strategy) mean+median ErrorsPerLineOfCode",
    )

    ap.add_argument(
        "--wilcoxon-vs-baseline-out",
        type=Path,
        default=Path("wilcoxon_vs_baseline_within_llm.csv"),
        help="Output CSV: Wilcoxon strategy vs baseline within each LLM",
    )

    ap.add_argument(
        "--wilcoxon-llm-pairwise-out",
        type=Path,
        default=Path("wilcoxon_llm_pairwise_within_strategy.csv"),
        help="Output CSV: Wilcoxon pairwise LLM comparisons within each strategy",
    )

    ap.add_argument(
        "--baseline",
        type=str,
        default=BASELINE_STRATEGY,
        help='Baseline strategy name (default: "only_prompt")',
    )

    args = ap.parse_args(argv)

    rows = read_rows(args.input_csv)

    write_eloc_summary_csv(rows, args.eloc_summary_out)
    write_wilcoxon_vs_baseline_csv(rows, args.wilcoxon_vs_baseline_out, baseline_strategy=args.baseline)
    write_llm_pairwise_within_strategy_wilcoxon_csv(rows, args.wilcoxon_llm_pairwise_out)

    print(f"Wrote summary:  {args.eloc_summary_out}")
    print(f"Wrote baseline: {args.wilcoxon_vs_baseline_out}")
    print(f"Wrote pairwise: {args.wilcoxon_llm_pairwise_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
