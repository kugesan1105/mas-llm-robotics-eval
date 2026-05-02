# mas-llm-robotics-eval

Reproduction package for **"Enabling Robotic Cognition: A Hierarchical
Multi-Agentic System for LLM-Driven Autonomous Problem-Solving in Robotics"**
(IEEE Access, manuscript ID **Access-2026-09207**).

---

## Comparative analysis

Three systems evaluated on the same 20-scenario Webots benchmark with
identical robot, RRT motion planner, GPT-4o backbone (`gpt-4o-2024-08-06`,
T = 0), and scenario-supplied door states. Outputs are graded under a strict
rubric — a scenario fails if the system's final user-facing message is
inconsistent with ground-truth state, regardless of whether the underlying
plan executed.

| System | SR | GCR | Exec | Hallucinated retrieval/grounding confirmations |
|---|---:|---:|---:|---:|
| **Baseline A — Rule-Based replanner** (keyword + Dijkstra + FSM, no LLM) | 65.0 % | 76.7 % | 100 % | 0 |
| **Baseline B — Non-Agentic LLM planner** (one GPT-4o call, ProgPrompt-style) | 70.0 % | 80.0 % | 100 % | **5** |
| **Hierarchical MAS (proposed)** | **90.0 %** | **83.3 %** | **100 %** | **0** |

The headline is the **hallucination column**, not the SR column. The
non-agentic LLM baseline emits five user-facing confirmations that
contradict ground truth ("I have brought the hammer" when no hammer
exists, "the chair is not in R1" when chairs are present, etc.); the
proposed MAS emits zero. The two MAS failures (s02, s08 in
[`scenarios/scenarios.json`](scenarios/scenarios.json)) are
perception/execution-layer issues, not generative reasoning errors.

The architectural difference responsible for this gap is **hierarchical
error escalation**: when a perception agent (e.g., `DoorChecker`) reports a
state inconsistent with the current plan, the failure is propagated to a
strategic agent (`NavigationsupervisorMain`) with the full mission context,
which re-invokes `WaypointGenerator` under the updated environmental
constraint. Baseline B re-invokes GPT-4o open-loop with no preserved
context; SayCan, Text2Motion, and ProgPrompt each handle replanning
differently and are discussed in
[`docs/replanning_landscape.md`](docs/replanning_landscape.md).

For the per-scenario predicate-level grading that produces the SR / GCR /
Exec columns, see [`docs/goal_conditions.md`](docs/goal_conditions.md). For
the agent-by-agent code map, see
[`docs/architecture.md`](docs/architecture.md).

---

## Try it — verify the numbers in 5 seconds

No Webots, no API key, no LLM calls — re-aggregates the canonical
per-scenario logs in [`results/`](results/) and reports SR / GCR / Exec /
hallucinations. Exits non-zero if any saved log disagrees with the
canonical aggregate.

```bash
git clone https://github.com/kugesan1105/mas-llm-robotics-eval
cd mas-llm-robotics-eval
python scripts/replay_grade.py --verify-jsons
```

Expected output (truncated):

```
Loaded 60 per-scenario rows from results/master_per_scenario.csv
  cross-check: 54 JSON-backed rows compared against CSV
    - 44 agree with CSV exactly
    - 10 documented overrides (CSV correctly diverges from JSON):
        single_llm/s01  override=strict_grader_hallucination   ...
        ...
    - 6 CSV rows have no JSON log (Table I carry-over -- see docs/goal_conditions.md §3.3)

System          n     SR    GCR    Exec   LLM/run  Wall_s/run  Hallucinations  fresh/table_i
mas            20  90.0%  83.3%  100.0%    35.38      180.13               0    14/6
rule_based     20  65.0%  76.7%  100.0%     0.00       91.49               0    20/0
single_llm     20  70.0%  80.0%  100.0%     1.15       96.11               6    20/0
```

Add `--per-scenario` to also dump the per-(system, scenario) detail.

---

## Try it — full re-execution in Webots

End-to-end re-run of all 60 (system × scenario) experiments. Requires
**Webots R2023b+**, an **OpenAI API key**, and a Python env with the deps
in [`requirements.txt`](requirements.txt). Estimated cost: ~3 hours of
Webots wall-clock plus ~$5–10 in GPT-4o API.

The system runs as a client–server stack across three terminals:

```bash
# Terminal 1 — Webots GUI
#   File → Open World → webots/worlds/home.wbt
#   Manually set door positions to match the scenario's `door_states` field.

# Terminal 2 — TCP bridge
python -m robot_server.mainserver

# Terminal 3 — orchestrator (assumes a conda env named `agent`)
conda activate agent
export OPENAI_API_KEY=sk-...
python -m eval.run_experiment \
    --systems rule_based single_llm mas \
    --trials 1 \
    --scenarios-file scenarios/scenarios.json \
    --results-dir results/

# After the run, regenerate the canonical CSVs and re-verify
python -m eval.aggregate_results --results-dir results/
python scripts/replay_grade.py --verify-jsons
```

Common subset commands:

```bash
# Plan-only smoke test (no robot, no Webots)
python -m eval.run_experiment --systems rule_based single_llm \
    --trials 1 --dry --scenarios s07 \
    --scenarios-file scenarios/scenarios.json \
    --results-dir results/_smoke

# Re-run a single scenario on the MAS only
python -m eval.run_experiment --systems mas \
    --trials 1 --scenarios s14 \
    --scenarios-file scenarios/scenarios.json \
    --results-dir results/
```

The full walkthrough — including the per-scenario door-state table, the
known caveats (s04 recursion limit, s19/s20 hallucinated arrival pattern in
fresh runs), and troubleshooting — is in
[`docs/reproduction.md`](docs/reproduction.md).

---

## Citation

Please cite the IEEE Access paper if you use this code or benchmark.
Machine-readable metadata is in [`CITATION.cff`](CITATION.cff).

## License

MIT — see [`LICENSE`](LICENSE).
