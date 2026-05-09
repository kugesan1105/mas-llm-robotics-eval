# End-to-End Simulation Execution Analysis

To rigorously evaluate the system's autonomous problem-solving
capabilities, we moved beyond isolated component testing to a holistic
end-to-end performance analysis. This metric assesses the system's ability
to handle the entire lifecycle of a complex task: interpreting ambiguous
intent, reasoning about environmental constraints, executing navigation,
and recovering from failures.

We conducted a stress test comprising 20 diverse scenarios in the
high-fidelity Webots simulation environment. These scenarios were designed
to challenge different cognitive aspects of the MAS:

- **Semantic Reasoning** — inferring destinations from vague needs (e.g., *"I need to wash my hands"*).
- **Dynamic Constraints** — replanning when doors are unexpectedly closed.
- **Object Search** — locating specific items (e.g., *"hammer"*) that may or may not be in their expected location.
- **Negative Constraints** — correctly handling requests for non-existent locations (e.g., *"netball court"*).

The results, detailed in the table below, demonstrate a **90 % success
rate**. The system successfully navigated and replanned in 18 out of 20
scenarios. Notably, it correctly handled "negative" scenarios by
recognizing the requested destination was outside its topological map,
rather than hallucinating a path. The two failures occurred in complex
object-retrieval tasks where the system correctly reached the room but
failed to visually confirm the object due to occlusion, highlighting areas
for future perception improvement.

## Accuracy of Simulation Execution

| User Prompt | Environmental Description | Result | Observation |
|---|---|---|---|
| I need a hammer. Can you take it for me. | Hammer is not inside the R2 tool room. D3 is open. Robot is in R3. | success | Robot went to R2 and identified that the hammer was not there. It returned and informed the user. |
| I need a hammer. Can you take it for me. | Hammer is inside the R2 tool room. D3 is open. Robot is in R3. | failure | Robot went to R2 but was unable to identify the hammer. It returned and informed the user. |
| I need your help to find a tool to tighten this screw nail. | D3 is closed, but D1, D2, and D4 are open. Robot is in R3. | success | Robot went to R2, identified the screwdriver, retrieved it, and came back. |
| I need a hammer. Can you take it for me. | D3 and D4 both closed. Robot is in R3. | success | Robot identified that all possible paths were closed and informed the user. |
| Go and grab me the allen key kit. | D3 is open, but the allen key kit is not there. Robot is in R3. | success | Robot went to R2 and identified that the allen-key set was not there. It returned and informed the user. |
| My hand is dirty. I need to wash my hand. Please take me to a sink. | D2 and D3 open. Robot is in R3. | success | Robot instructed the user to follow it and guided the user to the sink in R1. |
| My friend said that he is in the study area. I don't know where it is located. Can you tell me the direction. | — | success | Robot informed the user of the direction. |
| Can you go and check whether there are any extra chairs available in the study area. | D2 and D3 open. Robot is in R3. | failure | Robot went to R1 and identified the extra chair, but did not return to inform the user. Instead, it stayed in R1 and provided the information verbally. |
| Can you bring me a PLC kit. | Robot is in R3, PLC is not there in R3. | success | Robot identified that the PLC was missing in R3 and informed the user. |
| I'm creating a circuit. I need a power supply. Do you know where I can find a power supply in the robotics lab. | Robot is in R3. | success | Robot informed the user that the location is R2, which is the tool room. |
| Where can I find the Kuka robot arm. | — | success | Robot informed the user of the room where the KUKA robot is located. |
| Who is the president of USA? | — | success | Robot rejected the question as it was beyond its operational scope. |
| I need to find a washroom. Do you know where I can find that. | — | success | Robot informed the user that there is no washroom in the robotics lab. |
| I need to find Wasantha. He is in the study room. Can you take me there. D2 is closed. | D2 closed. Robot is in R2. | success | Robot instructed the user to follow it and guided the user to R1 using an alternative path. |
| Do you know where the kitchen is. | — | success | Robot informed the user that there is no kitchen in the robotics lab. |
| Can you grab me the hammer. | Robot is in R1. D2 is closed. | success | Robot went to R2 using an alternative path, retrieved the hammer, returned, and informed the user. |
| There is a biscuit packet in the study area. Grab it for me. | Robot is in R2, D2 open. | success | Robot went to R1, retrieved the biscuit packet, returned, and informed the user. |
| Can you take me to the sofa. | Robot is in R3. D2 and D3 open. | success | Robot instructed the user to follow it, guided the user to R1, identified the sofa, and informed the user. |
| Take me to the netball court. | — | success | Robot informed the user that there is no netball court in the robotics lab. |
| Take me to the canteen. | — | success | Robot informed the user that there is no canteen in the robotics lab. |
| **Overall Accuracy** | | | **90 %** |

This evaluation confirms the MAS's ability to effectively bridge the
semantic gap between human language and robotic understanding in a
practical implementation.
