# Architecture

This document describes the implementation behind manuscript Section III. It
maps each architectural concept in the paper to a concrete file or function so
that a reviewer or extender can navigate the code directly.

---

## 1. Two-process boundary

The system runs as a **client–server stack** so the LLM-driven reasoning and
the Webots-driven robot control can scale independently:

```
   Webots (terminal 1)
   ┌────────────────────────┐                  ┌────────────────────────────────┐
   │ home.wbt + Pioneer     │                  │ MAS / Baseline orchestrator    │
   │ controller (Python in  │                  │ (terminal 3)                   │
   │ webots/controllers/    │                  │                                │
   │ project_12_pioneer-    │                  │  - eval/run_experiment.py      │
   │ controller_1/)         │                  │  - mas/app.py (LangGraph)      │
   │                        │                  │  - baselines/{rule_based,      │
   │  ↕ frame              │                  │     single_llm}.py             │
   │  TCP/JSON length-     │                  │                                │
   │  prefixed              │                  │  ↕ frame                      │
   └─────────┬──────────────┘                  └────────┬───────────────────────┘
             │                                          │
             │   ┌──────────────────────────────────┐   │
             └──►│  TCP bridge (terminal 2)         │◄──┘
                 │  robot_server/mainserver.py      │
                 │  port 5000, frame-based forward  │
                 └──────────────────────────────────┘
```

Both endpoints implement the same wire format (`recv_frame` / `send_frame` in
[`comm/com_client.py`](../comm/com_client.py) and
[`robot_server/mainserver.py`](../robot_server/mainserver.py)): a 4-byte
network-order length prefix followed by a UTF-8 JSON body. The server
forwards each frame to the addressee named in the frame's `"To"` field, so any
subset of `{webots, mas, single_llm, rule_based}` can be connected
simultaneously without changing wire code.

This split is what lets the LLM-side absorb network latency without
destabilising low-level robot control: the controller (terminal 1) keeps a
local reactive loop alive while the LLM-side waits for the next strategic
input. See manuscript Section VIII-B for the corresponding latency analysis.

---

## 2. The agent graph (LangGraph)

The proposed MAS is a **LangGraph state machine with 21 nodes** organised into
five logical tiers. Source: [`mas/app.py`](../mas/app.py) (1023 lines).

### 2.1 Five-tier hierarchy

```
TIER 0 — I/O
  SpeechAgent ←──────────── (loops back from Finisher)
       ↓
TIER 1 — Strategic / mission-level
  Boss ──(Router_boss)──→ Speaker | TopPlanner
       ↓                       ↑
  TopPlanner                   │
       ↓                       │
  WorkflowClassifier ──(Router_workflow_classifier)──→ branches below
       ↓
TIER 2 — Task-level (one per task category)
  ObjectSearcher  ObjectGrabber  QuestionAnswerer  NavigationsupervisorMain
       │              │                │                       │
       └──────────────┴────────────────┘                       │
            (all return to WorkflowClassifier)                  │
                                                                ↓
TIER 3 — Navigation planning
  NavigationsupervisorMain ──→ NavigationsupervisorSec ──(Router_navsupsec)──→
       FinalDestinatioIdentifier  CurrentPositionIdentifier  WaypointGenerator
       FinalNavigationalPlanner ──→ NavigationHandlerMain
                                       ↓
TIER 4 — Execution
  NavigationHandlerMain ──(Router_navhanmain)──→ NavigationHandlerSec
                                                       ↓
                                           ┌──────────┴──────────┐
                                           │  (Router_navhansec) │
                                           ↓        ↓        ↓        ↓
                                    DoorChecker PathPlanner RobotExecutor ErrorHandler
                                       │            │            │            │
                                       └────────────┴────────────┘            │
                                       (return to NavigationHandlerSec)        │
                                                                                ↓
                                                               (Router_errorhandler)
                                                                                ↓
                                                  ┌─────────────────────────────┘
                                                  ↓
                                      NavigationsupervisorMain  WorkflowClassifier
                                          (strategic re-plan)    (re-classify task)

  Finisher ──→ SpeechAgent  (closes the outer loop)
```

`Router_*` are seven small Python functions in [`mas/app.py`](../mas/app.py)
that read the shared `GraphState` and return the name of the next node:

| Router | Source | Purpose |
|--------|--------|---------|
| `Router_boss` | mas/app.py:859 | Strategic dispatch from Boss |
| `Router_speaker` | mas/app.py:864 | Whether Speaker hands off to user or back to graph |
| `Router_workflow_classifier` | mas/app.py:869 | Choose task tier (search / grab / Q&A / navigate) |
| `Router_navsupsec` | mas/app.py:878 | Choose nav sub-step (destination / position / waypoints / planner) |
| `Router_navhanmain` | mas/app.py:883 | Schedule next navigation task |
| `Router_navhansec` | mas/app.py:894 | Choose execution primitive (door / path / robot / error) |
| `Router_errorhandler` | mas/app.py:899 | Strategic vs. tactical recovery |

### 2.2 Hierarchical error escalation

This is the central architectural claim of the manuscript (Section III and the
Contributions list, point 2). The escalation chain is:

```
    perception failure (e.g., closed door observed mid-execution)
                         │
                         ▼
    NavigationHandlerSec  ── detects via DoorChecker / RobotExecutor return ──┐
                         │                                                    │
                         ▼                                                    │
    ErrorHandler  ── reads full mission context from GraphState ──────────────┘
         │
         ├──→ NavigationsupervisorMain   (full strategic re-plan; topological graph
         │                                 re-evaluated under updated door state)
         │
         └──→ WorkflowClassifier          (re-classify task; e.g., escalate from
                                            "navigate" to "abort")
```

Compared with the baselines:

- **Rule-Based Replanner** removes the closed-door edge from its topological
  graph and re-runs Dijkstra from the current cell ([`baselines/rule_based.py`](../baselines/rule_based.py)). No mission-level re-evaluation.
- **Non-Agentic LLM Planner** re-invokes GPT-4o open-loop with the updated state
  ([`baselines/single_llm.py`](../baselines/single_llm.py)). No verification or
  cross-agent recovery.
- **MAS** propagates the failure with full mission context through `ErrorHandler`
  to `NavigationsupervisorMain`, which re-invokes `WaypointGenerator` under the
  new constraint. This is the source of the architectural distinction described
  in manuscript Section VII-D.

---

## 3. Per-agent reference

The 17 agent classes live in [`mas/agents/`](../mas/agents/); four additional
nodes (`SpeechAgent`, `ObjectGrabber`, `CurrentPositionIdentifier`,
`RobotExecutor`, `Finisher`) are wrapper functions defined inline in
`mas/app.py`.

### 3.1 Tier 0 — I/O

| Node | Source | Prompt | Role |
|------|--------|--------|------|
| `SpeechAgent` | `mas/app.py:168` (wraps `mas/agents/transcriptioner.py`) | — | Receives the user utterance, transcribes if audio. Loop-back point from `Finisher`. |
| `Speaker` | `mas/agents/speaker.py` | [`prompts/shared/context.md` § Speaker — Supportive Info](../prompts/shared/context.md) | Emits user-facing messages. |

### 3.2 Tier 1 — Strategic

| Node | Source | Prompt | Role |
|------|--------|--------|------|
| `Boss` | `mas/agents/boss.py` | [`prompts/boss.txt`](../prompts/boss.txt), `prompts/shared/context.md § Boss — Supportive Info` | Decides whether the user request needs reasoning or can be answered immediately; dispatches via `Router_boss`. |
| `TopPlanner` | `mas/agents/top_planner.py` | `prompts/shared/context.md § Top Planner — Supporting Info` | Produces a high-level task plan from the user request. |
| `WorkflowClassifier` | `mas/agents/workflow_classifier.py` | [`prompts/workflow_classifier.txt`](../prompts/workflow_classifier.txt) + shared | Routes the next task in the plan to the appropriate Tier-2 specialist. |

### 3.3 Tier 2 — Task specialists

| Node | Source | Role |
|------|--------|------|
| `ObjectSearcher` | `mas/agents/object_searcher.py` | Visual search for a named object via the robot's camera; emits `Object_search_status` and `Object_location_os`. |
| `ObjectGrabber` | `mas/app.py:329` | Wraps the robot's grab primitive after `ObjectSearcher` succeeds. |
| `QuestionAnswerer` | `mas/agents/question_answerer.py` | Pure-information task: emits `FinalAnswer_qa` without movement. |
| `NavigationsupervisorMain` | `mas/agents/navigational_supervisor_main.py` | Owns the navigation sub-graph (Tier 3 + 4). Receiving point for strategic recovery. |

### 3.4 Tier 3 — Navigation planning

| Node | Source | Role |
|------|--------|------|
| `NavigationsupervisorSec` | `mas/agents/navigational_supervisor_sec.py` | Within-mission router — chooses the next planning sub-step. |
| `FinalDestinatioIdentifier` | `mas/agents/final_destination_identifier.py` | Resolves the user-facing destination string to a logical room (R1/R2/R3/C). |
| `CurrentPositionIdentifier` | `mas/app.py:442` | Reads the robot's current logical position. |
| `WaypointGenerator` | `mas/agents/waypoint_generator.py` | Produces a waypoint sequence over the topological graph (rooms + doors). |
| `FinalNavigationalPlanner` | `mas/agents/final_navigational_planner.py` | Linearises waypoints into per-segment tasks for the Execution tier. |

### 3.5 Tier 4 — Execution

| Node | Source | Role |
|------|--------|------|
| `NavigationHandlerMain` | `mas/agents/navigation_handler_main.py` | Schedules the next per-segment task. |
| `NavigationHandlerSec` | `mas/agents/navigation_handler_sec.py` | Dispatches to the correct execution primitive. |
| `DoorChecker` | `mas/agents/door_status_checker.py` | Visually inspects a door's open/closed state via the camera. |
| `PathPlanner` | `mas/agents/path_planner.py` | Computes an RRT path on the binary occupancy map ([`mas/tools/binary_map.py`](../mas/tools/binary_map.py), [`mas/tools/path.py`](../mas/tools/path.py)). |
| `RobotExecutor` | `mas/app.py:650` | Sends the executable path to the robot via the TCP bridge. |
| `ErrorHandler` | `mas/agents/error_handler.py` | Receives perception/execution failures with full mission context; routes to strategic re-plan. |
| `Finisher` | `mas/app.py:687` | Marks the mission complete; returns control to `SpeechAgent`. |

---

## 4. Shared state (`GraphState`)

All agents communicate through a single LangGraph TypedDict
([`mas/app.py:42`](../mas/app.py#L42)). Field naming convention:
`<purpose>_<owner-suffix>`, e.g., `Thought_boss`, `Plan_FNP`. Grouped:

| Group | Fields |
|-------|--------|
| **Mission-wide** | `Current_robot_position_G`, `Recent_agent_G`, `Raw_user_request_G`, `Transcriptioner_status` |
| **Boss** | `Thought_boss`, `Next_agent_boss`, `AgentInput_boss` |
| **Speaker** | `Speaker_caller`, `Output_speaker` |
| **TopPlanner** | `Thought_toppl`, `taskplan_toppl` |
| **WorkflowClassifier** | `Thought_wc`, `Next_agent_wc`, `AgentInput_wc` |
| **ObjectSearcher / ObjectGrabber** | `Object_tobe_searched_os`, `Object_search_status`, `Object_location_os`, `Object_tobe_grabbed_og`, `Object_location_og`, `Object_grabber_status` |
| **QuestionAnswerer** | `Explanation_qa`, `FinalAnswer_qa` |
| **NavigationsupervisorMain** | `response_navigation_supervisor_main` |
| **NavigationsupervisorSec** | `Thought_navsupsec`, `Action_navsupsec`, `AgentInput_navsupsec` |
| **DestinationIdentifier** | `Explanation_destination` |
| **CurrentPositionIdentifier** | `Current_robot_position_CPI` |
| **WaypointGenerator** | `Room_waypoints`, `Door_sequence`, `Final_waypoints` |
| **FinalNavigationalPlanner** | `Plan_FNP` |
| **NavigationHandlerMain** | `Next_task_NHM`, `Action_type_NHM` |
| **NavigationHandlerSec** | `Thought_navhansec`, `Action_navhansec`, `AgentInput_navhansec` |
| **DoorChecker** | `Door_status_explanation` |
| **PathPlanner** | `Path_planning_status`, `Target_orientation`, `Target_position` |
| **RobotExecutor** | `Robot_executor_status` |
| **ErrorHandler** | `Thought_error`, `Action_error`, `AgentInput_error` |
| **Finisher** | `check_finisher` |

Single shared dict plus content-addressed keys is what allows
`ErrorHandler` to escalate with **full mission context** (Section III, paper):
nothing is hidden behind a private agent state.

---

## 5. Initialisation

`mas/app.py:124–145` instantiates the `Robot` object (occupancy grid, RRT
planner, Webots-side TCP client) and one instance of each agent class:

```python
Robot = robot3.Robot(current_position=(195, 195),
                     show_rt_display=True,
                     show_rt_camera_frame=True)

Transcriptioner          = TranscriptionAgent()
Boss                     = BossAgent()
TopPlanner               = TopPlannerAgent()
Speaker                  = SpeakerAgent()
WorkflowClassifier       = WorkflowClassifierAgent()
ObjectSearcher           = ObjectFindingAgent()
QuestionAnswerer         = QuestionAnsweringAgent()
NavigationSupervisorMain = NavigationSupervisorMainAgent()
NavigationSupervisorSec  = NavigationSupervisorSecAgent()
DestinationIdentifier    = DestinationDecisionAgent()
WaypointGenerator        = WaypointGenerationAgent()
FinalNavigationPlanner   = FinalNavigationalPlannerAgent()
NavigationHandlerMain    = NavigationalHandlerMainAgent()
NavigationHandlerSec     = NavigationalHandlerSecAgent()
PathPlanner              = PathPlannerAgent()
DoorStatusChecker        = DoorStatusCheckerAgent()
ErrorHandler             = ErrorHandlerAgent()
```

Each agent class is a thin `langchain` runnable: it loads its prompt from
`prompts/` and binds a JSON-output parser. Agent code is intentionally short
(~50–200 lines per file) so the state-machine wiring in `mas/app.py` is the
single source of truth for the architecture.

---

## 6. Two entry points

| Entry | Use | Recursion limit |
|-------|-----|-----------------|
| Direct script: `python -m mas.app` | Live operation with audio I/O via `SpeechAgent`. | `recursion_limit=1000` |
| Comparative evaluation: `python -m eval.run_experiment --systems mas` | Bypasses `SpeechAgent` via the text-in wrapper [`mas/runner.py`](../mas/runner.py) so the same scenario stream is graded for all three systems. | `recursion_limit=150` |

The comparative-evaluation wrapper is what makes the MAS row in the
Section VII-D comparative-evaluation table comparable with the two
baselines: it injects the scenario's
`command` and `door_states` directly as `Raw_user_request_G` and the
robot-side door state, skipping audio capture and ASR.

---

## 7. Code-to-paper mapping

The architecture concepts in manuscript Section III map to code as follows:

| Manuscript reference | Code |
|----------------------|------|
| Section III "stateful graph architecture using LangChain and LangGraph" | `mas/app.py:42` (GraphState), `mas/app.py:906` (`workflow = StateGraph(GraphState)`) |
| Contributions §I-A item 1 ("conditional routing and hierarchical error escalation") | `Router_*` functions, `Router_errorhandler`, the Tier-3/4 escalation path |
| Contributions item 2 ("perception-to-replanning loop") | `DoorChecker → ErrorHandler → NavigationsupervisorMain → WaypointGenerator` |
| Section VII-D ("hierarchical ErrorHandler escalation to NavigationSupervisor with full mission context") | `Router_errorhandler` returning `"NavigationsupervisorMain"`, `mas/app.py:822` (`Error_handler`) |
| Figure 3 (agent flow diagram) | The 21 `add_node` + `add_edge` calls at `mas/app.py:909–1019` |
| Algorithm 1 pseudocode | `mas/app.py` `app.invoke(...)` plus the state-key conventions documented in §4 above |

---

## 8. What's *not* in the LangGraph

A reviewer reading the paper sometimes expects every component to be a
LangGraph node. Three components live deliberately outside:

1. **The TCP bridge** ([`robot_server/mainserver.py`](../robot_server/mainserver.py))
   is process-external — it does not appear in the agent graph because it is
   a transport, not a reasoning step.

2. **The RRT motion planner** ([`mas/tools/path.py`](../mas/tools/path.py))
   runs as a method on `Robot` rather than as an agent; the LLM emits a
   target position and the RRT executes geometrically. The corresponding
   metric is `Exec` (Section VII-D), reported per system.

3. **The robot kinematics / ArUco localisation** are also methods on `Robot`
   (`robot3.py`) and do not appear as graph nodes.

This separation is what keeps the LLM-side reasoning bounded: the graph
contains agents that *interpret* state and *decide* the next step, while
the geometric and physical steps live in deterministic Python.
