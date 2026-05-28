# Client Demonstration Timeline

Purpose: demonstrate the Social Tour Guide Robot workspace as an integrated system, while being honest about the venue constraint that the real TurtleBot and Pepper are on separate WiFi networks and cannot be run as one live ROS graph.

Recommended format: present the system as one product with two live stations:

- Station A: Pepper HRI on the Pepper network.
- Station B: TurtleBot locomotion/navigation on the TurtleBot network.
- Optional laptop screen: architecture diagram, ROS topics, database contents, and prerecorded/terminal evidence of the integration bridge.

Target length: 22 to 30 minutes.

## Demo Story

The client should experience a complete tour-guide workflow:

1. A visitor is greeted by Pepper.
2. The visitor asks for a tour or a subset of exhibits.
3. The system interprets the command as a high-level action.
4. The locomotion subsystem shows how the route is selected, optimized, navigated, and docked.
5. Pepper shows how the robot explains exhibits using speech, tablet content, gestures, and interaction states.
6. The team explains that these subsystems are connected through ROS messages and launch files, but are shown separately because of the two-network hardware limitation.

## Pre-Demo Setup

Do this before the clients enter.

| Time | Station | Action | Check |
| --- | --- | --- | --- |
| T-30 min | Both | Charge robots, clear floor area, mark demo route boundaries. | Robots powered, safe walking area. |
| T-25 min | TurtleBot | Start navigation stack, confirm map/localization, confirm saved waypoints in `tours.db`. | TurtleBot can localize and accept waypoint goals. |
| T-20 min | TurtleBot | Confirm full tour, subtour, QR follower if used, and docking command path. | `/tour_command`, `/tsp_command`, `/dock_command` are ready. |
| T-15 min | Pepper | Connect to Pepper network, start Pepper HRI, gesture, speech/tablet assets. | Pepper can speak, gesture, and show exhibit content. |
| T-10 min | Laptop | Open architecture slide or terminal tabs showing the major ROS interfaces. | Ready to explain the integration boundary. |
| T-5 min | Team | Assign roles: narrator, Pepper operator, TurtleBot operator, safety spotter. | Everyone knows their cue. |

## Client Timeline

| Time | Segment | What We Do | What Client Sees | Contract Functionality Shown |
| --- | --- | --- | --- | --- |
| 0:00-1:00 | Opening | Briefly state the goal: a social tour guide robot that combines autonomous tour navigation with human-friendly interaction. Mention the two-WiFi constraint upfront. | Clear framing: this is one integrated architecture, demonstrated in two live hardware blocks. | Overall project objective. |
| 1:00-2:30 | System Architecture | Show the workspace architecture: speech/LLM intent, tour manager, Nav2/waypoints, docking, Pepper HRI, gestures/tablet. Explain that ROS topics/actions are the integration contract. | Clients understand how Pepper, TurtleBot, route management, and HRI connect. | Unified control framework; subsystem integration. |
| 2:30-5:00 | Pepper Greeting | Pepper greets visitors, waves, enters listening state, and introduces itself as a tour guide. | Pepper uses speech, hand/head movement, and approachable behavior. | Greeting visitors; gestures and expressive behavior; Pepper controlled from computer/ROS. |
| 5:00-7:00 | Speech/Intent Demo | Speak or type representative commands: "start the tour", "show me the crane exhibit", "visit exhibits 0, 2, and 4", "dock". Show the parsed intent or explain the command-to-action mapping. | Natural user requests become structured robot actions. | Voice commands; high-level actions; command-to-action mapping; behaviour layer interface. |
| 7:00-9:30 | Pepper Exhibit Explanation | Trigger an exhibit explanation. Pepper speaks, gestures while explaining, and displays the exhibit image/text on the tablet. If available, show listening/speaking/idle visual states. | Client sees Pepper behaving like a guide rather than only a speaker. | Contextual information; tablet support; speech plus gesture synchronization. |
| 9:30-10:30 | Handoff To Locomotion | Narrator says: "That command would normally publish a ROS intent into the locomotion stack. Because the robots are on separate WiFi networks, we now show the receiving side live on the TurtleBot station." | Smooth transition without pretending both robots are on one network. | Integration honesty; defined interfaces. |
| 10:30-13:30 | Tour Storage And Full Tour | On TurtleBot station, show saved waypoints in `tours.db` or RViz. Start a full tour. TurtleBot follows the route through saved points. | TurtleBot navigates between tour stops using a stored route. | Manual route/waypoint creation; saved tour retrieval; autonomous tour routine; collision-free path planning. |
| 13:30-15:30 | Talk At Waypoint Trigger | At a waypoint, show that the waypoint plugin publishes the original tour waypoint index as a talk command. Narrator explains Pepper would use this ID to select the correct explanation. | Client sees how navigation timing drives exhibit speech. | Provide information at right timing; speech/navigation integration. |
| 15:30-18:00 | Optimized Subtour | Send a subset of waypoints, such as 0, 2, and 4. Show the optimized order on `/tour_waypoint_order` or in logs/RViz, then execute it. | Robot visits only requested exhibits in an optimized sequence. | Route selection; travelling-salesman-style subtour; dynamic route management. |
| 18:00-20:00 | Safety And Social Navigation | Demonstrate obstacle avoidance by placing a safe obstacle/person in the path, or show speed/proximity handling if available. Narrator explains emergency stop/failsafe behavior. | Robot slows, avoids, stops, or replans safely. | Collision avoidance; dynamic/crowded environment safety; proximity-aware behavior. |
| 20:00-22:00 | QR/Follow Optional | If reliable, show QR following or person-following proxy. If not live-ready, show the node status and explain the intended follow behavior. | Client sees a concrete perception-driven follow mode or the interface prepared for it. | Follow a target/person-style behavior; camera-driven action. |
| 22:00-24:00 | Docking / Return Home | Publish docking command or show return-to-default-position routine. If physical docking is unreliable, show the command path and staged pose behavior. | Robot returns toward its default/dock pose after tour completion. | Dock after tour or low battery; default position/orientation. |
| 24:00-26:00 | Integration Summary | Return to architecture view. Walk through one complete logical chain: speech command -> intent token -> tour/subtour command -> Nav2 waypoint action -> waypoint talk command -> Pepper speech/tablet/gesture. | Client sees that both stations are two live halves of one system. | Seamless integration of speech, navigation, and embodiment. |
| 26:00-30:00 | Questions And Backup Evidence | Invite questions. Keep terminal/RViz/tablet ready to replay any short segment. | Confidence that functions are implemented and independently testable. | Subsystem independence and testability. |

## Suggested Presenter Lines

Opening:

> Today we are demonstrating the Social Tour Guide Robot as a complete visitor experience. The contract asks for autonomous navigation, route management, speech commands, contextual explanations, gestures, and safe behavior. Because Pepper and the TurtleBot are on two separate WiFi networks, we will show the integrated workflow in two live stations connected by the same ROS message contract.

Pepper to TurtleBot handoff:

> Pepper has just performed the visitor-facing side: greeting, listening, interpreting the request, and explaining exhibits. In the fully networked setup, that intent is published into the locomotion stack. Since today the robots cannot share a network, we now trigger the same receiving interface on the TurtleBot station and show the navigation response live.

Waypoint explanation:

> When the robot reaches a waypoint, Nav2 calls our waypoint task plugin. The plugin publishes the original exhibit index, so the HRI side knows exactly which explanation, image, and gesture sequence to play.

Closing:

> The important result is that each subsystem is independently demonstrable and uses a clear interface: commands in, robot behavior out. The two-WiFi limitation changes the staging of the demo, not the architecture.

## Evidence To Keep Visible

Use whichever of these are reliable on demo day.

| Evidence | Why It Helps |
| --- | --- |
| RViz map with robot pose and goals | Shows localization, path planning, and waypoint execution. |
| `tours.db` or waypoint table | Shows persistent route/waypoint storage. |
| `/tour_waypoint_order` echo/log | Shows optimized subtour ordering and original waypoint mapping. |
| `/talk_command` echo/log | Shows navigation-to-HRI timing handoff. |
| Pepper tablet exhibit image/text | Shows multimodal explanation. |
| Pepper gesture sequence | Shows embodied HRI, not only audio output. |
| Docking command/status | Shows return-home/docking behavior. |
| Architecture slide | Makes the separate WiFi limitation understandable. |

## Backup Plan

If a live component fails, keep the client-facing story intact:

| Failed Item | Backup |
| --- | --- |
| Pepper speech recognition | Use typed/manual trigger and explain it is the same intent payload. |
| Pepper audio | Show tablet text/images and gestures while narrator reads the spoken line. |
| TurtleBot localization | Show stored map/RViz, then demonstrate command flow and saved waypoint database. |
| Full tour | Run a shorter two-waypoint route. |
| Subtour optimizer | Show the `/tour_waypoint_order` output and explain the planned route without driving all goals. |
| Docking | Show dock command publication and saved dock pose; physically return robot if needed. |
| QR/follow | Show node status/config and describe it as optional extension unless it is stable. |

## Contract Coverage Checklist

- Greet visitors and initiate tours: Pepper greeting and listening state.
- Navigate safely: TurtleBot Nav2 route with obstacle avoidance.
- Provide contextual information: Pepper exhibit explanation plus waypoint-triggered talk command.
- Voice/basic conversational prompts: speech/intent demo.
- Gestures and expressive behavior: Pepper wave, listening, pointing/explaining gestures.
- Persistent/adaptable route management: `tours.db`, route saving/retrieval, full tour.
- Optimized route selection: selected subtour with optimized waypoint order.
- Docking/default return: docking command or return-home routine.
- Subsystem independence: Pepper and TurtleBot shown separately due to WiFi, each with clear inputs/outputs.
- Integration story: intent/tour/talk-command chain explained and evidenced.

