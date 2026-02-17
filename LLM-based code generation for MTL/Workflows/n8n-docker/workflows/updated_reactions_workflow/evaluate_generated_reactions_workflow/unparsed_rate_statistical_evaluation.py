from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Optional
from statsmodels.stats.contingency_tables import mcnemar


BASELINE_STRATEGY = "only_prompt"


def parse_bool(x):
    s = (x or "").strip().lower()
    if s in {"true", "1"}:
        return True
    if s in {"false", "0"}:
        return False
    raise ValueError(f"Cannot parse boolean from: {x!r}")

def derive_llm_and_strategy(reaction_file):
    """
    Returns (llm, strategy, task_id)

    llm      = segment before first '/'
    strategy = segment between first and second '/'
    task_id  = remainder after second '/' (used for McNemar pairing)
    """
    parts = (reaction_file or "").split("/")
    if len(parts) < 3:
        raise ValueError(
            f"CSV report must contain at least two '/' separators: {reaction_file!r}"
        )
    llm = parts[0]
    strategy = parts[1]
    task_id = parts[2]
    return llm, strategy, task_id

@dataclass(frozen=True)
class Row:
    reaction_file: str
    llm: str
    strategy: str
    parsed: bool
    task_id: str

def read_rows(input_csv: Path) -> List[Row]:
    with input_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"ReactionFile", "Parsed"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        rows: List[Row] = []
        for r in reader:
            rf = r.get("ReactionFile", "") or ""
            parsed = parse_bool(r.get("Parsed", ""))
            llm, strategy, task_id = derive_llm_and_strategy(rf)
            rows.append(Row(reaction_file=rf, llm=llm, strategy=strategy, parsed=parsed, task_id=task_id))
    return rows


def write_pivot_csv(rows: Iterable[Row], out_csv: Path) -> None:
    # Aggregate parsed rates per (strategy, llm)
    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    trues: Dict[Tuple[str, str], int] = defaultdict(int)
    llms = set()
    strategies = set()

    for row in rows:
        key = (row.strategy, row.llm)
        counts[key] += 1
        trues[key] += int(not row.parsed)
        llms.add(row.llm)
        strategies.add(row.strategy)

    llm_list = sorted(llms)
    strategy_list = sorted(strategies)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Strategy (UnparsedRate)"] + llm_list)
        for s in strategy_list:
            line = [s]
            for llm in llm_list:
                key = (s, llm)
                if counts.get(key, 0) == 0:
                    line.append("")  # no data
                else:
                    rate = trues[key] / counts[key]
                    line.append(f"{rate:.10f}".rstrip("0").rstrip(".") if rate not in (0.0, 1.0) else str(rate))
            writer.writerow(line)


def write_mcnemar_csv(
    rows: Iterable[Row],
    out_csv: Path,
    baseline_strategy: str = BASELINE_STRATEGY,
) -> None:
    """
    For each llm, compare each strategy vs baseline using paired task_id within that llm,
    using statsmodels' exact McNemar test.
    """
    # Map: llm -> strategy -> task_id -> parsed
    data: Dict[str, Dict[str, Dict[str, bool]]] = defaultdict(lambda: defaultdict(dict))

    llms = set()
    strategies = set()
    for row in rows:
        llms.add(row.llm)
        strategies.add(row.strategy)
        data[row.llm][row.strategy][row.task_id] = row.parsed

    llm_list = sorted(llms)
    strategy_list = sorted(strategies)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
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
                # No baseline for this llm => cannot test
                for strat in strategy_list:
                    if strat == baseline_strategy:
                        continue
                    writer.writerow([llm, strat, baseline_strategy, 0, 0, 0, 0, 0, ""])
                continue

            for strat in strategy_list:
                if strat == baseline_strategy:
                    continue

                strat_map = data[llm].get(strat, {})
                if not strat_map:
                    writer.writerow([llm, strat, baseline_strategy, 0, 0, 0, 0, 0, ""])
                    continue

                common = sorted(set(base_map.keys()) & set(strat_map.keys()))
                a = b = c = d = 0
                for tid in common:
                    base_parsed = base_map[tid]
                    strat_parsed = strat_map[tid]

                    if (not base_parsed) and (not strat_parsed):
                        a += 1
                    elif base_parsed and (not strat_parsed):
                        b += 1
                    elif (not base_parsed) and strat_parsed:
                        c += 1
                    else:
                        d += 1

                # Table layout:
                #              Strategy
                #            False   True
                # Baseline
                #   False      a      c
                #   True       b      d
                table = [[a, c], [b, d]]

                # Exact McNemar (binomial), two-sided p-value
                try:
                    res = mcnemar(table, exact=True)
                    p = res.pvalue
                    p_str = f"{p:.12g}"
                except Exception:
                    p_str = ""

                writer.writerow([llm, strat, baseline_strategy, len(common), a, b, c, d, p_str])


def write_llm_pairwise_within_strategy_csv(
    rows: Iterable[Row],
    out_csv: Path,
) -> None:
    """
    For each strategy, compare LLMs pairwise on UNPARSED event (not parsed),
    using exact McNemar on paired task_id.

    Output columns:
      1) strategy
      2) llm1
      3) unparsed-rate for (llm1,strategy)
      4) llm2
      5) unparsed-rate for (llm2,strategy)
      6) significance (exact McNemar p-value)

    Notes:
    - "unparsed rate" is computed over the common task_ids between llm1 and llm2 for that strategy,
      so the rates are directly comparable to the McNemar test (paired sample).
    """
    # Map: strategy -> llm -> task_id -> parsed
    data: Dict[str, Dict[str, Dict[str, bool]]] = defaultdict(lambda: defaultdict(dict))

    strategies = set()
    llms = set()
    for row in rows:
        strategies.add(row.strategy)
        llms.add(row.llm)
        data[row.strategy][row.llm][row.task_id] = row.parsed  # parsed=True/False

    strategy_list = sorted(strategies)
    llm_list = sorted(llms)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "strategy",
                "llm1",
                "unparsed_rate_llm1",
                "llm2",
                "unparsed_rate_llm2",
                "significance_p_exact_mcnemar",
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
                        # No paired sample => cannot compute
                        writer.writerow([strategy, llm1, "", llm2, "", ""])
                        continue

                    # Compute unparsed rates on the paired sample
                    unparsed_1 = 0
                    unparsed_2 = 0

                    # Build McNemar 2x2 on UNPARSED event
                    #              LLM2
                    #            False   True
                    # LLM1
                    # False       a       c
                    # True        b       d
                    # Here True means "unparsed"
                    a = b = c = d = 0

                    for tid in common:
                        llm1_unparsed = not m1[tid]
                        llm2_unparsed = not m2[tid]

                        unparsed_1 += int(llm1_unparsed)
                        unparsed_2 += int(llm2_unparsed)

                        if (not llm1_unparsed) and (not llm2_unparsed):
                            a += 1
                        elif llm1_unparsed and (not llm2_unparsed):
                            b += 1
                        elif (not llm1_unparsed) and llm2_unparsed:
                            c += 1
                        else:
                            d += 1

                    rate1 = unparsed_1 / len(common)
                    rate2 = unparsed_2 / len(common)

                    table = [[a, c], [b, d]]

                    if (b + c) == 0:
                        p_str = "1"
                    else:
                        try:
                            res = mcnemar(table, exact=True)
                            p_str = f"{res.pvalue:.12g}"
                        except Exception:
                            p_str = ""

                    writer.writerow(
                        [
                            strategy,
                            llm1,
                            f"{rate1:.10f}".rstrip("0").rstrip(".") if rate1 not in (0.0, 1.0) else str(rate1),
                            llm2,
                            f"{rate2:.10f}".rstrip("0").rstrip(".") if rate2 not in (0.0, 1.0) else str(rate2),
                            p_str,
                        ]
                    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Parsed-rate pivot + exact McNemar tests vs baseline strategy.")
    ap.add_argument("input_csv", type=Path, help="Input CSV file path")
    ap.add_argument("--pivot-out", type=Path, default=Path("parsed_rate_pivot.csv"),
                    help="Output CSV path for parsed-rate pivot (rows=strategy, cols=llm)")
    ap.add_argument("--mcnemar-out", type=Path, default=Path("mcnemar_exact.csv"),
                    help="Output CSV path for exact McNemar results")
    ap.add_argument("--baseline", type=str, default=BASELINE_STRATEGY,
                    help='Baseline strategy name (default: "only_prompt")')
    ap.add_argument(
        "--mcnemar-llm-pairwise-out",
        type=Path,
        default=Path("mcnemar_exact_llm_pairwise_within_strategy.csv"),
        help="Output CSV path for exact McNemar results comparing LLMs pairwise within each strategy",
    )

    args = ap.parse_args(argv)

    rows = read_rows(args.input_csv)
    write_pivot_csv(rows, args.pivot_out)
    write_mcnemar_csv(rows, args.mcnemar_out, baseline_strategy=args.baseline)
    write_llm_pairwise_within_strategy_csv(rows, args.mcnemar_llm_pairwise_out)
    print(f"Wrote LLM pairwise McNemar: {args.mcnemar_llm_pairwise_out}")
    print(f"Wrote pivot:   {args.pivot_out}")
    print(f"Wrote McNemar: {args.mcnemar_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())