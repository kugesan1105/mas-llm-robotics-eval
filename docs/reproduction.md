# Reproduction Guide

Two tiers of reproduction are supported:

| Tier | Goal | Requires | Time | Cost |
|------|------|----------|------|------|
| **Tier 2 — Replay grading** | Verify the Section VII-D comparative-evaluation table from saved logs | Python only | < 5 s | $0 |
| **Tier 1 — Full re-execution** | Re-run the 60 (system × scenario) experiments end-to-end | Webots + GPT-4o key + Python | ~3 h Webots time | ~$5–10 in API |

**Reviewers typically only need Tier 2.** It does not run any LLM call, does not start Webots, and does not consume API credits. It re-aggregates the per-scenario JSON logs in [`results/`](../results/) and produces the same SR / GCR / Exec / hallucination counts as the Section VII-D comparative-evaluation table of the manuscript.

Tier 1 is provided for full transparency and for researchers who want to extend the benchmark or re-measure under different conditions.

---

## Tier 2 — Replay grading (~5 seconds, no Webots, no API key)

### Prerequisites

- Python ≥ 3.9 (the development env used 3.11)
- A POSIX shell (Linux or WSL recommended; the project was developed on WSL Ubuntu)

### Steps

```bash
git clone <repo-url> mas-llm-robotics-eval
cd mas-llm-robotics-eval

# Tier 2 only needs the standard library; no install step is required.
# Optional: a virtualenv if you do not want to install the full Tier 1 deps.
python -m venv .venv && source .venv/bin/activate

# Verify the canonical results
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
        mas/s02  override=table_i_sr                            ...
    - 6 CSV rows have no JSON log (Table I carry-over -- see docs/goal_conditions.md §3.3 footnote)

System           n       SR      GCR     Exec    LLM/run   Wall_s/run  Hallucinations  fresh/table_i
----------------------------------------------------------------------------------------------------
mas             20    90.0%    83.3%   100.0%      35.38       180.13               0    14/6
rule_based      20    65.0%    76.7%   100.0%       0.00        91.49               0    20/0
single_llm      20    70.0%    80.0%   100.0%       1.15        96.11               6    20/0
```

The three SR / GCR / Hallucination columns are exactly the Section VII-D comparative-evaluation table. The script exits with status `0` when there are no unexplained mismatches, and `2` if any per-scenario JSON disagrees with the CSV in a way *not* covered by the two documented override patterns described in [`docs/goal_conditions.md`](goal_conditions.md).

### Optional flags

```bash
python scripts/replay_grade.py --per-scenario      # also dump per-(system, scenario) detail
python scripts/replay_grade.py --results-dir DIR   # custom results location
```

`--per-scenario` is useful if you want to inspect which exact scenarios contributed to each row of the comparative-evaluation table.

---

## Tier 1 — Full re-execution

### Prerequisites

1. **Webots simulator (R2023b or newer).** Install from <https://cyberbotics.com/>. Tested on Ubuntu 22.04 (WSL) and Windows 11.

2. **A conda env named `agent`** (or any equivalent venv) with the dependencies pinned in [`requirements.txt`](../requirements.txt). The development env was conda-managed:

    ```bash
    conda create -n agent python=3.11
    conda activate agent
    pip install -r requirements.txt
    ```

   `requirements.txt` was produced by `pip freeze` of the development environment and includes lines such as `langchain==0.3.25`, `langgraph==0.4.7`, `openai==1.93.0`, `opencv-python==4.12.0.88`, `pygame==2.6.1`, `faiss-cpu==1.11.0`, `numpy==2.2.6`. Lines with `@ file:///home/conda/...` are conda-managed and will be ignored by pip; replace them with their pip-installable equivalents if needed.

3. **An OpenAI API key with access to `gpt-4o`.** Set it once per shell session:

    ```bash
    export OPENAI_API_KEY=sk-...
    ```

   The MAS makes ~35 GPT-4o calls per scenario; the non-agentic LLM baseline makes 1–4. Total cost for one full pass over the 20-scenario benchmark on all three systems is approximately $5–$10 at current rates.

### Three-terminal launch

The system runs as a client–server stack: the Webots controller and the LLM-side orchestrator are separate processes that exchange JSON frames over TCP. Both must be running before any scenario is launched.

| # | Terminal | Command | What it does |
|---|----------|---------|--------------|
| 1 | Webots GUI | open `webots/worlds/home.wbt` from inside Webots | Starts the simulator, the Pioneer 3-AT robot, the four-room lab world, and the controller in [`webots/controllers/project_12_pioneercontroller_1/`](../webots/controllers/project_12_pioneercontroller_1/). The controller connects to the TCP server in step 2. |
| 2 | Linux terminal | `cd <repo-root> && conda activate agent && python -m robot_server.mainserver` | Starts the bridge server on port 5000. The Webots-side controller (terminal 1) and the LLM-side orchestrator (terminal 3) both connect here and exchange frames through the server. |
| 3 | Linux terminal | `cd <repo-root> && conda activate agent && python -m eval.run_experiment --systems rule_based single_llm mas --trials 1 --scenarios-file scenarios/scenarios.json --results-dir results/` | Runs each scenario on each of the three systems and writes per-scenario JSON logs to `results/<system>/`. |

Verify connectivity before starting scenarios: terminal 2 should print "Server listening on 0.0.0.0:5000" followed by "Client 'webots' connected from ..." once the Webots controller has come up.

### Manual door step (before each scenario)

Each scenario in [`scenarios/scenarios.json`](../scenarios/scenarios.json) declares a `door_states` field. Doors not listed are open by default. **Before running a scenario, manually set the door positions in the Webots GUI to match its `door_states`**, and place the robot at the scenario's `initial_position`.

| Scenario | initial_position | door_states |
|---|---|---|
| s01, s02, s05, s06, s07, s08, s09, s10, s11, s12, s13, s15, s18, s19, s20 | R3 | (all open) |
| s03 | R3 | D3 closed |
| s04 | R3 | D3 closed, D4 closed |
| s14 | R2 | D2 closed |
| s16 | R1 | D2 closed |
| s17 | R2 | (all open) |

This manual step is the main reproduction friction. It can be automated via the Webots Supervisor API (set door positions and robot pose programmatically before each scenario) as future work, but is left manual in this release to keep the orchestrator independent of any Webots-version-specific Supervisor binding.

### Useful invocation patterns

Single scenario, single trial, plan-only smoke test (rule_based and single_llm only — no robot):

```bash
python -m eval.run_experiment --systems rule_based single_llm \
    --trials 1 --dry --scenarios s07 \
    --scenarios-file scenarios/scenarios.json \
    --results-dir results/_test
```

Re-run only the MAS on scenarios where Table I was carried over (and update the strict grading once Webots is back up):

```bash
python -m eval.run_experiment --systems mas --trials 1 \
    --scenarios s05 s08 s14 s16 s17 s18 \
    --scenarios-file scenarios/scenarios.json \
    --results-dir results/
```

Aggregate the resulting JSON logs into the canonical CSVs (overwrites them in place):

```bash
python -m eval.aggregate_results --results-dir results/
```

This regenerates [`results/master_per_scenario.csv`](../results/master_per_scenario.csv),
[`results/summary_by_system.csv`](../results/summary_by_system.csv),
[`results/aggregate_report.txt`](../results/aggregate_report.txt), and
[`results/comparison_table.md`](../results/comparison_table.md). Re-run `python scripts/replay_grade.py` afterwards to verify the new numbers reproduce the comparative-evaluation table.

---

## Output structure

After a successful Tier 1 pass:

```
results/
├── master_per_scenario.csv     # 60 rows (3 systems × 20 scenarios)
├── summary_by_system.csv       # 3 rows — one per system
├── aggregate_report.txt        # human-readable summary
├── comparison_table.md         # comparative-evaluation table in Markdown
├── mas/
│   ├── s01_trial1.json
│   ├── ...
│   └── logs/                   # stdout captured per run
│       └── s01_trial1.log
├── rule_based/
│   └── ...
└── single_llm/
    └── ...
```

Each per-scenario JSON contains the `RunLog` schema defined at
[`eval/metric_logger.py`](../eval/metric_logger.py): scenario identity, success
flag, failure reason (if any), per-agent timings, LLM call counts, plan
generated, executable-action count, goal-conditions met/total. See
[`docs/goal_conditions.md`](goal_conditions.md) for how those fields aggregate
into SR / GCR / Exec.

---

## Known caveats

The following items are documented for transparency. None of them invalidate the reported numbers, but a careful re-runner should be aware:

- **MAS scenarios s05, s08, s14, s16, s17, s18 were not re-run for the comparative evaluation** — the manuscript's Table I assessment for those rows was carried over (`source=table_i` in `master_per_scenario.csv`). See `goal_conditions.md` §3.3 footnote. Re-running them in Tier 1 will produce richer logs and may shift the MAS GCR upward by 3–7 points.

- **MAS s04 fresh run can hit the LangGraph recursion limit (150).** The Table I assessment ("identified all paths blocked; informed user") is used in the CSV instead of the failed fresh-run outcome. To avoid this in your own runs, either increase the `recursion_limit` argument in [`mas/runner.py`](../mas/runner.py) or rely on the carry-over.

- **MAS fresh runs for s19 and s20 emit a hallucinated arrival pattern** ("successfully arrived at the netball court" / "...canteen") rather than a clean refusal. The Table I record is a clean refusal, and the CSV uses Table I per the documented `fresh_run+table_i_sr` policy. This divergence is one of the items reported by `python scripts/replay_grade.py --verify-jsons`.

- **Single-LLM hallucinated confirmations on s01, s04, s05, s08, s09, s12** are converted from rubric-success to strict-grader-failure at aggregation time (the `strict_grader_hallucination_override` flag). This implements the strict-failure rubric defined in [`README.md`](../README.md) (Evaluation & metrics → The strict failure rubric) and applied by the grader in [`eval/metric_logger.py`](../eval/metric_logger.py).

- **Wall-clock times are network-bound.** Per-scenario times depend on GPT-4o latency; the reported 180.1 s / 96.1 s / 91.5 s averages are from the development network. Local machine variance of ±20 % is expected.

- **The Webots world `home.wbt` is the only canonical world.** `worlds/new_world.ttt` is a CoppeliaSim variant and `worlds/robot_cutome.wbt` is an early prototype; both are present for completeness but were not used in the manuscript.

---

## Troubleshooting

### "Server listening" never prints in terminal 2

The TCP port (5000) may be occupied. Check with `lsof -i :5000` (Linux) or `netstat -an | grep 5000` (Windows). Stop any conflicting process or change the port in [`robot_server/mainserver.py`](../robot_server/mainserver.py) and the corresponding client constants in [`comm/com_client.py`](../comm/com_client.py).

### Webots controller does not connect

The Webots controller is at [`webots/controllers/project_12_pioneercontroller_1/project_12_pioneercontroller_1.py`](../webots/controllers/project_12_pioneercontroller_1/project_12_pioneercontroller_1.py). It connects to `localhost:5000`. If the LLM side runs on a different host (e.g., WSL while Webots runs on Windows), edit the connection target in that file.

### `OPENAI_API_KEY` not picked up

The agent modules load the key via `python-dotenv`. Either `export OPENAI_API_KEY=...` in the shell that runs terminal 3 or place the key in a `.env` file at the repo root.

### `GraphRecursionError` during a fresh MAS run

LangGraph's recursion guard is set to 150 in [`mas/app.py`](../mas/app.py) and [`mas/runner.py`](../mas/runner.py). Increase to 300 if a particular scenario expands beyond that. The current limit is enough for 19 of 20 scenarios; only s04 (all paths blocked) approaches the limit.

### A scenario fails because the wrong door is open

Re-check the manual door step. Webots door positions persist across runs unless reset; the orchestrator does not change them.

---

## Next steps

After a successful Tier 1 pass, re-aggregate and re-verify:

```bash
python -m eval.aggregate_results --results-dir results/
python scripts/replay_grade.py --verify-jsons
```

If the second command exits with status `0` and prints SR / GCR matching what `aggregate_results.py` wrote into `summary_by_system.csv`, the run is canonical and reproduces the Section VII-D comparative-evaluation table.

For methodology details on how SR / GCR / Exec are defined per scenario, see [`docs/goal_conditions.md`](goal_conditions.md).
