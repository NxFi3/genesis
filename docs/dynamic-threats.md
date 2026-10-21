# Dynamic Threats & Wildlife milestone

Branch `feature/genesis-dynamic-threats` starts at `6c97f9c`, retaining the latest validated Genesis 3 graphics and agentic work. Main and the earlier branches are preserved. Start the backend and Godot as described in the README; no new dependencies are required.

## Playing and balance

Zombies are disabled in new worlds. Open **God Mode → Threats & wildlife** to enable them. The off switch and intensity zero remove zombies and their live warnings immediately, even while paused; historical memories and events remain. Wolves are ordinary wildlife, controlled separately by territorial aggression. The panel also controls the zombie cap, spawn interval, initial grace, nocturnal behavior and a rectangular spawn area. Default automatic areas are wilderness border strips. Unsafe rectangles simply produce no spawns.

Defaults allow at most three zombies, a 360-tick initial grace and a base 180-tick spawn interval. Intensity scales spawn frequency and population below the cap; the engine enforces an absolute maximum of eight. Night is 20:00–06:00. With nocturnal behavior enabled, zombies spawn and move at night and become dormant by day. They recover stamina, search briefly after losing sight, abandon pursuit after 32 ticks without confirmation, and leave the world after 1,440 ticks. Non-graphic contact has range, stamina costs, cooldowns, armor, stance and shelter/watchtower protection. Incapacitated humans are not repeatedly attacked.

Spawn sites must be passable, at least nine tiles from settlement centers, four from buildings, seven from humans, two from wildlife and four from other zombies. Predator observer spawns and wolf births also exclude occupied settlement areas. Closed gates and walls affect movement and perception. Completing, closing or restoring a barrier cannot trap a human, living animal or zombie on an impassable tile.

The 3D client uses original low-poly zombie and wolf models, lurch/walk animation, wolf leg animation, clear threat labels, health feedback, settlement warning badges and human response labels. Select and focus a threat to inspect its actual health, stamina and activity. Agent Mind shows sourced safety reports. The existing flat renderer also renders/selects zombies. God Mode settings are recorded in history and saved.

## Independent humans and communication

Human inhabitants retain their own LLM eligibility, plans, memories, inventory and social state. Important sightings and warnings trigger the existing bounded asynchronous cognition scheduler. New validated actions are:

| Action | Meaning |
| --- | --- |
| `threat_response` | Record `flee`, `shelter`, `request_help`, `defend` or `cooperate` for a recently known threat. Immediate health/stamina still constrain safety. |
| `warn` | Signal a recently observed/reported threat to conscious humans within eight tiles. This is a mechanical alarm event, not fabricated dialogue. |
| `report_threat` | Share one known sighting with a conversation partner within three tiles, including its old location, source, timestamp and uncertainty. Supported as an explicit dialogue outcome. |
| `repel` | Resolve a nearby non-graphic defensive action against a zombie or wolf. Requires stamina, clear reach and cooldown. |

Threat conversation opportunities are grounded in the speaker's private sightings. In LLM mode, the shared provider authors the actual speech and may choose to share a structured report, discuss assistance, plan construction or decline. Heard speech becomes uncertain private knowledge; nobody receives another inhabitant's unrelated memories. Reports age and lose confidence when relayed. Guards investigate a reported position rather than following a hidden live target. Local alarms do not give a distant settlement omniscient knowledge.

Offline fallback responses vary with role, health, stamina, courage, aggression, sociability, nearby defenders and available shelter. Guards can approach and defend; civilians can flee, shelter, request help or cooperate. Useful plans and reserved production inputs persist through an interruption; elapsed plan timers and production progress pause during a threat response. Routine work resumes afterward. Strategic model responses execute through the action boundary, never by changing HP or positions directly.

Idle builders may finish protective projects, repair defenses after a local warning, or start a first watchtower when materials exist. Watchtower/wall/gate construction uses the existing material reservation, construction time and proximity rules. Repairs consume one owned wood and three stamina per ten condition. Equipment wears when repelling threats. Actual nearby witnesses can improve their opinion of a successful defender. Existing council construction, wall/gate placement and crafting remain available to models and the player. No resources or equipment appear as combat rewards.

## Wildlife and modules

`genesis/predators.py` handles lightweight wolves and shares the authoritative terrain/weather/pathfinding rules. Wolves maintain a territory, patrol preferred habitat, hunt deer/sheep when hungry, avoid groups/guards or retreat when weak, and warn nearby humans. Human contact is defensive/provoked or territorial at higher configured aggression; humans are not default prey. Predation changes prey health and consumes the carcass, preventing a second player hunting yield. Population growth remains bounded by the existing ecology cap.

`genesis/threats.py` owns zombie lifecycle, perception, combat, reports, alarms and defensive responses. Nonhuman decisions run at four-tick intervals; local human perception is bounded by range and the small population caps. Zombies and wolves never enter the inference queue. Existing SQLite version 1/2 saves receive additive safe defaults; settings, pursuit memory, wolf territories, human intentions, warnings and dialogue outcomes persist. Save validation rejects invalid resource/physical/threat states.

## Configuration example

The observer `/command` endpoint accepts the same settings as the panel. These controls are not exposed as NPC tools:

```json
{"action":"god","operation":"threats","enabled":true,"settings":{"intensity":0.5,"max_zombies":2,"spawn_interval":360,"grace_ticks":600,"night_only":true,"wolf_aggression":0.2,"spawn_regions":[[1,1,8,3]]}}
```

Omit settings to keep existing values; use an empty `spawn_regions` list for automatic borders. Validation is atomic: malformed settings change nothing. All spawn rectangles use integer simulation coordinates.

## Limits

This is a bounded optional survival challenge, not a siege or horror engine. Wolves have simple individual territories rather than simulated packs; animal reproduction and shelter protection remain abstract. Walls block paths but there is no siege demolition system. The fallback makes local safety decisions; elaborate strategic plans and natural-language conversations require a configured model. Protocol fixtures verify scheduling and validated outcomes, not model quality. Balance has been measured for specific seeded offline runs, not every world size, model or player intervention.
