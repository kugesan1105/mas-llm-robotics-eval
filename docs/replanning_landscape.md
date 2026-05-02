# Replanning Landscape

This document is the long-form version of the comparison sketched in
manuscript Section VII-D, where five systems are compared on how they handle
a perception-layer failure (e.g., a closed door observed mid-execution) that
invalidates the originally generated plan.

---

## 1. Side-by-side

| System | Reference | Replanning approach | What gets re-invoked |
|--------|-----------|---------------------|----------------------|
| **SayCan** | manuscript [3] (Ahn et al., CoRL 2022) | Per-step re-decision via myopic affordance scoring; no committed multi-step plan to invalidate. | Affordance scoring at each step. |
| **Text2Motion** | manuscript [4] (Lin et al., 2023) | No task-level replanning; geometric re-planning of the remaining low-level skills under the updated obstacle map. | Low-level motion planner only. |
| **ProgPrompt** | manuscript [5] (Singh et al., ICRA 2023) | Pre-baked `assert`/`else` recovery clauses inside the generated Python-like program; the LLM is not re-invoked at runtime. | Whatever recovery branch the LLM included at generation time. |
| **Baseline B (this work)** | [`baselines/single_llm.py`](../baselines/single_llm.py) | Open-loop LLM re-invocation on execution failure with the updated state. The full plan is regenerated each time. | A single fresh GPT-4o call with no inter-call shared state. |
| **MAS (this work)** | [`mas/app.py`](../mas/app.py); see [`docs/architecture.md`](architecture.md) §2.2 | Hierarchical `ErrorHandler` escalation to the strategic `NavigationsupervisorMain` carrying the full `GraphState` mission context; the strategic layer re-invokes `WaypointGenerator` under the updated environmental constraint. | A targeted strategic agent (not the whole graph), with full mission context. |

---

## 2. What this means for the benchmark

The strict grader documented in [`docs/goal_conditions.md`](goal_conditions.md)
penalises hallucinated user-facing confirmations (subtypes (a) hallucinated
retrieval, (c) false-absence/presence report, (d) fabricated out-of-scope
answer). Each non-MAS replanning approach has a different exposure to these
subtypes:

- **SayCan**'s per-step myopic scoring works as long as some action has high
  enough affordance to escape the failure state. When all affordances drop
  (e.g., every adjacent door is closed and the only "available" option is to
  emit a confident completion), the planner can degenerate into a hallucinated
  completion claim. The 20-scenario benchmark intentionally includes the
  blocked-paths scenario s04 to surface this failure mode.

- **Text2Motion** does not regenerate the task plan. When the task-level plan
  presupposes reaching a room that is later observed to be unreachable, the
  geometric replanner has no fallback at the task level. Reported by the
  authors as a known limitation.

- **ProgPrompt**'s `assert`/`else` recovery is bounded by what the original
  program author anticipated at generation time. Novel failure modes
  (especially perception failures the LLM did not hard-code a branch for) have
  no recovery and the program either aborts or emits a stale completion.

- **Baseline B** (ours) re-invokes GPT-4o open-loop on each execution failure.
  Because the new call has no shared state with the previous call beyond the
  current robot position and known door states, it can produce a hallucinated
  retrieval claim in the same way as the initial call. The 6 hallucinated
  user-facing confirmations enumerated in manuscript Appendix A.2 (s01, s04,
  s05, s08, s09, s12) are this exact failure pattern.

- **MAS** (ours) routes the failure to the strategic layer with the full
  `GraphState`. Because `NavigationsupervisorMain` sees both the original
  mission context and the perception-layer evidence, the standard recovery
  path is to re-invoke `WaypointGenerator` with the updated topological
  constraint rather than to emit a completion claim. The 0 hallucinated
  retrieval/grounding confirmations reported in Section VII-D Table V at
  n = 20 is the empirical consequence of this design.

---

## 3. Where the architectural distinction lives in code

| Step | File | Responsibility |
|------|------|----------------|
| Failure detection (perception) | [`mas/agents/door_status_checker.py`](../mas/agents/door_status_checker.py), [`mas/agents/object_searcher.py`](../mas/agents/object_searcher.py) | Visual confirmation of doors / objects. |
| Failure detection (execution) | `Robot_executor` in [`mas/app.py`](../mas/app.py) | Returns failure status on RRT-path execution failure. |
| Tactical-vs-strategic routing | `Router_navhansec` and `Router_errorhandler` in `mas/app.py` | Decide whether the failure can be retried locally (re-plan path) or must escalate. |
| Strategic re-evaluation | `Navigation_supervisor_main` in `mas/app.py`, `mas/agents/navigational_supervisor_main.py` | Re-evaluates the topological graph under the updated state and re-invokes `WaypointGenerator`. |
| Mission-level cancellation | `Router_errorhandler` returning `"WorkflowClassifier"` | When even strategic re-plan fails, escalate to task re-classification (e.g., abort the retrieval task and inform the user that the target is unreachable). |

---

## 4. Limitations of this comparison

- We treat SayCan, Text2Motion, and ProgPrompt as architectural contrasts
  rather than reimplementing them in our 20-scenario benchmark. The
  architectural claims above follow from the published descriptions of those
  systems and are not based on a re-run on our scenarios. Manuscript Section
  VII-D and Appendix A clearly note this.

- The benchmark is n = 20 (ablation-style across architectural classes), not
  a statistically powered evaluation. Manuscript Section VII-D paragraph 1
  explicitly flags this. Section VIII-A and Section VIII-C discuss
  scalability and future work.

---

## See also

- Manuscript Section VII-D and Appendix A.2.
- [`docs/architecture.md`](architecture.md) §2.2 — error escalation in code.
- [`docs/goal_conditions.md`](goal_conditions.md) §3 — per-scenario hallucination outcomes.
