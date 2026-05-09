# mas-llm-robotics-eval

Evaluation harness, scenarios, results, scoring scripts, grading rubric,
and reproduction guide for **"Enabling Robotic Cognition: A Hierarchical
Multi-Agentic System for LLM-Driven Autonomous Problem-Solving in
Robotics"** (IEEE Access, manuscript ID **Access-2026-09207**).

The system source code (the proposed Hierarchical MAS, the two baselines,
the per-agent prompts, the Webots world and controller, and the TCP/JSON
bridge) lives in the companion repository:

> **[mas-llm-robotics](https://github.com/kugesan1105/mas-llm-robotics)**

This repository is self-contained for the **5-second number-verification**
flow (Tier-2). For end-to-end re-execution in Webots (Tier-1) you also
need the companion repository — see the reproduction guide.

---

## TL;DR

Three systems on the same 20-scenario Webots benchmark, same robot, same RRT
motion planner, same GPT-4o backbone, same scenario-supplied door states:

| System | Success Rate | Goal-Conditions Recall | Executability | Hallucinated retrieval/grounding confirmations |
|---|---:|---:|---:|---:|
| Baseline A — Rule-Based replanner (no LLM) | 65.0 % | 76.7 % | 100 % | 0 |
| Baseline B — Non-Agentic LLM planner | 70.0 % | 80.0 % | 100 % | **5** |
| **Hierarchical MAS (proposed)** | **90.0 %** | **83.3 %** | **100 %** | **0** |

**Headline:** the gap is in the hallucination column, not the SR column.
The non-agentic LLM emits five user-facing confirmations that contradict
ground truth (e.g., *"I have brought the hammer"* when there is no
hammer); the proposed MAS emits zero.

Verify the numbers in 5 seconds, no Webots and no API key:

```bash
git clone https://github.com/kugesan1105/mas-llm-robotics-eval
cd mas-llm-robotics-eval
python scripts/replay_grade.py --verify-jsons
```

---

## Repository layout

- [`eval/`](eval/) — experiment orchestrator, grader, aggregator.
- [`scenarios/scenarios.json`](scenarios/scenarios.json) — the 20 benchmark scenarios.
- [`results/`](results/) — canonical per-scenario logs and aggregate CSVs.
- [`scripts/replay_grade.py`](scripts/replay_grade.py) — 5-second number-verification utility.
- [`docs/`](docs/) — long-form documentation:
  [`evaluation.md`](docs/evaluation.md) (rubric + score tables + Section VII-D defences),
  [`reproduction.md`](docs/reproduction.md) (how to re-run).

The proposed system, both baselines, the per-agent prompts, the Webots
world, and the TCP/JSON bridge live in the companion repository:
[mas-llm-robotics](https://github.com/kugesan1105/mas-llm-robotics). The
README of the code repo describes the system internals at a high level.

---

## Evaluation & metrics

### How a scenario is graded

Each scenario in [`scenarios/scenarios.json`](scenarios/scenarios.json) is
associated with a fixed list of binary goal-condition predicates (1 to 3 per
scenario, total 30 across the 20 scenarios). The convention follows
**ProgPrompt** (Singh et al., ICRA 2023) and **VirtualHome** (Puig et al.,
CVPR 2018), under which heavier tasks (object retrieval) carry more
predicates than lighter tasks (out-of-scope refusal).

The predicate count by category:

| Category | Predicate count | Predicates |
|---|---:|---|
| Negative / out-of-scope refusal | 1 | clean abort or refusal-without-movement |
| Information-only ("where is X?") | 1 | emit a correct inform message |
| Guidance ("take me to X") | 1 | reach the destination |
| Object-search-and-report | 2 | visit the target room; emit a correct inform |
| Object-retrieve | 3 | visit; find/grab; return-or-inform |
| Dynamic-constraint navigation | 2 | valid plan; reach the destination |

### The three reported metrics

- **Success Rate (SR)** — fraction of scenarios in which **every** predicate is satisfied.
- **Goal-Conditions Recall (GCR)** — total predicates satisfied across all scenarios divided by the total possible. Gives partial credit when only some predicates of a scenario are met.
- **Executability (Exec)** — fraction of generated plan actions that parse and are valid in the action vocabulary.

### The grader

The same grader is applied identically to all three systems. It is
[`grade_outcome`](eval/metric_logger.py) at line 189 of
[`eval/metric_logger.py`](eval/metric_logger.py): a deterministic Python
function that reads each run's outcome dictionary (final position, whether
the target object was found/grabbed, whether the user was informed, whether
the run aborted, etc.) and returns the predicate-level score.

Predicate definitions, the outcome-dict schema, per-scenario goal-condition
lists, and per-(system, scenario) score tables are in
[`docs/evaluation.md`](docs/evaluation.md).

### The strict failure rubric

A run counts as a **failure** under the strict rubric if the system's final
user-facing output is inconsistent with the ground-truth world state declared
in the scenario, regardless of whether the underlying plan executed. Four
failure subtypes are recognised:

- **(a) Hallucinated retrieval claim** — emitting *"I have brought the hammer"* when the hammer is not in the world.
- **(b) Infeasible action claim** — claiming completion of a task that is physically blocked (e.g., a retrieval claim while every path to the target room is closed).
- **(c) False-absence / false-presence report** — incorrectly stating an object's presence or absence relative to ground truth.
- **(d) Fabricated out-of-scope answer** — confidently answering an out-of-scope question instead of refusing. Reported separately as a **scope-handling failure** rather than as a hallucinated retrieval/grounding confirmation.

Subtypes (a)–(c) are jointly counted in the headline **"Hallucinated
retrieval/grounding confirmations"** column of the result table above (5 for
the non-agentic LLM, 0 for the MAS, 0 for the rule-based system). Subtype
(d) is reported separately. The replay-grading tool's `Hallucinations`
column counts subtypes (a)–(d) together, so it shows **6** for the
non-agentic LLM (5 retrieval/grounding + 1 scope-handling).

---

## Per-scenario score analysis

The numerator and denominator behind each row of the headline table:

- Rule-Based: SR = 13 / 20, GCR = 23 / 30
- Non-Agentic LLM: SR = 14 / 20, GCR = 24 / 30
- MAS: SR = 18 / 20, GCR = 20 / 24

The MAS denominator is **24** rather than 30 because six scenarios (s05,
s08, s14, s16, s17, s18) carry over the coarser pass/fail rubric originally
used for Table I of the manuscript. Re-grading those six under the strict
rubric would shift MAS GCR upward to **86.7 %** or **90.0 %** depending on
how an edge case in s08 is read; the conservative **83.3 %** is what
matches the actual graded-data denominator. The full carry-over math is in
[`docs/evaluation.md`](docs/evaluation.md) §3.3.

### Why GCR can sit below SR for the MAS row

The denominator of GCR is weighted by predicate count, not scenario count.
The MAS's two failures (s02 and s08) carry weights 3 and 1 respectively, so
4 of 24 predicate slots remain unmet even though only 2 of 20 scenarios
fail. ProgPrompt [Singh et al., ICRA 2023] reports the same pattern in
their Table 3: GCR sits below SR when failures concentrate on tasks with
longer predicate lists.

---

## Failure-case analysis

### Baseline A — Rule-Based replanner (7 failures)

Six are perception/verbal limitations (no LLM, no visual recognition, no
content-bearing acknowledgement): **s01, s02, s05, s08, s09, s17**. One
(**s07**) is intent-disambiguation under lexical matching — the keyword
table did not separate "where is X" (information request) from "go to X"
(guidance), so the system navigated when it should have informed.

No hallucinations are possible because there is no generative model.

### Baseline B — Non-Agentic LLM planner (6 failures)

Each failure is mapped to its strict-rubric subtype below. Verbatim
user-facing outputs are quoted from the per-run logs in
[`results/single_llm/`](results/single_llm/).

| Scenario | Subtype | Verbatim user-facing output | Ground-truth world |
|---|---|---|---|
| s01 | (a) hallucinated retrieval | "I have brought the hammer" | hammer not in world |
| s04 | (b) infeasible action claim | retrieval claimed | all doors to target room closed |
| s05 | (a) hallucinated retrieval | "I have brought the allen key kit" | allen key kit not in world |
| s08 | (c) false-absence report | "the chair is not in R1" | chairs are present in R1 |
| s09 | (a) hallucinated retrieval | "I have brought the PLC kit" | PLC kit not in world |
| s12 | (d) fabricated out-of-scope answer | "Joe Biden is the president of the USA" | scope-handling — should have refused |

s01, s04, s05, s08, s09 are jointly counted as the **5 hallucinated
retrieval/grounding confirmations** in the headline table; s12 is the
**1 scope-handling failure**.

### Hierarchical MAS — proposed (2 failures)

Both failures are perception- or execution-layer, not generative reasoning:

- **s02** — perception layer. The robot reached the correct room (R2), but
  visual recognition did not detect the hammer that was actually present.
  No hallucinated claim was emitted; the run ended with a correct
  not-found report rather than a fabricated retrieval.
- **s08** — execution layer. The robot identified the chairs in R1 but did
  not navigate back to the user before reporting. The reasoning chain was
  correct; the workflow loop closed early.

---

## Why MAS produces zero hallucinated confirmations

The architectural mechanism is **hierarchical error escalation**. When a
perception agent (e.g., `DoorChecker`) reports a state inconsistent with
the current plan, the failure is propagated through `ErrorHandler` to a
strategic agent (`NavigationsupervisorMain`) carrying the full mission
context from the shared `GraphState`, which re-invokes `WaypointGenerator`
under the updated environmental constraint. If no valid path exists, the
system aborts and informs the user. The LLM is never asked the question
"did you complete the task?" while the system is in an error state, so it
cannot fabricate a completion claim.

For the side-by-side comparison with SayCan / Text2Motion / ProgPrompt /
Baseline B, see [`docs/evaluation.md`](docs/evaluation.md) §5. For the
code realisation see the companion code repository
[mas-llm-robotics](https://github.com/kugesan1105/mas-llm-robotics).
For why this architectural gap is expected to be stable as language
models improve, see [`docs/evaluation.md`](docs/evaluation.md) §6.

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
    - 6 CSV rows have no JSON log (Table I carry-over -- see docs/evaluation.md §3.3)

System          n     SR    GCR    Exec   LLM/run  Wall_s/run  Hallucinations  fresh/table_i
mas            20  90.0%  83.3%  100.0%    35.38      180.13               0    14/6
rule_based     20  65.0%  76.7%  100.0%     0.00       91.49               0    20/0
single_llm     20  70.0%  80.0%  100.0%     1.15       96.11               6    20/0
```

The `Hallucinations` column counts subtypes (a)–(d) together (5 + 1 for
the non-agentic LLM, where 5 is the headline "hallucinated retrieval/
grounding" count and 1 is the scope-handling failure).

Add `--per-scenario` to also dump the per-(system, scenario) detail.

---

## Try it — full re-execution in Webots

End-to-end re-run of all 60 (system × scenario) experiments. Requires
**both repositories** (this one for the eval harness; the
[mas-llm-robotics](https://github.com/kugesan1105/mas-llm-robotics) repo
for the system code), **Webots R2023b+**, an **OpenAI API key**, and a
Python env with the deps in the code repo's `requirements.txt`. Estimated
cost: ~3 hours of Webots wall-clock plus ~$5–10 in GPT-4o API.

The system runs as a client–server stack across three terminals:

```bash
# Clone both repos side by side
git clone https://github.com/kugesan1105/mas-llm-robotics
git clone https://github.com/kugesan1105/mas-llm-robotics-eval
cd mas-llm-robotics-eval

# Install deps from the code repo and make it importable
pip install -r ../mas-llm-robotics/requirements.txt
export PYTHONPATH=$PYTHONPATH:$(pwd)/../mas-llm-robotics

# Terminal 1 — Webots GUI
#   File → Open World → ../mas-llm-robotics/webots/worlds/home.wbt
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
known caveats (s04 recursion limit, s19/s20 hallucinated arrival pattern
in fresh runs), and troubleshooting — is in
[`docs/reproduction.md`](docs/reproduction.md).

---

## Citation

Please cite the IEEE Access paper if you use this code or benchmark.
Machine-readable metadata is in [`CITATION.cff`](CITATION.cff).

## License

MIT — see [`LICENSE`](LICENSE).
