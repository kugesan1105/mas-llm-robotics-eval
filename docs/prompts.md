# Prompts

The MAS uses one prompt per agent class. Prompt content lives in
[`prompts/`](../prompts/); each agent class loads its prompt at construction
time. This document indexes the mapping. For the architectural role of each
agent see [`docs/architecture.md`](architecture.md) §3.

---

## 1. Per-agent prompt mapping

| Agent class | Source code | Prompt file(s) |
|---|---|---|
| `BossAgent` | [`mas/agents/boss.py`](../mas/agents/boss.py) | [`prompts/boss.txt`](../prompts/boss.txt) + [`prompts/shared/context.md`](../prompts/shared/context.md) § Boss — Supportive Info |
| `TopPlannerAgent` | [`mas/agents/top_planner.py`](../mas/agents/top_planner.py) | `prompts/shared/context.md` § Top Planner — Supporting Info |
| `WorkflowClassifierAgent` | [`mas/agents/workflow_classifier.py`](../mas/agents/workflow_classifier.py) | [`prompts/workflow_classifier.txt`](../prompts/workflow_classifier.txt) + `prompts/shared/context.md` § Workflow Classifier — Supportive Info |
| `SpeakerAgent` | [`mas/agents/speaker.py`](../mas/agents/speaker.py) | `prompts/shared/context.md` § Speaker — Supportive Info |
| `ObjectFindingAgent` | [`mas/agents/object_searcher.py`](../mas/agents/object_searcher.py) | inline + `prompts/shared/context.md` § Environment Description |
| `QuestionAnsweringAgent` | [`mas/agents/question_answerer.py`](../mas/agents/question_answerer.py) | inline + shared environment |
| `NavigationSupervisorMainAgent` | [`mas/agents/navigational_supervisor_main.py`](../mas/agents/navigational_supervisor_main.py) | [`prompts/navigation.txt`](../prompts/navigation.txt) |
| `NavigationSupervisorSecAgent` | [`mas/agents/navigational_supervisor_sec.py`](../mas/agents/navigational_supervisor_sec.py) | [`prompts/navigation_NHS.txt`](../prompts/navigation_NHS.txt) + `prompts/shared/context.md` § NHS Agent Special Notes |
| `DestinationDecisionAgent` | [`mas/agents/final_destination_identifier.py`](../mas/agents/final_destination_identifier.py) | inline + shared environment |
| `WaypointGenerationAgent` | [`mas/agents/waypoint_generator.py`](../mas/agents/waypoint_generator.py) | inline + `prompts/shared/context.md` § Environment Description (Path Planner), § Example: Final Waypoints |
| `FinalNavigationalPlannerAgent` | [`mas/agents/final_navigational_planner.py`](../mas/agents/final_navigational_planner.py) | `prompts/shared/context.md` § Example: Scenarios Plan |
| `NavigationalHandlerMainAgent` | [`mas/agents/navigation_handler_main.py`](../mas/agents/navigation_handler_main.py) | `prompts/navigation.txt` |
| `NavigationalHandlerSecAgent` | [`mas/agents/navigation_handler_sec.py`](../mas/agents/navigation_handler_sec.py) | `prompts/navigation_NHS.txt` |
| `PathPlannerAgent` | [`mas/agents/path_planner.py`](../mas/agents/path_planner.py) | `prompts/shared/context.md` § Environment Description (Path Planner) |
| `DoorStatusCheckerAgent` | [`mas/agents/door_status_checker.py`](../mas/agents/door_status_checker.py) | inline (vision prompt — VLM call with the camera frame) |
| `ErrorHandlerAgent` | [`mas/agents/error_handler.py`](../mas/agents/error_handler.py) | `prompts/shared/context.md` § Error Handling Info |
| `TranscriptionAgent` | [`mas/agents/transcriptioner.py`](../mas/agents/transcriptioner.py) | n/a — Whisper-style audio transcription |

"inline" = the prompt template lives directly in the Python source rather
than in `prompts/`. This is true for the vision-grounded agents
(`ObjectFindingAgent`, `DoorStatusCheckerAgent`) where the prompt embeds
image bytes, and for short-form agents whose prompt is short enough to live
beside the parser.

---

## 2. Shared context file

[`prompts/shared/context.md`](../prompts/shared/context.md) consolidates 11
runtime reference fragments from the original WSL working tree into one
file with section headers:

| Section | Used by |
|---|---|
| Environment Description | most spatial agents |
| Environment Description (Path Planner) | `PathPlannerAgent`, `WaypointGenerationAgent` |
| Special Notes | strategic and navigation tiers |
| NHS Agent Special Notes | `NavigationalHandlerSecAgent` |
| Boss — Supportive Info | `BossAgent` |
| Top Planner — Supporting Info | `TopPlannerAgent` |
| Workflow Classifier — Supportive Info | `WorkflowClassifierAgent` |
| Speaker — Supportive Info | `SpeakerAgent` |
| Example: Final Waypoints | `WaypointGenerationAgent` |
| Example: Scenarios Plan | `FinalNavigationalPlannerAgent` |
| Error Handling Info | `ErrorHandlerAgent` |

Each section is annotated with its source filename so an agent that needs
only one section can either parse the consolidated file or load the
corresponding standalone prompt file.

---

## 3. GPT-4o configuration

All LLM calls in the MAS and Baseline B use the same configuration for
fairness:

- Model: `gpt-4o-2024-08-06`
- Temperature: `0`
- Output format: JSON-validated via `langchain_core.output_parsers.JsonOutputParser`

Prompt construction relies on
`langchain_core.prompts.ChatPromptTemplate` with `MessagesPlaceholder` for
the `GraphState`-derived chat history.

---

## See also

- [`docs/architecture.md`](architecture.md) §3 — full per-agent reference with role descriptions.
- [`docs/goal_conditions.md`](goal_conditions.md) — predicates each agent's outputs are graded on.
