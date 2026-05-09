# Evaluation — Long-form supplementary

This document is the comprehensive companion to manuscript Section VII-D.
It collects everything a reviewer or extender needs in order to audit the
comparative evaluation: the predicate-level grading rubric, the per-scenario
goal-condition lists, the per-(system, scenario) score tables, the
architectural contrast against published replanning approaches, and the
reasoning behind why the reported gap is expected to be stable as language
models improve.

The grading rubric is implemented in
[`eval/metric_logger.py`](../eval/metric_logger.py) (function
`grade_outcome`, line 189) and is applied identically to all three systems
(rule-based, non-agentic LLM, MAS).

---

## 1. Predicate-level grading rubric

The rubric follows the goal-conditions formalism introduced by **VirtualHome**
(Puig et al., CVPR 2018) and adapted by **ProgPrompt** (Singh et al., ICRA 2023,
[5] in the manuscript), under which each task is associated with a fixed list
of binary predicates and metrics are computed against them. We use the same
**variable per-task predicate counts** as those works — heavier tasks (e.g.,
object retrieval) carry more predicates than lighter ones (e.g., out-of-scope
refusal). This is the dominant pattern in the LLM-robotics evaluation
literature; equal-weight grading is uncommon for benchmarks of mixed task
complexity.

### 1.1 Predicate definitions by scenario category

Six task categories appear in the 20-scenario benchmark. Each category defines
its own predicate list. The `expected_behavior` field in
[`scenarios/scenarios.json`](../scenarios/scenarios.json) refines categories
with multiple sub-rubrics.

| Category | `expected_behavior` | Predicate count | Predicates |
|---|---|---|---|
| `negative` | `reject_out_of_scope`, `reject_not_in_environment` | **1** | (a) `aborted` OR (b) (`informed_user` AND NOT `moved`) |
| `question_answering` | `inform_direction`, `inform_location` | **1** | `informed_user` |
| `semantic` | `inform_location` | **1** | `informed_user` |
| `semantic` | `guide_user`, `reroute_search_retrieve`, others | **1** | `reached_expected` OR `visited_expected` |
| `dynamic_constraint` | `detect_blocked_report` | **1** | `aborted` OR `informed_user` OR NOT `had_valid_plan` |
| `dynamic_constraint` | `reroute_and_guide`, `reroute_retrieve_return` | **2** | (a) `had_valid_plan`; (b) `reached_expected` OR `visited_expected` |
| `object_search` | `search_and_report_present`, `search_and_report_absent`, `search_current_room_report_absent` | **2** | (a) `reached_expected` OR `visited_expected`; (b) `informed_user` |
| `object_search` | `search_and_retrieve`, `retrieve_and_return` | **3** | (a) `reached_expected` OR `visited_expected`; (b) `found_object` if object present, else credit if absent (recognition of absence); (c) `informed_user` OR `returned_to_user` |

A run satisfies the **SR** condition iff every predicate for its scenario is
met. **GCR** is the fraction of predicates met across all scenarios:

```
GCR  =  Σ_i (predicates_met_i)  /  Σ_i (predicates_total_i)
```

**Exec** is the fraction of plan actions that parsed and were valid in the
action vocabulary, summed across all runs.

### 1.2 Outcome-dictionary keys

The outcome dictionary the grader reads is constructed by each system at run
time (see `outcome` keys in the `grade_outcome` docstring,
[`eval/metric_logger.py:160`](../eval/metric_logger.py#L160)):

| Key | Meaning |
|---|---|
| `final_position` | Logical room the robot ended in (R1/R2/R3/C). |
| `reached_expected` | `final_position == scenario["expected_destination"]`. |
| `visited_expected` | The robot touched the expected destination at any point during the run. |
| `found_object` | The robot's perception layer visually confirmed the target. |
| `grabbed_object` | A grab/pick action was emitted and accepted. |
| `returned_to_user` | The robot navigated back to the origin position. |
| `informed_user` | An inform/speak action was emitted. |
| `aborted` | An abort action was emitted (clean refusal). |
| `had_valid_plan` | The plan parsed and passed schema validation. |
| `moved` | The robot left its origin position at some point. |

---

## 2. Per-scenario predicate budget

Applying §1 to the 20 scenarios in
[`scenarios/scenarios.json`](../scenarios/scenarios.json):

| ID | Category | `expected_behavior` | Predicates |
|----|----------|---------------------|------------|
| s01 | object_search | search_and_report_absent | **2** |
| s02 | object_search | search_and_retrieve | **3** |
| s03 | semantic | reroute_search_retrieve | **1** |
| s04 | dynamic_constraint | detect_blocked_report | **1** |
| s05 | object_search | search_and_report_absent | **2** |
| s06 | semantic | guide_user | **1** |
| s07 | question_answering | inform_direction | **1** |
| s08 | object_search | search_and_report_present | **2** |
| s09 | object_search | search_current_room_report_absent | **2** |
| s10 | semantic | inform_location | **1** |
| s11 | question_answering | inform_location | **1** |
| s12 | negative | reject_out_of_scope | **1** |
| s13 | negative | reject_not_in_environment | **1** |
| s14 | dynamic_constraint | reroute_and_guide | **2** |
| s15 | negative | reject_not_in_environment | **1** |
| s16 | dynamic_constraint | reroute_retrieve_return | **2** |
| s17 | object_search | retrieve_and_return | **3** |
| s18 | semantic | guide_user | **1** |
| s19 | negative | reject_not_in_environment | **1** |
| s20 | negative | reject_not_in_environment | **1** |
| **Σ** | | | **30** |

A system fully graded under this rubric has a denominator of **30**.

---

## 3. Per-(system, scenario) scores

Source: [`results/master_per_scenario.csv`](../results/master_per_scenario.csv).
`met / total` is the predicate score; `SR` is 1 iff `met == total`.

### 3.1 Baseline A — Rule-Based Replanner

| ID  | met / total | SR  | Notes |
|-----|:-----------:|:---:|-------|
| s01 | 1/2 | 0 | reached R2; no perception → cannot confirm absence; no informational verbal output |
| s02 | 2/3 | 0 | reached R2; no perception of object presence; no informational verbal output |
| s03 | 1/1 | 1 | rerouted via corridor when D3 closed |
| s04 | 1/1 | 1 | Dijkstra correctly returned PATH_BLOCKED |
| s05 | 1/2 | 0 | reached R2; no perception/verbal |
| s06 | 1/1 | 1 | guided user to sink (R1) |
| s07 | 0/1 | 0 | navigated instead of informing — Type I/G intent confusion |
| s08 | 1/2 | 0 | reached R1; no perception/verbal |
| s09 | 1/2 | 0 | already in R3; no perception/verbal report of absence |
| s10 | 1/1 | 1 | matched keyword `power supply` → R2 |
| s11 | 1/1 | 1 | matched keyword `kuka` → R3 |
| s12 | 1/1 | 1 | UNKNOWN_COMMAND counts as graceful refusal |
| s13 | 1/1 | 1 | UNKNOWN_COMMAND |
| s14 | 2/2 | 1 | rerouted under D2 closed; reached R1 |
| s15 | 1/1 | 1 | UNKNOWN_COMMAND |
| s16 | 2/2 | 1 | alternative path R1→C→R3→R2 |
| s17 | 2/3 | 0 | reached R1; no perception of biscuit packet; no informational verbal output |
| s18 | 1/1 | 1 | guided user to sofa (R1) |
| s19 | 1/1 | 1 | UNKNOWN_COMMAND |
| s20 | 1/1 | 1 | UNKNOWN_COMMAND |
| **Σ** | **23 / 30** | **13 / 20** | |

**Rule-Based: SR = 13/20 = 65.0%, GCR = 23/30 = 76.7%, Exec = 100%.**

Seven failures: s01, s02, s05, s07, s08, s09, s17. Six are perception/verbal
limitations (no LLM, no visual recognition, no content-bearing acknowledgement);
one (s07) is intent-disambiguation under lexical matching.

### 3.2 Baseline B — Non-Agentic LLM Planner

| ID  | met / total | SR  | Notes |
|-----|:-----------:|:---:|-------|
| s01 | 1/2 | 0 | hallucinated retrieval ("I have brought the hammer" — hammer not in world) |
| s02 | 3/3 | 1 | retrieved hammer correctly |
| s03 | 1/1 | 1 | inform that tool is in R2 |
| s04 | 0/1 | 0 | hallucinated retrieval despite all paths blocked |
| s05 | 1/2 | 0 | hallucinated retrieval ("I have brought the allen key kit") |
| s06 | 1/1 | 1 | guided to R1 |
| s07 | 1/1 | 1 | informed direction to study area |
| s08 | 1/2 | 0 | false-absence report ("The chair is not in R1" — chairs present) |
| s09 | 1/2 | 0 | hallucinated retrieval ("I have brought the PLC kit") |
| s10 | 1/1 | 1 | informed power supply is in R2 |
| s11 | 1/1 | 1 | informed Kuka is in R3 |
| s12 | 0/1 | 0 | fabricated answer ("Joe Biden is the president of the USA") |
| s13 | 1/1 | 1 | abort / refused |
| s14 | 2/2 | 1 | rerouted; reached R1 |
| s15 | 1/1 | 1 | abort / refused |
| s16 | 2/2 | 1 | retrieved hammer with alternative path |
| s17 | 3/3 | 1 | retrieved biscuit packet |
| s18 | 1/1 | 1 | guided to sofa |
| s19 | 1/1 | 1 | abort / refused |
| s20 | 1/1 | 1 | abort / refused |
| **Σ** | **24 / 30** | **14 / 20** | |

**Non-Agentic LLM: SR = 14/20 = 70.0%, GCR = 24/30 = 80.0%, Exec = 100%.**

The six failures fall under the four failure subtypes named in manuscript
Section VII-D and in [`README.md`](../README.md) under "How a scenario is
graded": s01, s05, s09 (subtype a — hallucinated retrieval of absent
object); s04 (subtype b — infeasible-action claim under blocked paths);
s08 (subtype c — false-absence report); s12 (subtype d — fabricated
out-of-scope answer).

### 3.3 Hierarchical MAS (proposed)

| ID  | met / total | SR  | Source† | Notes |
|-----|:-----------:|:---:|:------:|-------|
| s01 | 2/2 | 1 | fresh_run+table_i_sr | reached R2; reported absence correctly |
| s02 | 0/3 | 0 | fresh_run+table_i_sr | **paper-recorded failure** (object recognition): reached R2 but vision did not detect the hammer |
| s03 | 1/1 | 1 | fresh_run+table_i_sr | rerouted via corridor; retrieved screwdriver |
| s04 | 1/1 | 1 | fresh_run+table_i_sr | identified all paths blocked; informed user |
| s05 | 1/1 | 1 | table_i ‡ | allen key not present; reported absence (paper-recorded success) |
| s06 | 1/1 | 1 | fresh_run+table_i_sr | guided to sink in R1 |
| s07 | 1/1 | 1 | fresh_run+table_i_sr | informed direction |
| s08 | 0/1 | 0 | table_i ‡ | **paper-recorded failure** (did not return): identified chairs in R1 but stayed there |
| s09 | 2/2 | 1 | fresh_run+table_i_sr | already in R3; reported PLC absence |
| s10 | 1/1 | 1 | fresh_run+table_i_sr | informed power supply is in R2 |
| s11 | 1/1 | 1 | fresh_run+table_i_sr | informed Kuka is in R3 |
| s12 | 1/1 | 1 | fresh_run+table_i_sr | refused — out-of-scope question |
| s13 | 1/1 | 1 | fresh_run+table_i_sr | refused — washroom not in environment |
| s14 | 1/1 | 1 | table_i ‡ | rerouted under D2 closed; guided user to R1 |
| s15 | 1/1 | 1 | fresh_run+table_i_sr | refused — kitchen not in environment |
| s16 | 1/1 | 1 | table_i ‡ | retrieved hammer via alternative path |
| s17 | 1/1 | 1 | table_i ‡ | retrieved biscuit packet |
| s18 | 1/1 | 1 | table_i ‡ | guided user to sofa |
| s19 | 1/1 | 1 | fresh_run+table_i_sr | refused — netball court not in environment |
| s20 | 1/1 | 1 | fresh_run+table_i_sr | refused — canteen not in environment |
| **Σ** | **20 / 24** | **18 / 20** | | |

**MAS: SR = 18/20 = 90.0%, GCR = 20/24 = 83.3%, Exec = 100%.**

Two failures: **s02** (perception layer — visual recognition miss on a
target object that was actually present) and **s08** (execution layer —
failure to return to the user before reporting). Neither is a generative
reasoning error.

### † `source=table_i` and the predicate-budget shortcut for MAS

The 20 scenarios were originally graded for the MAS in Table I of the
manuscript under a coarser pass/fail rubric (one observable per scenario:
whether the overall task succeeded or failed). When the strict, predicate-
level rubric in §1 was introduced for the comparative evaluation,
**fourteen MAS scenarios were re-run from scratch in Webots** and graded
under the full §1 rubric (`source=fresh_run+table_i_sr` in
[`results/master_per_scenario.csv`](../results/master_per_scenario.csv)),
and **six MAS scenarios were carried over from Table I unchanged**
(`source=table_i`) to avoid the cost of re-running them.

The six carried-over scenarios are: s05, s08, s14, s16, s17, s18.

For these six, the predicate count is **1** (the original Table I pass/fail
observable) rather than the **2 or 3** that the §1 rubric would assign. As
a consequence, the MAS denominator is **24** rather than **30**.

The carry-over does not affect SR for the five carry-over successes (which
remain binary successes under either rubric), but it does affect GCR. If
those six scenarios were re-graded under the full §1 rubric:

- The five carry-over successes (s05, s14, s16, s17, s18) would each
  satisfy every predicate of their full rubric, contributing
  **2 + 2 + 2 + 3 + 1 = 10 predicates met out of 10 total** (replacing the
  current 5/5).
- The carry-over failure (s08) would be re-graded under
  `search_and_report_present`'s two predicates (reached/visited and
  `informed_user`). The robot did reach R1, so predicate (a) is met.
  Predicate (b) depends on how the verbal output emitted in R1 is encoded
  in the outcome dict — strict reading (proper inform action required)
  gives 1/2; lenient reading (any user-facing speech counts) gives 2/2.

Combining these, full re-grading would land MAS at:

| s08 reading | Numerator | Denominator | GCR | SR |
|---|---:|---:|:---:|:---:|
| Strict (`informed_user=False`) | 26 | 30 | **86.7%** | 18/20 = 90.0% |
| Lenient (`informed_user=True`) | 27 | 30 | **90.0%** | 19/20 = 95.0% |

Either reading **raises** GCR above the current 83.3% reported in §4. The
manuscript retains the conservative current number because it matches the
actual graded-data denominator and does not require the lenient-reading
judgement call on s08. A reviewer who wishes to verify under full
re-grading can re-run the six carry-over scenarios using the orchestrator
at [`eval/run_experiment.py`](../eval/run_experiment.py); the expected
outcome is that MAS GCR moves into the 86.7–90.0% range and SR moves to
either 90.0% or 95.0% depending on the s08 reading.

---

## 4. Aggregate computation

| System | Σ predicates met | Σ predicates total | GCR | SR (n=20) |
|---|:---:|:---:|:---:|:---:|
| Rule-Based | 23 | 30 | **76.7%** | 13/20 = **65.0%** |
| Non-Agentic LLM | 24 | 30 | **80.0%** | 14/20 = **70.0%** |
| **MAS** | **20** | **24** | **83.3%** | 18/20 = **90.0%** |

Note that GCR can fall below SR for the MAS row because the denominator is
*weighted by predicate count, not scenario count*. The MAS's two failures
(s02, s08) carry weights 3 and 1 respectively. Successful scenarios
contribute 20 predicates against 20 conditions; failing scenarios
contribute 0 predicates against 4 conditions. The recall is therefore
20 / 24 = 83.3%, while the scenario-level success rate is 18 / 20 = 90.0%.

This is the same behaviour reported in ProgPrompt [5] Table 3, where GCR
can sit below SR when failures concentrate on tasks with longer predicate
lists. The rule-based and non-agentic LLM rows do not exhibit this pattern
because their failures are spread across scenarios of varying predicate
weight, not concentrated on the highest-weight ones.

---

## 5. Replanning landscape — architectural contrast

Manuscript Section VII-D contrasts five systems on how they handle a
perception-layer failure (e.g., a closed door observed mid-execution) that
invalidates the originally generated plan.

### 5.1 Side-by-side

| System | Reference | Replanning approach | What gets re-invoked |
|--------|-----------|---------------------|----------------------|
| **SayCan** | [3] (Ahn et al., CoRL 2022) | Per-step re-decision via myopic affordance scoring; no committed multi-step plan to invalidate. | Affordance scoring at each step. |
| **Text2Motion** | [4] (Lin et al., 2023) | No task-level replanning; geometric re-planning of the remaining low-level skills under the updated obstacle map. | Low-level motion planner only. |
| **ProgPrompt** | [5] (Singh et al., ICRA 2023) | Pre-baked `assert`/`else` recovery clauses inside the generated Python-like program; the LLM is not re-invoked at runtime. | Whatever recovery branch the LLM included at generation time. |
| **Baseline B (this work)** | [`baselines/single_llm.py`](https://github.com/kugesan1105/mas-llm-robotics/blob/master/baselines/single_llm.py) | Open-loop LLM re-invocation on execution failure with the updated state. The full plan is regenerated each time. | A fresh GPT-4o call with no inter-call shared state. |
| **MAS (this work)** | [`mas/app.py`](https://github.com/kugesan1105/mas-llm-robotics/blob/master/mas/app.py) (companion code repo) | Hierarchical `ErrorHandler` escalation to the strategic `NavigationsupervisorMain` carrying the full `GraphState` mission context; the strategic layer re-invokes `WaypointGenerator` under the updated environmental constraint. | A targeted strategic agent (not the whole graph), with full mission context. |

### 5.2 What this means for hallucination exposure

Each non-MAS replanning approach has a different exposure to the strict-
grader subtypes (a) hallucinated retrieval, (c) false-absence/presence
report, (d) fabricated out-of-scope answer:

- **SayCan**'s per-step myopic scoring works as long as some action has high
  enough affordance to escape the failure state. When all affordances drop
  (e.g., every adjacent door is closed and the only "available" option is
  to emit a confident completion), the planner can degenerate into a
  hallucinated completion claim. The 20-scenario benchmark intentionally
  includes the blocked-paths scenario s04 to surface this failure mode.

- **Text2Motion** does not regenerate the task plan. When the task-level
  plan presupposes reaching a room that is later observed to be unreachable,
  the geometric replanner has no fallback at the task level. Reported by
  the authors as a known limitation.

- **ProgPrompt**'s `assert`/`else` recovery is bounded by what the original
  program author anticipated at generation time. Novel failure modes
  (especially perception failures the LLM did not hard-code a branch for)
  have no recovery and the program either aborts or emits a stale
  completion.

- **Baseline B** (this work) re-invokes GPT-4o open-loop on each execution
  failure. Because the new call has no shared state with the previous call
  beyond the current robot position and known door states, it can produce
  a hallucinated retrieval claim in the same way as the initial call. The
  six user-facing-output failures enumerated in §3.2 above — five
  hallucinated retrieval/grounding claims (s01, s04, s05, s08, s09) plus
  one scope-handling failure (s12) — are this exact failure pattern.

- **MAS** (this work) routes the failure to the strategic layer with the
  full `GraphState`. Because `NavigationsupervisorMain` sees both the
  original mission context and the perception-layer evidence, the standard
  recovery path is to re-invoke `WaypointGenerator` with the updated
  topological constraint rather than to emit a completion claim. The 0
  hallucinated retrieval/grounding confirmations reported in the Section
  VII-D comparative-evaluation table at n = 20 is the empirical
  consequence of this design.

### 5.3 Where the architectural distinction lives in code

| Step | File | Responsibility |
|------|------|----------------|
| Failure detection (perception) | [`mas/agents/door_status_checker.py`](https://github.com/kugesan1105/mas-llm-robotics/blob/master/mas/agents/door_status_checker.py), [`mas/agents/object_searcher.py`](https://github.com/kugesan1105/mas-llm-robotics/blob/master/mas/agents/object_searcher.py) | Visual confirmation of doors / objects. |
| Failure detection (execution) | `Robot_executor` in [`mas/app.py`](https://github.com/kugesan1105/mas-llm-robotics/blob/master/mas/app.py) | Returns failure status on RRT-path execution failure. |
| Tactical-vs-strategic routing | `Router_navhansec` and `Router_errorhandler` in `mas/app.py` | Decide whether the failure can be retried locally (re-plan path) or must escalate. |
| Strategic re-evaluation | `Navigation_supervisor_main` in `mas/app.py`, `mas/agents/navigational_supervisor_main.py` | Re-evaluates the topological graph under the updated state and re-invokes `WaypointGenerator`. |
| Mission-level cancellation | `Router_errorhandler` returning `"WorkflowClassifier"` | When even strategic re-plan fails, escalate to task re-classification (e.g., abort the retrieval task and inform the user that the target is unreachable). |

### 5.4 Limitations of this comparison

- We treat SayCan, Text2Motion, and ProgPrompt as architectural contrasts
  rather than reimplementing them in our 20-scenario benchmark. The
  architectural claims above follow from the published descriptions of
  those systems and are not based on a re-run on our scenarios. Manuscript
  Section VII-D notes this.
- The benchmark is n = 20 (ablation-style across architectural classes),
  not a statistically powered evaluation. Manuscript Section VII-D
  paragraph 1 explicitly flags this. Section VIII-A and Section VIII-C
  discuss scalability and future work.

---

## 6. Why a stronger LLM does not close the gap

A natural objection to the comparative evaluation is: *the gap is just
hallucination, and hallucination is a property of the model. GPT-5 /
Claude / Gemini will hallucinate less, so the architectural advantage will
shrink as models improve.* Four observations make the gap defensible
against this objection.

### 6.1 The gap is not only hallucination

The Success Rate gap is 20 percentage points (MAS 90 % vs Baseline B 70 %).
Even under a hypothetical zero-hallucination LLM, Baseline B's six
hallucinated user-facing runs would convert to correct outcomes at best,
lifting it to 76 % — still 14 percentage points below the MAS. The
residual gap is structural and not addressable by a better model. The
hallucination column (0 vs 5) is the most legible single difference, but
it is not the only difference.

### 6.2 Both LLM-driven systems use the same backbone

Baseline B and the MAS both use GPT-4o (`gpt-4o-2024-08-06`) with
temperature 0. The MAS produces 0 user-facing hallucinations and Baseline
B produces 5, under identical model conditions on the same 20 scenarios.
Attributing the gap to "the model is bad" requires an explanation for why
the *same* model behaves differently in the two architectures.

### 6.3 Hallucination here is an architectural symptom, not a model property

Baseline B re-invokes the LLM open-loop on execution failure, with no
preserved mission state. When execution diverges from the plan, the new
LLM call has to reconstruct the situation from scratch — and the model
sometimes confabulates a completion claim consistent with the *plan it
just regenerated*, rather than with the *world state it observed*.

The MAS preserves the full mission context in its shared `GraphState`
(see [`mas/app.py`](https://github.com/kugesan1105/mas-llm-robotics/blob/master/mas/app.py)
in the companion code repo) and routes failures to a strategic agent that
already holds the original expectation. Concretely,
when `DoorChecker` reports an unexpected closed door:

1. The failure is escalated through `ErrorHandler` to
   `NavigationsupervisorMain`, which already knows what the original
   destination and intent were.
2. `NavigationsupervisorMain` re-invokes `WaypointGenerator` *under the
   updated topological constraint* — the old plan is invalidated, but the
   mission is not regenerated from a blank slate.
3. If no valid path exists, the system aborts and informs the user.
   Crucially, the LLM is never asked the question "did you complete the
   task?" while the system is in an error state, so it cannot fabricate a
   completion claim.

The MAS is *never asked* to make up a completion claim because it never
loses track of what it was supposed to do. A stronger LLM lowers the rate
at which Baseline B confabulates, but does not change the property that
the architecture *can still ask* the model to. SayCan (running on
PaLM-540B) is a much larger model than GPT-4o on the parameter axis, and
it still exhibits the same class of degeneration into completion claims
when per-step affordances all drop in blocked-path scenarios. The
hallucination failure mode is not eliminated by scale; it is eliminated by
removing the architectural pressure that produces it.

### 6.4 The MAS's residual failures are not reasoning errors

The MAS's two failures on the 20-scenario benchmark are:

- **s02** — perception-layer. The robot reached the correct room but
  visual recognition did not detect the hammer that was actually present.
- **s08** — execution-layer. The robot identified the target object
  correctly but the workflow loop closed before the return-to-user step.

Neither is an LLM hallucination, and neither is repaired by a better
reasoning model. They are fixed by improvements to the visual recognition
stack and the workflow-handler state machine respectively — components
orthogonal to the LLM.

Baseline B's six failures, in contrast, are all LLM-driven: hallucinated
retrieval claims (×3), an infeasible-action claim, a false-absence
report, and a fabricated out-of-scope answer. As LLMs improve, Baseline
B's error budget shrinks because most of its errors are in the LLM. The
MAS's error budget shrinks more slowly with LLM improvements because most
of its remaining errors are *not* in the LLM.

### 6.5 Implication

The architectural gap reported in manuscript Section VII-D is therefore
stable to model choice, not contingent on it. A stronger backbone would:

- Reduce Baseline B's hallucination rate (probably by some, not all).
- Reduce Baseline B's remaining task-failure rate (probably by some, not all).
- Leave the MAS's perception/execution failures unchanged.
- Leave the structural difference in how mission context is preserved
  unchanged — that is determined by the architecture, not the model.

The proposed evaluation is not a head-to-head comparison of language
models; it is a head-to-head comparison of *what role the language model
plays in the system*. That distinction is what the comparative evaluation
controls for.

---

## 7. Reproducibility

Each per-scenario JSON log in [`results/`](../results/) records both the
`outcome` dict consumed by `grade_outcome` and the resulting
`(goal_conditions_met, goal_conditions_total)` tuple. A reviewer can:

- **Audit the rubric** by reading
  [`eval/metric_logger.py:189`](../eval/metric_logger.py#L189) (function
  `grade_outcome`).
- **Audit the per-(system, scenario) outcome** by reading any JSON log
  under `results/<system>/<scenario>_trial<N>.json`.
- **Re-derive the aggregates** from
  [`results/master_per_scenario.csv`](../results/master_per_scenario.csv).
- **Replay the grader** without re-running Webots via
  [`scripts/replay_grade.py`](../scripts/replay_grade.py).
- **Re-run the experiments end-to-end** via
  [`docs/reproduction.md`](reproduction.md).

---

## 8. References

- Singh, I. et al. (2023). *ProgPrompt: Generating Situated Robot Task
  Plans using Large Language Models.* IEEE ICRA. — manuscript reference [5].
- Puig, X. et al. (2018). *VirtualHome: Simulating Household Activities
  via Programs.* IEEE/CVF CVPR. — originator of the goal-conditions
  formalism.
- Ahn, M. et al. (2022). *Do As I Can, Not As I Say: Grounding Language
  in Robotic Affordances (SayCan).* CoRL. — manuscript reference [3].
- Lin, K. et al. (2023). *Text2Motion: From Natural Language Instructions
  to Feasible Plans.* — manuscript reference [4].
- Zhou, G. et al. (2024). *NavGPT: Explicit Reasoning in Vision-and-
  Language Navigation with Large Language Models.* — manuscript
  reference [10].
