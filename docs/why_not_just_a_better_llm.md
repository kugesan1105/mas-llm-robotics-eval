# Won't a stronger LLM close the gap?

A natural objection to the comparative evaluation in manuscript Section
VII-D is: *the gap is just hallucination, and hallucination is a property
of the model. GPT-5 / Claude / Gemini will hallucinate less, so the
architectural advantage will shrink as models improve.*

This document records why the MAS-vs-Baseline-B gap reported at $n = 20$ is
expected to be stable to model choice, not contingent on it. Four
observations support this.

---

## 1. The gap is not only hallucination

The Success Rate gap is 20 percentage points (MAS 90 % vs Baseline B 70 %).
Even under a hypothetical zero-hallucination LLM, Baseline B's six
hallucinated user-facing runs would convert to correct outcomes at best,
lifting it to 76 % — still 14 percentage points below the MAS. The
residual gap is structural and not addressable by a better model.

The hallucination column (0 vs 5) is the most legible single difference,
but it is not the only difference.

---

## 2. Both systems use the same backbone

All three systems in the comparative evaluation use GPT-4o
(`gpt-4o-2024-08-06`) with temperature 0. The MAS produces 0 user-facing
hallucinations and Baseline B produces 5, under identical model conditions
on the same 20 scenarios.

Attributing the gap to "the model is bad" requires an explanation for why
the *same* model behaves differently in the two architectures.

---

## 3. Hallucination here is an architectural symptom, not a model property

Baseline B re-invokes the LLM open-loop on execution failure, with no
preserved mission state. When execution diverges from the plan, the new
LLM call has to reconstruct the situation from scratch — and the model
sometimes confabulates a completion claim consistent with the *plan it
just regenerated*, rather than with the *world state it observed*.

The MAS preserves the full mission context in its shared `GraphState` (see
[`docs/architecture.md`](architecture.md) §4) and routes failures to a
strategic agent that already holds the original expectation. Concretely,
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
the architecture *can still ask* the model to.

This is consistent with the literature: SayCan (running on PaLM-540B) is a
much larger model than GPT-4o on the parameter axis, and it still exhibits
the same class of degeneration into completion claims when per-step
affordances all drop in blocked-path scenarios. The hallucination failure
mode is not eliminated by scale; it is eliminated by removing the
architectural pressure that produces it.

---

## 4. The MAS's residual failures are not reasoning errors

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

---

## What this implies

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

## See also

- Manuscript Section VII-D — the controlled comparison and the headline numbers.
- [`README.md`](../README.md) — comparative-analysis summary.
- [`docs/replanning_landscape.md`](replanning_landscape.md) — full SayCan / Text2Motion / ProgPrompt / Baseline B / MAS replanning side-by-side.
- [`docs/architecture.md`](architecture.md) §2.2 — the code path that realises hierarchical error escalation.
- [`docs/goal_conditions.md`](goal_conditions.md) §3.2, §3.3 — per-scenario score tables for each system.
