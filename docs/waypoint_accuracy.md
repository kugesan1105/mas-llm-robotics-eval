# Waypoint Generation Accuracy

Adaptive path planning evaluated on physical hardware.

Waypoint Generation Accuracy (WGA) quantifies the MAS's capacity to
produce optimal and executable navigation paths. This metric was validated
on the hardware platform to assess the system's ability to perform
adaptive replanning in response to environmental cues. Scenarios involving
blocked paths were used to trigger the replanning logic.

```
        Number of Correct and Feasible Waypoint Sequences
WGA  =  ─────────────────────────────────────────────────  ×  100 %
        Total Number of Generated Navigation Scenarios
```

The system was tested with various path constraints, requiring the
Waypoint Generator agent to synthesize new, valid routes based on feedback
from the robot's perception agents. As detailed in the table below, the
MAS achieved **100 % accuracy** in generating correct and feasible
waypoint sequences for all evaluated real-world scenarios. The rerouting
mechanism, orchestrated through inter-agent communication, consistently
produced valid alternative paths, demonstrating the system's reliability
in a real-world control loop.

## Accuracy of Waypoint Generation

| Scenario Description | Expected Route Logic | Generated Waypoint Sequence | Result |
|---|---|---|---|
| R2 to R1 (Door D2 closed) | Reroute via R3 and Corridor | R2 → D3 → R3 → D4 → C → D1 → R1 | Correct |
| Corridor to KUKA (in R3) | Direct path | C → D4 → R3 | Correct |
| Corridor to KUKA (Door D4 closed) | Reroute via R1 and R2 | C → D1 → R1 → D2 → R2 → D3 → R3 | Correct |
| Corridor to R2 | Path through R3 | C → D4 → R3 → D3 → R2 | Correct |
| R1 to R3 (Door D2 closed) | Reroute via Corridor | R1 → D1 → C → D4 → R3 | Correct |
| R1 to R2 (Door D2 closed) | Reroute via Corridor | R1 → D1 → C → D3 → R2 | Correct |
| **Overall Accuracy** | | | **100 %** |
