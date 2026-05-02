# mas-llm-robotics-eval

Reproduction package for **"Enabling Robotic Cognition: A Hierarchical
Multi-Agentic System for LLM-Driven Autonomous Problem-Solving in Robotics"**
(IEEE Access, manuscript ID **Access-2026-09207**).

The package contains the proposed Multi-Agentic System (MAS), two baselines
used in Section VII-D of the manuscript (a deterministic rule-based replanner
and a non-agentic single-shot LLM planner), the 20-scenario benchmark, the
goal-condition grader, the Webots simulation assets, and the canonical
per-scenario logs from the comparative evaluation.

---

## Headline result (Section VII-D Table V)

| System | SR | GCR | Exec | Hallucinated retrieval/grounding confirmations |
|---|---:|---:|---:|---:|
| Rule-Based replanner | 65.0 % | 76.7 % | 100 % | 0 |
| Non-Agentic LLM planner | 70.0 % | 80.0 % | 100 % | 5 |
| **Hierarchical MAS (proposed)** | **90.0 %** | **83.3 %** | **100 %** | **0** |

All three rows reproduce exactly from the saved logs in [`results/`](results/) via
`python scripts/replay_grade.py --verify-jsons` — see
[Quickstart](#quickstart-tier-2-no-webots-no-api-key) below.

---

## Architecture

The proposed system is a **LangGraph state machine** with 21 nodes organised
into five logical tiers:

```
   I/O          SpeechAgent ←─────────────────────────────────┐
                    ↓                                         │
   Strategic    Boss → TopPlanner → WorkflowClassifier        │
                                       ↓ (router)             │
   Task-level   ObjectSearcher  ObjectGrabber  QuestionAnswerer  NavigationsupervisorMain
                                                                          ↓
   Navigation   NavigationsupervisorSec → FinalDestinationIdentifier      │
                                          → CurrentPositionIdentifier     │
                                          → WaypointGenerator             │
                                          → FinalNavigationalPlanner      │
                                                                          ↓
   Execution    NavigationHandlerMain → NavigationHandlerSec ─→ DoorChecker
                                                              ─→ PathPlanner (RRT)
                                                              ─→ RobotExecutor
                                                              ─→ ErrorHandler ──┐
                                                                                ↓
                                                                  Strategic re-plan
                                                                  (back to NavSupMain)
                Finisher ────────────────────────────────────────────────────────┘
```

The two baselines reuse the same robot, RRT motion planner, GPT-4o backbone
(`gpt-4o-2024-08-06`, T = 0), and scenario-supplied door states for fair
comparison. Full agent-by-agent reference and code-to-paper mapping is in
[`docs/architecture.md`](docs/architecture.md).

---

## Quickstart — Tier 2 (no Webots, no API key)

```bash
git clone <repo-url> mas-llm-robotics-eval
cd mas-llm-robotics-eval
python scripts/replay_grade.py --verify-jsons
```

Reproduces SR / GCR / Exec / hallucination counts from
[`results/master_per_scenario.csv`](results/master_per_scenario.csv) and
cross-checks every available per-scenario JSON log against the CSV. Exits
with status `0` on a clean reproduction; status `2` on any unexplained drift.

Runtime: ~5 seconds. No LLM calls, no simulation, no API key required.

---

## Quickstart — Tier 1 (full re-execution)

End-to-end re-run of the 60 (system × scenario) experiments in Webots.
**Three terminals required**, plus a manual door-state setup before each
scenario. Estimated time: ~3 hours of Webots wall-clock plus ~$5–10 in
GPT-4o API cost. Full walkthrough:
[`docs/reproduction.md`](docs/reproduction.md).

```bash
# Terminal 1 — Webots GUI: open webots/worlds/home.wbt
# Terminal 2 (Linux):
python -m robot_server.mainserver
# Terminal 3 (Linux):
conda activate agent
python -m eval.run_experiment \
    --systems rule_based single_llm mas \
    --trials 1 \
    --scenarios-file scenarios/scenarios.json \
    --results-dir results/
```

---

## Repository layout

| Path | Contents |
|---|---|
| [`mas/`](mas/) | Proposed Multi-Agent System: 17 agents + LangGraph wiring + RRT/binary-map tools. |
| [`baselines/`](baselines/) | Rule-based replanner (Baseline A) and non-agentic LLM planner (Baseline B). |
| [`eval/`](eval/) | Experiment orchestrator (`run_experiment.py`), shared metric logger, aggregator. |
| [`comm/`](comm/) | Shared TCP/JSON-frame client used by all three systems. |
| [`robot_server/`](robot_server/) | TCP bridge running on the Webots side. |
| [`webots/`](webots/) | Webots project (world `home.wbt`, controllers, libraries, protos, door reference images). |
| [`prompts/`](prompts/) | Per-agent prompt files + consolidated `shared/context.md` runtime reference. |
| [`scenarios/`](scenarios/) | The 20-scenario benchmark used for SR / GCR / Exec evaluation. |
| [`results/`](results/) | Canonical per-scenario JSON logs + master CSV + summary CSV + comparison table. `archive/` holds intermediate runs for reviewers who do not re-execute. |
| [`docs/`](docs/) | Reproduction guide, architecture overview, goal-condition framework, replanning landscape, prompt index. |
| [`scripts/`](scripts/) | Reviewer transparency tools (`replay_grade.py`). |

---

## Documentation

| Document | Purpose |
|---|---|
| [`docs/reproduction.md`](docs/reproduction.md) | Tier-1 (full) and Tier-2 (replay) reproduction. Includes the manual door-state table and known caveats. |
| [`docs/architecture.md`](docs/architecture.md) | Five-tier agent hierarchy, per-node reference, shared `GraphState` schema, code-to-paper mapping. |
| [`docs/goal_conditions.md`](docs/goal_conditions.md) | The grading rubric. Per-scenario predicate budget, per-(system, scenario) scores, aggregation, and the `source=table_i` carry-over footnote. |
| [`docs/replanning_landscape.md`](docs/replanning_landscape.md) | Comparison of the proposed hierarchical replanning against SayCan, Text2Motion, ProgPrompt, and the open-loop baseline. |
| [`docs/prompts.md`](docs/prompts.md) | Index mapping each agent class to its prompt file(s). |

---

## How to verify a specific number

| Claim in the manuscript | Verification step |
|---|---|
| MAS SR = 90.0 % | `python scripts/replay_grade.py` — first row, "SR" column |
| Single-LLM hallucinated 6 of 20 user-facing confirmations | `--verify-jsons` enumerates the 6 strict-grader overrides |
| MAS hierarchical error escalation | [`docs/architecture.md`](docs/architecture.md) §2.2 + `mas/app.py:822` (`Error_handler`) and the `Router_errorhandler` function |
| Per-agent latency (Table 3) | Each `results/mas/sNN_trial1.json` carries an `agent_timings` array; `eval/aggregate_results.py` produces the summary |
| Goal-condition rubric per category | [`eval/metric_logger.py`](eval/metric_logger.py) `grade_outcome` (line 189), documented in [`docs/goal_conditions.md`](docs/goal_conditions.md) §1 |

---

## Citation

Please cite the IEEE Access paper if you use this code or benchmark. See
[`CITATION.cff`](CITATION.cff) for machine-readable metadata.

---

## License

MIT — see [`LICENSE`](LICENSE).
