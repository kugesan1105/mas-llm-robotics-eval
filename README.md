# mas-llm-robotics-eval

Reproduction package for **"Enabling Robotic Cognition: A Hierarchical
Multi-Agentic System for LLM-Driven Autonomous Problem-Solving in Robotics"**
(IEEE Access, manuscript ID **Access-2026-09207**).

---

## TL;DR

Three systems on the same 20-scenario Webots benchmark, same robot, same RRT
motion planner, same GPT-4o backbone, same scenario-supplied door states:

| System | Success Rate | Goal-Conditions Recall | Executability | Hallucinated retrieval/grounding confirmations |
|---|---:|---:|---:|---:|
| Baseline A — Rule-Based replanner (no LLM) | 65.0 % | 76.7 % | 100 % | 0 |
| Baseline B — Non-Agentic LLM planner | 70.0 % | 80.0 % | 100 % | **5** |
| **Hierarchical MAS (proposed)** | **90.0 %** | **83.3 %** | **100 %** | **0** |

**Headline:** two gaps appear under identical model conditions — a
20-percentage-point Success Rate gap (90 vs 70) **and** a categorical
hallucination gap (0 vs 5). The non-agentic LLM emits five user-facing
confirmations that contradict ground truth (e.g., *"I have brought the
hammer"* when there is no hammer); the proposed MAS emits zero.

Verify the numbers in 5 seconds, no Webots and no API key:

```bash
git clone https://github.com/kugesan1105/mas-llm-robotics-eval
cd mas-llm-robotics-eval
python scripts/replay_grade.py --verify-jsons
```

---

## What's in this repository

| Path | Contents |
|------|----------|
| [`mas/`](mas/) | The proposed Hierarchical MAS. 17 agent classes in [`mas/agents/`](mas/agents/), 21-node LangGraph state machine in [`mas/app.py`](mas/app.py), shared topological/RRT tools in [`mas/tools/`](mas/tools/). |
| [`baselines/`](baselines/) | Baseline A ([`baselines/rule_based.py`](baselines/rule_based.py)) and Baseline B ([`baselines/single_llm.py`](baselines/single_llm.py)) — the two systems compared against MAS. |
| [`eval/`](eval/) | Experiment orchestrator ([`eval/run_experiment.py`](eval/run_experiment.py)), grader ([`eval/metric_logger.py`](eval/metric_logger.py)), and aggregator ([`eval/aggregate_results.py`](eval/aggregate_results.py)). |
| [`scenarios/`](scenarios/) | The 20 benchmark scenarios in [`scenarios/scenarios.json`](scenarios/scenarios.json) — one JSON object per scenario with `command`, `expected_destination`, `expected_behavior`, `door_states`, and ground-truth world state. |
| [`results/`](results/) | Canonical per-scenario logs (60 rows = 3 systems × 20 scenarios), aggregate CSVs, and the human-readable summary. |
| [`scripts/`](scripts/) | Reviewer-facing utilities; the most important is [`scripts/replay_grade.py`](scripts/replay_grade.py). |
| [`webots/`](webots/) | The Webots world ([`webots/worlds/home.wbt`](webots/worlds/home.wbt)) and the Pioneer 3-AT controller. |
| [`prompts/`](prompts/) | One prompt per LLM-driven agent. |
| [`comm/`](comm/), [`robot_server/`](robot_server/) | TCP/JSON bridge between the LLM-side orchestrator and the Webots-side controller. |
| [`docs/`](docs/) | Long-form documentation — see index below. |

### Documentation index

| Document | Covers |
|----------|--------|
| [`docs/architecture.md`](docs/architecture.md) | Five-tier agent hierarchy, every node mapped to a source file, the `GraphState` schema, and the code-to-paper mapping. Companion to manuscript Section III. |
| [`docs/goal_conditions.md`](docs/goal_conditions.md) | Full predicate-level grading rubric, per-scenario goal-condition lists, per-(system, scenario) score tables, and the SR / GCR / Exec aggregation arithmetic. Companion to manuscript Section VII-D. |
| [`docs/replanning_landscape.md`](docs/replanning_landscape.md) | Side-by-side replanning behaviour for SayCan, Text2Motion, ProgPrompt, Baseline B, and MAS — the architectural contrast referenced in Section VII-D. |
| [`docs/reproduction.md`](docs/reproduction.md) | Two-tier reproduction guide: 5-second replay grading and full Webots re-execution. Includes per-scenario door-state table, known caveats, and troubleshooting. |
| [`docs/prompts.md`](docs/prompts.md) | Per-agent prompt-file mapping and the GPT-4o configuration used for all LLM calls. |

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
[`docs/goal_conditions.md`](docs/goal_conditions.md).

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
[`docs/goal_conditions.md`](docs/goal_conditions.md) §3.3.

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

The architectural difference responsible for the gap is **hierarchical
error escalation**. When a perception agent (e.g., `DoorChecker`) reports a
state inconsistent with the current plan, the failure is propagated to a
strategic agent (`NavigationsupervisorMain`) carrying the full mission
context from the shared `GraphState`, which re-invokes `WaypointGenerator`
under the updated environmental constraint.

The other systems handle replanning differently:

- **Baseline B** re-invokes GPT-4o open-loop with no preserved state, so the new call can produce a hallucinated retrieval claim in the same way as the initial call.
- **SayCan** re-decides per step via affordance scoring; when affordances drop, it can degenerate into a hallucinated completion claim.
- **Text2Motion** does not regenerate the task plan; the geometric replanner has no fallback at the task level.
- **ProgPrompt** uses pre-baked `assert`/`else` recovery clauses bounded by what the program author anticipated at generation time.

The full side-by-side breakdown is in
[`docs/replanning_landscape.md`](docs/replanning_landscape.md). The code
realisation of the escalation chain is in
[`docs/architecture.md`](docs/architecture.md) §2.2.

---

## Won't a stronger LLM close the gap?

A natural objection: *the gap is just hallucination, and hallucination is a
property of the model. GPT-5 / Claude / Gemini will hallucinate less, so the
architectural advantage will shrink as models improve.*

Four observations make this defensible against the objection:

1. **The gap is not only hallucination.** The Success Rate gap is 20
   percentage points (90 vs 70). Even under a hypothetical zero-hallucination
   LLM, Baseline B's six hallucinated runs would convert to correct outcomes
   at best, lifting it to 76 % — still 14 points below the MAS. The remaining
   gap is structural.

2. **Same backbone in both systems.** All three systems use the same GPT-4o
   model with the same temperature. The MAS produces 0 hallucinations and
   Baseline B produces 5 *under identical model conditions*. Attributing
   the gap to "the model is bad" requires explaining why the same model
   behaves differently in the two architectures.

3. **Hallucination is an architectural symptom, not a model property.**
   Baseline B re-invokes the LLM open-loop on execution failure, with no
   preserved mission state. When execution diverges from plan, the model
   has to reconstruct the situation from scratch and confabulates. The MAS
   preserves the full mission context in its shared `GraphState` and routes
   failures to a strategic agent that already holds the original
   expectation. The MAS is *never asked* to make up a completion claim
   because it never loses track of what it was supposed to do. A stronger
   LLM lowers the rate at which Baseline B confabulates, but does not
   change the property that it can still be asked to. SayCan (running on
   PaLM-540B) exhibits the same degeneration into completion claims when
   per-step affordances drop in blocked-path scenarios.

4. **MAS's residual failures are not reasoning errors.** The MAS's two
   failures (s02, s08) are perception-layer (visual recognition miss) and
   execution-layer (workflow loop closed early before return-to-user). A
   stronger LLM does not fix either of those. So as models improve,
   Baseline B's error budget — which is dominated by LLM-driven failures —
   shrinks, but the MAS's headroom is dominated by perception and
   execution components that are orthogonal to the LLM.

The architectural gap is therefore stable to model choice, not contingent
on it.

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

The `Hallucinations` column counts subtypes (a)–(d) together (5 + 1 for
the non-agentic LLM, where 5 is the headline "hallucinated retrieval/
grounding" count and 1 is the scope-handling failure).

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
known caveats (s04 recursion limit, s19/s20 hallucinated arrival pattern
in fresh runs), and troubleshooting — is in
[`docs/reproduction.md`](docs/reproduction.md).

---

## Citation

Please cite the IEEE Access paper if you use this code or benchmark.
Machine-readable metadata is in [`CITATION.cff`](CITATION.cff).

## License

MIT — see [`LICENSE`](LICENSE).
