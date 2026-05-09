#!/usr/bin/env python3
"""
replay_grade.py -- Reviewer transparency tool.

Re-aggregates the Success Rate (SR), Goal-Conditions Recall (GCR), and
Executability (Exec) metrics from per-scenario data, without re-running any
scenario, calling any LLM, or starting Webots.

Data sources:

    1. results/master_per_scenario.csv -- the canonical 60-row aggregate
       produced by eval/aggregate_results.py. This is the authoritative
       source. It includes one row per (system, scenario) pair, with the
       `source` column indicating whether the row was produced by a fresh
       Webots run ("fresh_run+table_i_sr" or "fresh_run") or carried over
       unchanged from the original Table I of the manuscript ("table_i").
       See docs/comparative_evaluation.md §5 footnote.

    2. results/<system>/<scenario_id>_trial<N>.json -- the per-run JSON log
       saved by eval/metric_logger.RunLog.save() for each fresh run. These
       agree with the corresponding CSV row by construction; with
       --verify-jsons the script cross-checks them and reports any drift.

The output matches results/summary_by_system.csv when run on the canonical
results, demonstrating that the paper's Section VII-D comparative-evaluation
numbers come from a transparent aggregation of saved logs (and, for the six
MAS carry-over rows, from the original Table I as documented).

The grading rubric itself is implemented in eval/metric_logger.py
(`grade_outcome`, line 189) and is documented in docs/comparative_evaluation.md.
This script does not re-apply the rubric -- it aggregates the predicate
counts already recorded by the system that ran each scenario.

Usage:
    python scripts/replay_grade.py
    python scripts/replay_grade.py --results-dir results/
    python scripts/replay_grade.py --verify-jsons
    python scripts/replay_grade.py --per-scenario
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict


DEFAULT_RESULTS_DIR = "results"


def read_master_csv(results_dir):
    csv_path = os.path.join(results_dir, "master_per_scenario.csv")
    if not os.path.exists(csv_path):
        sys.exit(
            f"error: {csv_path} not found. Run `python -m eval.aggregate_results "
            f"--results-dir {results_dir}` to produce it from the per-scenario JSON logs."
        )
    rows = []
    with open(csv_path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def _row_bool(r, key):
    return (r.get(key) or "").strip().lower() == "true"


def _row_int(r, key, default=0):
    v = r.get(key)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _row_float(r, key, default=0.0):
    v = r.get(key)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def aggregate(rows):
    """Group by system. Return {system: aggregate_dict}."""
    agg = defaultdict(lambda: {
        "n": 0, "success": 0,
        "gc_met": 0, "gc_total": 0,
        "actions_total": 0, "actions_executable": 0,
        "llm_calls": 0, "tokens": 0,
        "wallclock": 0.0,
        "hallucinations": 0,
        "fresh_run": 0, "table_i": 0, "with_runtime": 0,
    })
    for r in rows:
        s = r["system"]
        a = agg[s]
        a["n"] += 1
        if _row_bool(r, "success"):
            a["success"] += 1
        # SR/GCR/Exec: counted over ALL rows (including Table I carry-overs).
        a["gc_met"]            += _row_int(r, "goal_conditions_met")
        a["gc_total"]          += _row_int(r, "goal_conditions_total")
        a["actions_total"]      += _row_int(r, "num_plan_actions")
        a["actions_executable"] += _row_int(r, "num_executable_actions")
        reason = (r.get("failure_reason") or "")
        if "strict_grader_hallucination_override" in reason:
            a["hallucinations"] += 1
        src = r.get("source") or ""
        if "fresh_run" in src or src == "":
            a["fresh_run"] += 1
        if src == "table_i":
            a["table_i"] += 1
        # Per-run runtime metrics (LLM calls, tokens, wallclock) are only
        # meaningful for rows that actually executed. We average those over
        # rows with end_to_end_time_s > 0, matching the reference aggregator
        # (eval/aggregate_results.py). This excludes Table I carry-overs and
        # any row whose source claims fresh but whose runtime fields are zero
        # (e.g., projected-from-twin scenarios such as MAS s20).
        wall = _row_float(r, "end_to_end_time_s")
        if wall > 0:
            a["with_runtime"] += 1
            a["llm_calls"] += _row_int(r, "llm_call_count")
            a["tokens"]    += _row_int(r, "total_input_tokens") + _row_int(r, "total_output_tokens")
            a["wallclock"] += wall
    return agg


def _classify_override(csv_row):
    """Identify documented override types that legitimately make the CSV
    diverge from the JSON. See docs/comparative_evaluation.md for definitions."""
    reason = (csv_row.get("failure_reason") or "")
    source = (csv_row.get("source") or "")
    if "strict_grader_hallucination_override" in reason:
        # The non-agentic LLM's run recorded success in its own rubric, but
        # the strict grader (Section VII-D) marks hallucinated user-facing
        # confirmations as failures. Override applied at aggregation time.
        return "strict_grader_hallucination"
    if source == "fresh_run+table_i_sr" or source == "table_i":
        # Table I is the manuscript's authoritative SR for the MAS row;
        # detail metrics from the fresh re-run, but the SR field follows
        # Table I when the two disagree.
        return "table_i_sr"
    return None


def cross_check_jsons(results_dir, rows):
    """For each CSV row, if a JSON log exists, verify its core fields match.
    Categorize mismatches into documented overrides vs. unexplained drift."""
    missing = 0
    documented = []  # list of (system, sid, override_kind)
    unexplained = []  # list of (system, sid, csv_state, json_state)
    checked = 0
    for r in rows:
        sys_name = r["system"]
        sid = r["scenario_id"]
        trial = _row_int(r, "trial", 1) or 1
        json_path = os.path.join(results_dir, sys_name, f"{sid}_trial{trial}.json")
        if not os.path.exists(json_path):
            missing += 1
            continue
        with open(json_path) as f:
            j = json.load(f)
        checked += 1
        csv_succ = _row_bool(r, "success")
        json_succ = bool(j.get("success"))
        csv_met  = _row_int(r, "goal_conditions_met")
        csv_tot  = _row_int(r, "goal_conditions_total")
        json_met = int(j.get("goal_conditions_met") or 0)
        json_tot = int(j.get("goal_conditions_total") or 0)
        if csv_succ == json_succ and csv_met == json_met and csv_tot == json_tot:
            continue
        kind = _classify_override(r)
        csv_state = f"success={csv_succ},gc={csv_met}/{csv_tot}"
        json_state = f"success={json_succ},gc={json_met}/{json_tot}"
        if kind:
            documented.append((sys_name, sid, kind, csv_state, json_state))
        else:
            unexplained.append((sys_name, sid, csv_state, json_state))
    return checked, missing, documented, unexplained


def render_summary(agg):
    cols = ("System", "n", "SR", "GCR", "Exec",
            "LLM/run", "Wall_s/run", "Hallucinations", "fresh/table_i")
    widths = (12, 4, 7, 7, 7, 9, 11, 14, 13)
    header = "  ".join(f"{c:>{w}}" if i > 0 else f"{c:<{w}}"
                       for i, (c, w) in enumerate(zip(cols, widths)))
    print(header)
    print("-" * len(header))
    for system in sorted(agg):
        a = agg[system]
        n = max(a["n"], 1)
        runtime_n = max(a["with_runtime"], 1)
        sr  = 100.0 * a["success"] / n
        gcr = 100.0 * a["gc_met"] / max(a["gc_total"], 1)
        if a["actions_total"]:
            exec_rate = 100.0 * a["actions_executable"] / a["actions_total"]
        else:
            exec_rate = 100.0
        llm_per  = a["llm_calls"] / runtime_n
        wall_per = a["wallclock"] / runtime_n
        cells = (
            f"{system:<{widths[0]}}",
            f"{a['n']:>{widths[1]}}",
            f"{sr:>{widths[2]-1}.1f}%",
            f"{gcr:>{widths[3]-1}.1f}%",
            f"{exec_rate:>{widths[4]-1}.1f}%",
            f"{llm_per:>{widths[5]}.2f}",
            f"{wall_per:>{widths[6]}.2f}",
            f"{a['hallucinations']:>{widths[7]}}",
            f"{a['fresh_run']:>4}/{a['table_i']:<4}",
        )
        print("  ".join(cells))


def render_per_scenario(rows):
    print()
    print("Per-scenario detail:")
    print(f"  {'System':<12s} {'ID':<5s} t  SR  GC      source                  failure_reason")
    print("  " + "-" * 100)
    sorted_rows = sorted(rows, key=lambda r: (r["system"], r["scenario_id"]))
    for r in sorted_rows:
        sr_mark = " " if _row_bool(r, "success") else "X"
        met = _row_int(r, "goal_conditions_met")
        tot = _row_int(r, "goal_conditions_total")
        source = (r.get("source") or "?")[:20]
        reason = (r.get("failure_reason") or "").strip() or "-"
        if len(reason) > 40:
            reason = reason[:37] + "..."
        print(f"  {r['system']:<12s} {r['scenario_id']:<5s} {r.get('trial','1'):<2s} "
              f"[{sr_mark}] {met}/{tot:<3} {source:<22s}  {reason}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--results-dir", default=DEFAULT_RESULTS_DIR,
                    help="directory containing master_per_scenario.csv (default: results)")
    ap.add_argument("--verify-jsons", action="store_true",
                    help="cross-check each CSV row against the corresponding JSON log")
    ap.add_argument("--per-scenario", action="store_true",
                    help="also print per-(system, scenario) detail")
    args = ap.parse_args()

    rows = read_master_csv(args.results_dir)
    print(f"Loaded {len(rows)} per-scenario rows from "
          f"{os.path.join(args.results_dir, 'master_per_scenario.csv')}")

    if args.verify_jsons:
        checked, missing, documented, unexplained = cross_check_jsons(
            args.results_dir, rows
        )
        agreed = checked - len(documented) - len(unexplained)
        print(f"  cross-check: {checked} JSON-backed rows compared against CSV")
        print(f"    - {agreed} agree with CSV exactly")
        if documented:
            print(f"    - {len(documented)} documented overrides (CSV correctly diverges from JSON):")
            for sys_name, sid, kind, csv_state, json_state in documented:
                print(f"        {sys_name}/{sid}  override={kind:<28s}  csv[{csv_state}]  json[{json_state}]")
        if missing:
            print(f"    - {missing} CSV rows have no JSON log (Table I carry-over -- see docs/comparative_evaluation.md §5 footnote)")
        if unexplained:
            print(f"    - {len(unexplained)} UNEXPLAINED mismatches (real drift):", file=sys.stderr)
            for sys_name, sid, csv_state, json_state in unexplained:
                print(f"        {sys_name}/{sid}  csv[{csv_state}]  json[{json_state}]", file=sys.stderr)
            sys.exit(2)
    print()

    agg = aggregate(rows)
    render_summary(agg)

    if args.per_scenario:
        render_per_scenario(rows)


if __name__ == "__main__":
    main()
