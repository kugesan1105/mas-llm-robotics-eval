# Comparative Evaluation Against Baselines

This document is the long-form companion to manuscript Section VII-D. It
documents the controlled comparison of three systems on the 20-scenario
Webots benchmark, the predicate-level grading rubric, the per-(system,
scenario) score tables, and why the MAS's GCR sits slightly below its SR.

## 1. The three systems compared

We evaluate three systems on the 20-scenario benchmark under identical
conditions: the Pioneer 3-AT robot, the RRT motion planner, the GPT-4o
backbone (used by the two LLM-driven systems), and the scenario-supplied
door states.

- **Baseline A — Rule-Based Replanner.** A classical planner with no LLM.
  The user command is mapped to a destination room through a keyword
  lookup table; Dijkstra's shortest-path algorithm is run on the
  room/door graph with closed-door edges removed; on a blocked-door
  observation during execution, the door is marked closed and the
  planner re-runs.

- **Baseline B — Non-Agentic LLM Planner.** A flat single-LLM planner.
  The user command, the environment description, and a small set of
  few-shot examples are supplied to GPT-4o in one call, which returns
  the complete action plan; on execution failure the LLM is re-invoked
  open-loop with the updated state. This follows the single-call
  program-generation paradigm of ProgPrompt (Singh et al., ICRA 2023).
  SayCan (Ahn et al., CoRL 2022) and Text2Motion (Lin et al., 2023) are
  other non-agentic single-LLM systems treated as architectural
  contrasts rather than reimplemented.

- **Hierarchical MAS (proposed).** The system described in manuscript
  Section III.

## 2. Headline result

| Metric | Rule-Based | Non-Agentic LLM | MAS |
|---|---:|---:|---:|
| Success Rate (SR) | 65.0 % | 70.0 % | **90.0 %** |
| Goal-Conditions Recall (GCR) | 76.7 % | 80.0 % | **83.3 %** |
| Executability (Exec) | 100 % | 100 % | 100 % |
| Hallucinated confirmations | **0** | 5 | **0** |

At n = 20, the non-agentic LLM produces five hallucinations across the
20 scenarios (e.g., *"I have brought the hammer"* when the hammer is not
present in the environment); the proposed MAS produces zero
hallucinations.

## 3. Grading rubric

The same predicate-level grader is applied identically to all three
systems. It is implemented in
[`eval/metric_logger.py`](../eval/metric_logger.py) (`grade_outcome`,
line 189) as a deterministic Python function that reads each run's
outcome dictionary (final position, whether the target object was found
or grabbed, whether the user was informed, whether the run aborted,
etc.) and returns the predicate-level score.

The rubric follows the goal-conditions formalism introduced by
**VirtualHome** (Puig et al., CVPR 2018) and adapted by **ProgPrompt**
(Singh et al., ICRA 2023): each task is associated with a fixed list of
binary predicates, with heavier tasks (e.g., object retrieval) carrying
more predicates than lighter ones (e.g., out-of-scope refusal).

Six task categories appear in the benchmark; each defines its own
predicate list. The `expected_behavior` field in
[`scenarios/scenarios.json`](../scenarios/scenarios.json) refines the
category with sub-rubrics where needed.

| Category | `expected_behavior` | Count | Predicates |
|---|---|---|---|
| `negative` | `reject_out_of_scope`, `reject_not_in_environment` | **1** | (a) `aborted` OR (b) (`informed_user` AND NOT `moved`) |
| `question_answering` | `inform_direction`, `inform_location` | **1** | `informed_user` |
| `semantic` | `inform_location` | **1** | `informed_user` |
| `semantic` | `guide_user`, `reroute_search_retrieve`, others | **1** | `reached_expected` OR `visited_expected` |
| `dynamic_constraint` | `detect_blocked_report` | **1** | `aborted` OR `informed_user` OR NOT `had_valid_plan` |
| `dynamic_constraint` | `reroute_and_guide`, `reroute_retrieve_return` | **2** | (a) `had_valid_plan`; (b) `reached_expected` OR `visited_expected` |
| `object_search` | `search_and_report_present`, `search_and_report_absent`, `search_current_room_report_absent` | **2** | (a) `reached_expected` OR `visited_expected`; (b) `informed_user` |
| `object_search` | `search_and_retrieve`, `retrieve_and_return` | **3** | (a) `reached_expected` OR `visited_expected`; (b) `found_object` if object present, else credit if absent; (c) `informed_user` OR `returned_to_user` |

A run satisfies the **SR** condition iff every predicate for its
scenario is met. **GCR** is the fraction of predicates met across all
scenarios:

```
GCR  =  Σ_i (predicates_met_i)  /  Σ_i (predicates_total_i)
```

**Exec** is the fraction of plan actions that parsed and were valid in
the action vocabulary, summed across all runs.

## 4. Per-scenario predicate budget

Applying §3 to the 20 scenarios in
[`scenarios/scenarios.json`](../scenarios/scenarios.json) gives a total
of **30 predicates**. The per-scenario count: **3 predicates** for s02
and s17 (object retrieval); **2 predicates** for s01, s05, s08, s09
(object-search-and-report) and s14, s16 (dynamic-constraint navigation);
**1 predicate** for the remaining 12 scenarios (refusal, information,
guidance, and dynamic-constraint detection).

## 5. Per-(system, scenario) scores

Source: [`results/master_per_scenario.csv`](../results/master_per_scenario.csv).
`met / total` is the predicate score; `SR` is 1 iff `met == total`.

| ID | Predicates | Rule-Based | Non-Agentic LLM | MAS |
|----|:---:|:---:|:---:|:---:|
| s01 | 2 | 1/2 (0) | 1/2 (0) — hallucinated retrieval | 2/2 (1) |
| s02 | 3 | 2/3 (0) | 3/3 (1) | 0/3 (0) — vision miss |
| s03 | 1 | 1/1 (1) | 1/1 (1) | 1/1 (1) |
| s04 | 1 | 1/1 (1) | 0/1 (0) — hallucinated retrieval under blocked paths | 1/1 (1) |
| s05 | 2 | 1/2 (0) | 1/2 (0) — hallucinated retrieval | 1/1 (1) † |
| s06 | 1 | 1/1 (1) | 1/1 (1) | 1/1 (1) |
| s07 | 1 | 0/1 (0) — intent confusion | 1/1 (1) | 1/1 (1) |
| s08 | 2 | 1/2 (0) | 1/2 (0) — false-absence | 0/1 (0) † — did not return |
| s09 | 2 | 1/2 (0) | 1/2 (0) — hallucinated retrieval | 2/2 (1) |
| s10 | 1 | 1/1 (1) | 1/1 (1) | 1/1 (1) |
| s11 | 1 | 1/1 (1) | 1/1 (1) | 1/1 (1) |
| s12 | 1 | 1/1 (1) | 0/1 (0) — fabricated answer | 1/1 (1) |
| s13 | 1 | 1/1 (1) | 1/1 (1) | 1/1 (1) |
| s14 | 2 | 2/2 (1) | 2/2 (1) | 1/1 (1) † |
| s15 | 1 | 1/1 (1) | 1/1 (1) | 1/1 (1) |
| s16 | 2 | 2/2 (1) | 2/2 (1) | 1/1 (1) † |
| s17 | 3 | 2/3 (0) | 3/3 (1) | 1/1 (1) † |
| s18 | 1 | 1/1 (1) | 1/1 (1) | 1/1 (1) † |
| s19 | 1 | 1/1 (1) | 1/1 (1) | 1/1 (1) |
| s20 | 1 | 1/1 (1) | 1/1 (1) | 1/1 (1) |
| **Σ** | | **23 / 30, 13/20** | **24 / 30, 14/20** | **20 / 24, 18/20** |

Format per cell: `met/total (SR)` with a brief failure note where
applicable. † on the MAS column marks scenarios scored against a coarser
predicate count (one observable instead of two or three) — see §6.

**Rule-Based: SR = 13/20 = 65.0 %, GCR = 23/30 = 76.7 %, Exec = 100 %.**
Seven failures: six perception/verbal limitations (no LLM, no visual
recognition, no content-bearing acknowledgement) and one (s07) intent
disambiguation under lexical matching.

**Non-Agentic LLM: SR = 14/20 = 70.0 %, GCR = 24/30 = 80.0 %, Exec = 100
%.** Six failures fall under four subtypes: hallucinated retrieval of an
absent object (s01, s05, s09), infeasible-action claim under blocked
paths (s04), false-absence report (s08), and fabricated out-of-scope
answer (s12).

**MAS: SR = 18/20 = 90.0 %, GCR = 20/24 = 83.3 %, Exec = 100 %.** Two
failures: s02 (vision did not detect a hammer that was present) and s08
(workflow loop closed before return-to-user). Neither is a generative
reasoning error.

## 6. The MAS denominator and the carry-over (†)

The 20 scenarios were originally graded for the MAS in Table 1 of the
manuscript under a coarser pass/fail rubric (one observable per
scenario: whether the overall task succeeded or failed). When the
strict, predicate-level rubric in §3 was introduced for the comparative
evaluation, **fourteen MAS scenarios were re-run from scratch in
Webots** and graded under the full rubric, and **six MAS scenarios were
carried over from Table 1 unchanged** (`source=table_i` in
[`results/master_per_scenario.csv`](../results/master_per_scenario.csv))
to avoid the cost of re-running them.

The six carried-over scenarios are: **s05, s08, s14, s16, s17, s18**.
For these six, the predicate count is **1** rather than the **2 or 3**
that the §3 rubric would assign. As a consequence, the MAS denominator
is **24** rather than **30**.

The carry-over does not affect SR for the five carry-over successes
(s05, s14, s16, s17, s18) — they remain successes under either rubric
— but it does affect GCR. Re-grading the six under the full §3 rubric
would land the MAS at:

| s08 reading | Numerator | Denominator | GCR | SR |
|---|---:|---:|:---:|:---:|
| Strict (`informed_user=False`) | 26 | 30 | **86.7 %** | 18/20 = 90.0 % |
| Lenient (`informed_user=True`) | 27 | 30 | **90.0 %** | 19/20 = 95.0 % |

Either reading **raises** GCR above the current 83.3 %. The manuscript
retains the conservative current number because it matches the actual
graded-data denominator and does not require the lenient-reading
judgement call on s08.

## 7. Why GCR can sit below SR for the MAS row

Under the variable per-task goal-condition convention, the denominator
of GCR is *weighted by predicate count, not scenario count*. The MAS's
two failures (s02, s08) carry weights 3 and 1 respectively; successful
scenarios contribute 20 predicates against 20 conditions, while failing
scenarios contribute 0 predicates against 4 conditions. The recall is
therefore 20 / 24 = 83.3 %, while the scenario-level success rate is
18 / 20 = 90.0 %.

This is the same behaviour reported in ProgPrompt (Singh et al., ICRA
2023, Table 3), where GCR can sit below SR when failures concentrate
on tasks with longer predicate lists. The rule-based and non-agentic
LLM rows do not exhibit this pattern because their failures are spread
across scenarios of varying predicate weight, not concentrated on the
highest-weight ones.

## 8. Replanning landscape — architectural contrast

The architectural mechanism behind the MAS's zero-hallucination column
is **hierarchical error escalation**: when a failure is detected during
execution, it is propagated to the strategic agent together with the
full mission context, and the strategic agent re-invokes the relevant
lower-tier component (e.g., the waypoint generator) using the updated
state of the environment.

The other systems handle replanning differently:

| System | Replanning approach |
|---|---|
| **Baseline B** (this work) | Open-loop LLM re-invocation on execution failure with the updated state. The full plan is regenerated each time, with no inter-call shared state. |
| **SayCan** (Ahn et al., CoRL 2022) | Per-step re-decision via affordance scoring; no committed multi-step plan to invalidate. |
| **Text2Motion** (Lin et al., 2023) | No task-level replanning; geometric re-planning of the remaining low-level skills under the updated obstacle map. |
| **ProgPrompt** (Singh et al., ICRA 2023) | Pre-baked `assert`/`else` recovery clauses inside the generated program; the LLM is not re-invoked at runtime. Recovery is bounded by what the program author anticipated. |
| **MAS** (this work) | Hierarchical `ErrorHandler` escalation to the strategic `NavigationsupervisorMain` carrying the full `GraphState` mission context; the strategic layer re-invokes `WaypointGenerator` under the updated environmental constraint. |

In each non-MAS case the system either loses, or never had, the
original mission context, and the LLM (or affordance scorer) can be
asked to fill that gap with a confident statement that contradicts
ground truth. The MAS preserves the mission context across the failure
event, so the LLM is never asked the question that produces a
hallucinated answer.

We treat SayCan, Text2Motion, and ProgPrompt as architectural contrasts
rather than reimplementing them in the 20-scenario benchmark; the
architectural claims above follow from the published descriptions of
those systems.
