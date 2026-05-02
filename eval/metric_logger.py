"""
metric_logger.py

Shared logging infrastructure for the three-way evaluation
(MAS, rule-based, single-LLM). All three systems write results
using the same JSON schema so aggregation is trivial.

Usage:
    from eval.metric_logger import RunLog, timed_llm_call

    log = RunLog(scenario_id="s01", system="rule_based", trial=1)
    log.start()
    # ... run the scenario ...
    log.stop(success=True)
    log.save("results/rule_based/s01_trial1.json")
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Any


@dataclass
class LLMCallRecord:
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    timestamp: float


@dataclass
class AgentTimingRecord:
    agent: str
    start: float
    end: float
    duration: float


@dataclass
class RunLog:
    # identity
    scenario_id: str
    system: str                         # "mas" | "rule_based" | "single_llm"
    trial: int

    # outcome
    success: bool = False
    failure_reason: Optional[str] = None
    graceful_failure: bool = False      # did it fail cleanly with a user-facing explanation?

    # timing
    start_time: float = 0.0
    end_time: float = 0.0
    reasoning_time_s: float = 0.0       # sum of LLM latencies (decomposed time)
    locomotion_time_s: float = 0.0      # time spent moving the robot
    perception_time_s: float = 0.0      # time spent on door checks / object recognition

    # plan quality
    plan_generated: Optional[str] = None
    plan_valid: bool = False
    num_plan_actions: int = 0
    num_executable_actions: int = 0     # for Executability metric

    # replanning
    replanning_triggered: bool = False
    replanning_succeeded: Optional[bool] = None
    num_replans: int = 0

    # goal conditions
    goal_conditions_total: int = 0
    goal_conditions_met: int = 0

    # LLM usage
    llm_call_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    llm_calls: list = field(default_factory=list)

    # per-agent timings (MAS only; empty for baselines)
    agent_timings: list = field(default_factory=list)

    # misc
    final_position: Optional[str] = None
    notes: str = ""

    # ---- lifecycle ----

    def start(self):
        self.start_time = time.time()

    def stop(self, success: bool, failure_reason: Optional[str] = None,
             graceful_failure: bool = False):
        self.end_time = time.time()
        self.success = success
        self.failure_reason = failure_reason
        self.graceful_failure = graceful_failure

    # ---- helpers ----

    def log_llm_call(self, agent: str, model: str,
                     input_tokens: int, output_tokens: int,
                     latency_s: float):
        rec = LLMCallRecord(
            agent=agent,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_s=latency_s,
            timestamp=time.time(),
        )
        self.llm_calls.append(asdict(rec))
        self.llm_call_count += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.reasoning_time_s += latency_s

    def log_agent_timing(self, agent: str, start: float, end: float):
        rec = AgentTimingRecord(
            agent=agent,
            start=start,
            end=end,
            duration=round(end - start, 6),
        )
        self.agent_timings.append(asdict(rec))

    def add_locomotion_time(self, seconds: float):
        self.locomotion_time_s += seconds

    def add_perception_time(self, seconds: float):
        self.perception_time_s += seconds

    # ---- serialisation ----

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @property
    def total_time(self) -> float:
        return round(self.end_time - self.start_time, 6)


# ----------------------------------------------------------------------
# LLM call wrapper
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# Unified grading rubric
# ----------------------------------------------------------------------
#
# All three systems (MAS, rule-based, single-LLM) MUST grade outcomes
# using the same rubric so the Success Rate and Goal Conditions Recall
# numbers are comparable. This function is the single source of truth.
#
# The rubric is expressed as goal-condition sets per scenario category.
# A run is a full SR success iff every goal condition is met. GCR is
# the fraction met.
#
# `outcome` is a dict the caller fills with what the system actually
# did:
#     {
#       "final_position":   "R2",
#       "reached_expected": True,        # final_position == expected_destination
#       "visited_expected": True,        # touched expected_destination at any
#                                        #   point during the run. For object
#                                        #   retrieval the robot is expected
#                                        #   to return to origin, so final_pos
#                                        #   != expected_destination is normal.
#       "found_object":     True,        # visually located the target
#       "grabbed_object":   True,        # grabbed / picked up the target
#       "returned_to_user": False,       # navigated back to the origin
#       "informed_user":    True,        # emitted an inform/speak message
#       "aborted":          False,       # emitted an abort action
#       "had_valid_plan":   True,        # plan parsed and passed schema
#     }
#
# Not every field has to be set -- the grader only looks at the ones
# relevant to the scenario category.
# ----------------------------------------------------------------------

def grade_outcome(scenario: dict, outcome: dict) -> tuple[int, int]:
    """
    Compute (goal_conditions_total, goal_conditions_met) for a single run.

    Identical rubric for all three systems; do not fork this function
    inside a system file.
    """
    category = scenario["category"]
    expected_dest = scenario.get("expected_destination")

    reached_expected = bool(outcome.get("reached_expected", False))
    visited_expected = bool(outcome.get("visited_expected", reached_expected))
    informed = bool(outcome.get("informed_user", False))
    aborted = bool(outcome.get("aborted", False))
    found = bool(outcome.get("found_object", False))
    grabbed = bool(outcome.get("grabbed_object", False))
    had_valid_plan = bool(outcome.get("had_valid_plan", False))

    # ----- negative scenarios -----
    # success condition: the system refused cleanly (abort or an
    # informational refusal) instead of inventing a path.
    if category == "negative":
        total = 1
        met = 1 if (aborted or (informed and not outcome.get("moved", False))) else 0
        return total, met

    # ----- question answering -----
    # success condition: emitted an inform message. No movement required.
    if category == "question_answering":
        total = 1
        met = 1 if informed else 0
        return total, met

    # ----- semantic navigation -----
    # Two sub-behaviors:
    #   inform_location: user just asked "where is X?"; answer via inform.
    #   guide_user / other: physically guide the user to the room.
    if category == "semantic":
        behavior = scenario.get("expected_behavior", "")
        if behavior == "inform_location":
            return 1, 1 if informed else 0
        total = 1
        met = 1 if (reached_expected or visited_expected) else 0
        return total, met

    # ----- dynamic constraint -----
    # Two conditions: had a valid plan AND reached expected destination
    # (or, if all paths genuinely blocked, gave up cleanly).
    if category == "dynamic_constraint":
        if scenario.get("expected_behavior") == "detect_blocked_report":
            # e.g. s04: D3 and D4 closed, hammer unreachable. Success =
            # detect that it's unreachable and report cleanly.
            total = 1
            met = 1 if (aborted or informed or not had_valid_plan) else 0
            return total, met
        total = 2
        met = 0
        if had_valid_plan:
            met += 1
        # For retrieval-style dynamic_constraint scenarios the robot is
        # expected to return to origin after completing the task, so we
        # credit "visited" rather than "ended at" the expected destination.
        if reached_expected or visited_expected:
            met += 1
        return total, met

    # ----- object search / retrieve -----
    # Three conditions, but the third (return / inform) is flexible:
    # if the robot either returns to origin OR emits an inform message
    # that counts as "reporting back to the user".
    if category == "object_search":
        behavior = scenario.get("expected_behavior", "")

        # question-answer-shaped object searches ("check whether there
        # are extra chairs") are graded like semantic + inform.
        # The robot is expected to return to origin after the search,
        # so credit visited_expected, not just reached_expected.
        if behavior in ("search_and_report_present", "search_and_report_absent",
                        "search_current_room_report_absent"):
            total = 2
            met = 0
            if reached_expected or visited_expected:
                met += 1
            if informed:
                met += 1
            return total, met

        # standard retrieve = visited target room + find (if object in
        # world) + report back to user (inform OR return to origin).
        total = 3
        met = 0
        if reached_expected or visited_expected:
            met += 1
        object_present = scenario.get("object_in_world", False)
        if object_present and found:
            met += 1
        elif not object_present:
            # if the object is absent, "found=False" is the correct state;
            # credit the recognition step
            met += 1
        reported_back = informed or outcome.get("returned_to_user", False)
        if reported_back:
            met += 1
        return total, met

    return 1, 0


# ----------------------------------------------------------------------
# LLM call wrapper
# ----------------------------------------------------------------------

def timed_llm_call(log: RunLog, agent_name: str, model: str, call_fn):
    """
    Wrap a callable that makes an OpenAI chat completion and return
    (response, latency_seconds). The LLM call details are recorded
    on the provided RunLog.

    Expected call_fn return: an object with `.usage.prompt_tokens`,
    `.usage.completion_tokens`, and the normal OpenAI response shape.

    Example:
        def do_call():
            return client.chat.completions.create(
                model=MODEL, temperature=0, messages=messages)
        resp, dt = timed_llm_call(log, "Planner", MODEL, do_call)
    """
    t0 = time.time()
    resp = call_fn()
    t1 = time.time()
    dt = t1 - t0

    try:
        in_tok = int(resp.usage.prompt_tokens)
        out_tok = int(resp.usage.completion_tokens)
    except AttributeError:
        # some SDK shapes expose usage dict differently
        usage = getattr(resp, "usage", {}) or {}
        in_tok = int(usage.get("prompt_tokens", 0))
        out_tok = int(usage.get("completion_tokens", 0))

    log.log_llm_call(
        agent=agent_name,
        model=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_s=round(dt, 6),
    )
    return resp, dt


# ----------------------------------------------------------------------
# Standalone self-test
# ----------------------------------------------------------------------

if __name__ == "__main__":
    log = RunLog(scenario_id="s01", system="rule_based", trial=1)
    log.start()
    time.sleep(0.05)
    log.add_locomotion_time(1.23)
    log.add_perception_time(0.45)
    log.goal_conditions_total = 3
    log.goal_conditions_met = 3
    log.plan_generated = "R3->D3->R2"
    log.plan_valid = True
    log.num_plan_actions = 3
    log.num_executable_actions = 3
    log.final_position = "R2"
    log.stop(success=True)
    print(json.dumps(log.to_dict(), indent=2))
