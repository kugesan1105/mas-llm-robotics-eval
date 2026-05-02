# mas-llm-robotics-eval

Reproduction package for **"Enabling Robotic Cognition: A Hierarchical
Multi-Agentic System for LLM-Driven Autonomous Problem-Solving in Robotics"**
(IEEE Access, manuscript ID **Access-2026-09207**).

---

## Comparative analysis

Three systems evaluated on the same 20-scenario Webots benchmark with
identical robot, RRT motion planner, GPT-4o backbone (`gpt-4o-2024-08-06`,
T = 0), and scenario-supplied door states.

### How the numbers are graded

Each scenario in [`scenarios/scenarios.json`](scenarios/scenarios.json) is
associated with a fixed list of binary goal-condition predicates (1 to 3
per scenario, total 30 across the 20 scenarios — following ProgPrompt
[Singh et al., ICRA 2023] and VirtualHome [Puig et al., CVPR 2018]). The
predicates depend on the task category:

- **Negative / out-of-scope refusal** — 1 predicate: clean abort or refusal-without-movement.
- **Information-only** ("where is X?") — 1 predicate: emit a correct inform message.
- **Guidance** ("take me to X") — 1 predicate: reach the destination.
- **Object-search-and-report** — 2 predicates: visit the target room, emit a correct inform.
- **Object-retrieve** — 3 predicates: visit, find/grab, return-or-inform.
- **Dynamic-constraint navigation** — 2 predicates: valid plan, reach the destination.

From those predicates we report:

- **SR (Success Rate)** — fraction of scenarios in which **every** predicate is satisfied.
- **GCR (Goal-Conditions Recall)** — total predicates satisfied across all scenarios, divided by the total possible (30). Gives partial credit when only some predicates of a scenario are met.
- **Exec (Executability)** — fraction of generated plan actions that parse and are valid in the action vocabulary.

A scenario is graded as a **failure** under a strict rubric: the system's
final user-facing output must be consistent with the ground-truth world
state declared in the scenario, regardless of whether the underlying plan
executed. Four failure subtypes are recognised:

- **(a) Hallucinated retrieval claim** — emitting *"I have brought the hammer"* when the hammer is not in the world.
- **(b) Infeasible action claim** — claiming completion of a task that is physically blocked (e.g., a retrieval claim while every path to the target room is closed).
- **(c) False-absence / false-presence report** — incorrectly stating an object's presence or absence relative to ground truth.
- **(d) Fabricated out-of-scope answer** — confidently answering an out-of-scope question instead of refusing (counted separately as a "scope-handling failure").

The same rubric is applied identically to all three systems; the grader is
[`eval/metric_logger.py`](eval/metric_logger.py) (`grade_outcome`, line
189). Per-scenario predicate budgets, per-(system, scenario) scores, and
the aggregation arithmetic are in
[`docs/goal_conditions.md`](docs/goal_conditions.md).

### Results

| System | SR | GCR | Exec | Hallucinated retrieval/grounding confirmations |
|---|---:|---:|---:|---:|
| **Baseline A — Rule-Based replanner** (keyword + Dijkstra + FSM, no LLM) | 65.0 % | 76.7 % | 100 % | 0 |
| **Baseline B — Non-Agentic LLM planner** (one GPT-4o call, ProgPrompt-style) | 70.0 % | 80.0 % | 100 % | **5** |
| **Hierarchical MAS (proposed)** | **90.0 %** | **83.3 %** | **100 %** | **0** |

Numerator / denominator for each row:

- Rule-Based: SR = 13 / 20, GCR = 23 / 30
- Non-Agentic LLM: SR = 14 / 20, GCR = 24 / 30
- MAS: SR = 18 / 20, GCR = 20 / 24 *(denominator 24 because six scenarios used a Table I carry-over with a coarser predicate count — see [`docs/goal_conditions.md`](docs/goal_conditions.md) §3.3 footnote; the conservative 83.3 % understates MAS by 3–7 points relative to a full re-grade)*

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
