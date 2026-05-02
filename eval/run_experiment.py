"""
run_experiment.py  --  Experiment orchestrator.

Runs scenarios from scenarios.json on one or more of the three systems
(rule_based, single_llm, mas) with a configurable number of trials and
writes per-run JSON logs to results/{system}/{scenario_id}_trial{N}.json.

Typical usage:

    # plan-only smoke test (no robot, no Webots) for baselines A and B
    python3 run_experiment.py --systems rule_based single_llm --trials 1 --dry

    # full comparison run (all 3 systems, 3 trials, real robot)
    python3 run_experiment.py --systems rule_based single_llm mas --trials 3

    # only re-run one scenario on one system
    python3 run_experiment.py --systems single_llm --scenarios s01 s04 --trials 3

Flags:
    --systems       which systems to run. Choices: rule_based, single_llm, mas
    --trials        number of trials per scenario per system (default 3)
    --scenarios     subset of scenario IDs to run (default: all 20)
    --dry           plan-only mode (robot=None). Baselines work; MAS skipped.
    --results-dir   output directory (default: results/)
    --scenarios-file    scenarios JSON path (default: scenarios.json)

After a run:
    python3 aggregate_results.py          # produces master CSV + summary
"""

import argparse
import json
import os
import sys
import time
import traceback
from typing import Optional

from eval.metric_logger import RunLog


# ----------------------------------------------------------------------
# System loader -- lazy imports so a dry-run test does not require
# installing Webots / pygame / all LangChain deps.
# ----------------------------------------------------------------------

def load_system(name: str, robot, use_real_perception: bool):
    if name == "rule_based":
        from baselines.rule_based import RuleBasedSystem
        return RuleBasedSystem(robot=robot, use_real_perception=use_real_perception)
    if name == "single_llm":
        from baselines.single_llm import SingleLLMSystem
        return SingleLLMSystem(robot=robot, use_real_perception=use_real_perception)
    if name == "mas":
        # The MAS is wired inside Allinone_1.py as a LangGraph app and it
        # runs with a speech-agent entry. For fair comparison we need a
        # text-in wrapper that bypasses the SpeechAgent. That wrapper is
        # provided by mas_runner.MASRunner (to be authored by the team
        # alongside this orchestrator). Stub pattern:
        #
        #     from mas_runner import MASRunner
        #     return MASRunner(robot=robot)
        #
        # For now we raise a clear error if MAS is requested but the
        # wrapper is not available, so the baselines can be run
        # independently without blocking on MAS integration.
        try:
            from mas.runner import MASRunner  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "mas_runner.MASRunner not available. "
                "To include the MAS in the comparison, add a thin "
                "text-in / text-out wrapper at mas_runner.py that "
                "exposes .run_scenario(scenario, log). "
                f"(import error: {e})"
            )
        return MASRunner(robot=robot)
    raise ValueError(f"unknown system: {name}")


# ----------------------------------------------------------------------
# Robot loader (lazy -- dry mode skips this entirely)
# ----------------------------------------------------------------------

def load_robot(dry: bool):
    if dry:
        return None
    import robot3
    robot = robot3.Robot(
        current_position=(195, 195),
        show_rt_display=False,
        show_rt_camera_frame=False,
    )
    # give sensors a moment to initialise
    time.sleep(2.0)
    return robot


def reset_robot_for_scenario(robot, scenario: dict):
    """Reset physical + map state before each scenario run.

    The base binary map has ALL doors closed by default (they show up
    as walls). A door is OPENED on demand by the planner via
    update_binary_map(door_num, True) just before driving through it.
    So for scenario setup we just reset the map back to "all closed"
    and let each system open doors as it plans them. Doors the scenario
    marks as physically closed remain closed, which is the default.

    NOTE: closed doors from scenario.door_states must be set up in the
    Webots world itself (physical door state). The binary map just
    represents traversability from the planner's perspective.
    """
    if robot is None:
        return
    # The scenario parameter is kept for future use (teleport-to-
    # initial_position, door pre-state, etc.) -- currently the base
    # binary map reset is enough.
    _ = scenario
    try:
        robot.reset_binary_map()
    except Exception:
        pass
    try:
        robot.reset_parameters()
    except Exception:
        pass


# ----------------------------------------------------------------------
# Run one (system, scenario, trial) tuple
# ----------------------------------------------------------------------

class _TeeStdout:
    """Duplicate every write to stdout AND to a per-run log file so every
    scenario has its full trace preserved for post-mortem inspection."""

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._file = open(path, "w", buffering=1)  # line-buffered
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr

    def __enter__(self):
        sys.stdout = self
        sys.stderr = self
        return self

    def __exit__(self, *_exc):
        _ = _exc  # propagate any exception upstream; tee just releases resources
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr
        try:
            self._file.close()
        except Exception:
            pass

    def write(self, data):
        try:
            self._orig_stdout.write(data)
        except Exception:
            pass
        try:
            self._file.write(data)
        except Exception:
            pass

    def flush(self):
        try:
            self._orig_stdout.flush()
        except Exception:
            pass
        try:
            self._file.flush()
        except Exception:
            pass


def run_single(system_name: str,
               system_obj,
               scenario: dict,
               trial: int,
               results_dir: str,
               robot) -> RunLog:
    log = RunLog(
        scenario_id=scenario["id"],
        system=system_name,
        trial=trial,
    )

    reset_robot_for_scenario(robot, scenario)

    # Tee stdout/stderr into results/{system}/logs/{scenario}_trial{N}.log
    # so every [TRACE] line and every runtime warning is preserved for
    # the full 180-run batch.
    log_path = os.path.join(
        results_dir, system_name, "logs",
        f"{scenario['id']}_trial{trial}.log",
    )
    with _TeeStdout(log_path):
        try:
            system_obj.run_scenario(scenario, log)
        except Exception as e:
            if log.start_time == 0.0:
                log.start()
            log.stop(success=False,
                     failure_reason=f"exception:{type(e).__name__}:{e}",
                     graceful_failure=False)
            log.notes = (log.notes + " | " if log.notes else "") + \
                        "traceback: " + traceback.format_exc()[-500:]

    out_path = os.path.join(
        results_dir,
        system_name,
        f"{scenario['id']}_trial{trial}.json",
    )
    log.save(out_path)
    return log


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--systems", nargs="+",
                    default=["rule_based", "single_llm", "mas"],
                    choices=["rule_based", "single_llm", "mas"])
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--scenarios", nargs="*", default=None,
                    help="subset of scenario IDs; default is all")
    ap.add_argument("--dry", action="store_true",
                    help="plan-only mode (no robot, no Webots)")
    ap.add_argument("--real-perception", action="store_true",
                    help="use real VLM for door checks (requires robot)")
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--scenarios-file", default="scenarios.json")
    args = ap.parse_args()

    with open(args.scenarios_file) as f:
        cfg = json.load(f)
    all_scenarios = cfg["scenarios"]
    if args.scenarios:
        wanted = set(args.scenarios)
        scenarios = [s for s in all_scenarios if s["id"] in wanted]
        missing = wanted - {s["id"] for s in scenarios}
        if missing:
            print(f"WARNING: unknown scenario ids: {sorted(missing)}", file=sys.stderr)
    else:
        scenarios = all_scenarios

    if not scenarios:
        print("no scenarios selected, exiting", file=sys.stderr)
        sys.exit(1)

    print(f"orchestrator: running {len(scenarios)} scenarios x "
          f"{args.trials} trials on systems={args.systems} "
          f"(dry={args.dry}, real_perception={args.real_perception})")

    # load robot once, shared across all systems. In --dry mode the
    # robot is None and the MAS / baselines run in their plan-only
    # stubs (no Webots required).
    robot = load_robot(dry=args.dry)

    summary: dict[str, dict[str, int]] = {
        s: {"runs": 0, "success": 0, "fail": 0} for s in args.systems
    }

    for system_name in args.systems:
        print(f"\n=== SYSTEM: {system_name} ===")
        system_obj = load_system(system_name, robot, args.real_perception)
        for sc in scenarios:
            for trial in range(1, args.trials + 1):
                t0 = time.time()
                log = run_single(
                    system_name=system_name,
                    system_obj=system_obj,
                    scenario=sc,
                    trial=trial,
                    results_dir=args.results_dir,
                    robot=robot,
                )
                summary[system_name]["runs"] += 1
                if log.success:
                    summary[system_name]["success"] += 1
                else:
                    summary[system_name]["fail"] += 1
                dt = time.time() - t0
                tag = "OK  " if log.success else "FAIL"
                print(f"  [{system_name}][{sc['id']}][t{trial}] {tag} "
                      f"({dt:.2f}s) reason={log.failure_reason}")

    print("\n=== SUMMARY ===")
    for s, stats in summary.items():
        total = stats["runs"]
        succ = stats["success"]
        pct = (100.0 * succ / total) if total else 0.0
        print(f"  {s:<12} {succ}/{total}  ({pct:.1f}%)")
    print(f"\nResults written to: {os.path.abspath(args.results_dir)}")


if __name__ == "__main__":
    main()
