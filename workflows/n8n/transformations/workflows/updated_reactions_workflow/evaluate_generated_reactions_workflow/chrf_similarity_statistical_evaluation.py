from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Optional

import numpy as np
from scipy.stats import wilcoxon, kruskal


BASELINE_STRATEGY = "only_prompt"


def parse_float(x) -> float:
    if x is None:
        raise ValueError("Missing float value")
    s = str(x).strip()
    if s == "":
        raise ValueError("Empty float value")
    return float(s)


@dataclass(frozen=True)
class Row:
    llm: str
    strategy: str
    file_id: str  # pairing id
    score: float  # CHRF Score


def read_rows(input_csv: Path) -> List[Row]:
    """
    Expects CSV with columns: LLM, Strategy, File, Score
    """
    with input_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"LLM", "Strategy", "File", "Score"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        rows: List[Row] = []
        for r in reader:
            llm = (r.get("LLM", "") or "").strip()
            strategy = (r.get("Strategy", "") or "").strip()
            file_id = (r.get("File", "") or "").strip()
            score = parse_float(r.get("Score", ""))

            if not llm or not strategy or not file_id:
                # skip malformed row
                continue

            rows.append(Row(llm=llm, strategy=strategy, file_id=file_id, score=score))
    return rows


def write_chrf_summary_csv(rows: Iterable[Row], out_csv: Path) -> None:
    """
    1) CSV with per llm-strategy combination the average and median CHRF score.
    """
    vals: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    llms = set()
    strategies = set()

    for row in rows:
        vals[(row.strategy, row.llm)].append(row.score)
        llms.add(row.llm)
        strategies.add(row.strategy)

    llm_list = sorted(llms)
    strategy_list = sorted(strategies)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Strategy", "LLM", "N", "MeanCHRF", "MedianCHRF"])

        for strategy in strategy_list:
            for llm in llm_list:
                xs = vals.get((strategy, llm), [])
                if not xs:
                    continue
                mean = float(np.mean(xs))
                med = float(np.median(xs))
                w.writerow([strategy, llm, len(xs), f"{mean:.12g}", f"{med:.12g}"])


def _wilcoxon_p_two_sided(x: np.ndarray, y: np.ndarray) -> str:
    """
    Helper for paired Wilcoxon two-sided p-value.
    Uses Pratt to handle zeros
    Returns string p-value formatted or "1" if all diffs are zero.
    """
    diffs = x - y
    if np.allclose(diffs, 0.0):
        return "1"
    try:
        res = wilcoxon(x, y, alternative="two-sided", zero_method="pratt")
    except TypeError:
        res = wilcoxon(x, y, alternative="two-sided")
    return f"{float(res.pvalue):.12g}"


def write_wilcoxon_vs_baseline_csv(
    rows: Iterable[Row],
    out_csv: Path,
    baseline_strategy: str = BASELINE_STRATEGY,
) -> None:
    """
    2) CSV comparing each strategy vs baseline within one LLM using paired Wilcoxon signed-rank test.

    Pairing:
      - fixed LLM
      - paired by file_id (task)
    """
    # Map: llm -> strategy -> file_id -> score
    data: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    llms = set()
    strategies = set()

    for row in rows:
        llms.add(row.llm)
        strategies.add(row.strategy)
        data[row.llm][row.strategy][row.file_id] = row.score

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

                base_vals = np.array([base_map[fid] for fid in common], dtype=float)
                strat_vals = np.array([strat_map[fid] for fid in common], dtype=float)

                p_str = _wilcoxon_p_two_sided(strat_vals, base_vals)

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
       using paired Wilcoxon signed-rank test on CHRF score.

    Pairing:
      - fixed strategy
      - paired by file_id (task)
    """
    # Map: strategy -> llm -> file_id -> score
    data: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    strategies = set()
    llms = set()

    for row in rows:
        strategies.add(row.strategy)
        llms.add(row.llm)
        data[row.strategy][row.llm][row.file_id] = row.score

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

                    v1 = np.array([m1[fid] for fid in common], dtype=float)
                    v2 = np.array([m2[fid] for fid in common], dtype=float)

                    p_str = _wilcoxon_p_two_sided(v2, v1)

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


def write_kruskal_within_strategy_csv(
    rows: Iterable[Row],
    out_csv: Path,
) -> None:
    """
    For each strategy, compare CHRF score distributions across LLMs using Kruskal–Wallis.

    H0: all LLMs have the same distribution (same median ranks).
    Requires >=2 LLM groups with at least 1 observation each.
    """
    # Map: strategy -> llm -> list[score]
    data: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    strategies = set()
    llms = set()
    for row in rows:
        strategies.add(row.strategy)
        llms.add(row.llm)
        data[row.strategy][row.llm].append(row.score)

    strategy_list = sorted(strategies)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Strategy", "NumLLMs", "TotalN", "LLMsIncluded", "KruskalPValue"])

        for strategy in strategy_list:
            # only include llms that actually have data for this strategy
            groups: List[Tuple[str, List[float]]] = []
            for llm, xs in data[strategy].items():
                if xs:
                    groups.append((llm, xs))

            if len(groups) < 2:
                # Not enough groups to run Kruskal–Wallis
                llms_included = ",".join(sorted([g[0] for g in groups]))
                total_n = sum(len(g[1]) for g in groups)
                w.writerow([strategy, len(groups), total_n, llms_included, ""])
                continue

            # Run Kruskal–Wallis
            # scipy.stats.kruskal expects each group as a separate argument
            arrays = [np.array(xs, dtype=float) for _, xs in groups]
            try:
                res = kruskal(*arrays)
                p_str = f"{float(res.pvalue):.12g}"
            except Exception:
                p_str = ""

            llms_included = ",".join(sorted([g[0] for g in groups]))
            total_n = sum(len(g[1]) for g in groups)

            w.writerow([strategy, len(groups), total_n, llms_included, p_str])


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="CHRF summaries + paired Wilcoxon tests vs baseline and pairwise across LLMs."
    )
    ap.add_argument("input_csv", type=Path, help="Input CSV (must include LLM, Strategy, File, Score)")

    ap.add_argument(
        "--chrf-summary-out",
        type=Path,
        default=Path("chrf_summary.csv"),
        help="Output CSV: per (llm,strategy) mean+median CHRF",
    )

    ap.add_argument(
        "--wilcoxon-vs-baseline-out",
        type=Path,
        default=Path("chrf_wilcoxon_vs_baseline_within_llm.csv"),
        help="Output CSV: Wilcoxon strategy vs baseline within each LLM (CHRF)",
    )

    ap.add_argument(
        "--wilcoxon-llm-pairwise-out",
        type=Path,
        default=Path("chrf_wilcoxon_llm_pairwise_within_strategy.csv"),
        help="Output CSV: Wilcoxon pairwise LLM comparisons within each strategy (CHRF)",
    )

    ap.add_argument(
        "--baseline",
        type=str,
        default=BASELINE_STRATEGY,
        help='Baseline strategy name (default: "only_prompt")',
    )

    ap.add_argument(
        "--kruskal-within-strategy-out",
        type=Path,
        default=Path("chrf_kruskal_within_strategy.csv"),
        help="Output CSV: Kruskal–Wallis p-values across LLMs within each strategy (CHRF)",
    )

    args = ap.parse_args(argv)

    rows = read_rows(args.input_csv)

    write_chrf_summary_csv(rows, args.chrf_summary_out)
    write_wilcoxon_vs_baseline_csv(rows, args.wilcoxon_vs_baseline_out, baseline_strategy=args.baseline)
    write_llm_pairwise_within_strategy_wilcoxon_csv(rows, args.wilcoxon_llm_pairwise_out)
    write_kruskal_within_strategy_csv(rows, args.kruskal_within_strategy_out)

    print(f"Wrote summary:  {args.chrf_summary_out}")
    print(f"Wrote baseline: {args.wilcoxon_vs_baseline_out}")
    print(f"Wrote pairwise: {args.wilcoxon_llm_pairwise_out}")
    print(f"Wrote kruskal:  {args.kruskal_within_strategy_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
