# Architecture and honest scope

## Ownership

`genesis/models.py` contains serializable world entities. `world.py` owns seeded generation, the clock, passable-tile pathfinding, ecology, utilities, resource transactions, building recipes, social history, and daily life. `combat.py` is an additional module with no model or rendering dependency. `actions.py` is the validated player command boundary. `persistence.py` uses transactions for snapshots and an event history table. `llm.py` is an optional, bounded Ollama adapter. `server.py` serializes world mutations under one lock; it releases the lock for model calls and discards stale dialogue results after world replacement. The GDScript client is presentation and input only.

Every default world has two geographically different settlements, ten individuals each, and one controllable player. The left settlement has more food, the right has more metal. Starting stock, resources, equipment, and buildings are explicit state. The seed controls all randomness. RNG state is saved, so loaded simulations continue identically. Runtime performance measurements are deliberately outside persistent state.

## Decisions and actions

Routine autonomy is a utility/priorities hybrid, not a full GOAP planner: urgent survival and recovery precede patrol, supply delivery, construction, socializing, and gathering. Gathering scores depend on resource demand, travel distance, and carried stock. Skills improve slowly through use. Occupations initially assign a guard and builder to each settlement; others gather flexibly. Full life stories are not scripted.

Movement uses breadth-first paths around impassable water and cardinal steps, with terrain, equipment, and base speed affecting progress and stamina. Buildings reserve materials at construction start; builders contribute work over successive ticks. Farms and workshops change inventories. No animation reports work without a state change.

Combat checks range and stamina before every strike. Equipment and defensive stance reduce damage, and watchtowers provide local protection. The lower bound is one HP. Costs occur on valid strikes only. Low health or stamina favors retreat. Trust and personality select negotiation, avoidance, defense, or fighting. A dispute ends with peace, guard mediation, separation, mutual disengagement, incapacitation, or an 80-tick maximum truce. Pair cooldown prevents immediate repeated conflict. The player chooses a response; NPCs remain autonomous. Peaceful worlds are allowed and normal.

Wildlife grazes/wanders and flees when crowded; a cornered threatened boar may defend itself. There is no hunting/animal attack UI. Guards patrol a local circuit and respond to witnessed conflicts. Settlement conflict state is peace or alert; cross-settlement disputes update diplomatic status. Stability changes are consequences, not a full political model.

## Persistence and memory

SQLite `saves(slot, version, tick, state, saved_at)` stores versioned snapshots; `history(slot, event_id, tick, kind, event)` provides a queryable record. Each transaction writes a consistent snapshot/history pair. Rewinding a slot deliberately replaces its future history. Full-world snapshots currently include all events. Agent working memory is bounded to 120 entries with preferential retention of important events; retrieval ranks importance, word overlap, and recency. The complete event history remains in the world/save. This is simple relevance retrieval, not embedding search or LLM summarization.

## Limitations and next milestones

This implementation delivers the first runnable vertical slice and the requested modular conflict foundation. It does **not** claim completion of the full civilization research roadmap.

- No migration, births, new settlement founding, technology tree, institutional evolution, elections, belief systems, or autonomous long-range diplomacy yet. Councils are seeded metadata; they do not deliberate.
- Initial guard/builder roles are assigned. Settlement growth is facility construction, not population growth. Cross-settlement travel is possible through paths and player movement, but no autonomous trade caravans or migration planner exists yet.
- Resource demand influences gathering, but prices, currency, transport contracts, offer/accept/reject negotiation, and market institutions are not implemented. Trade is a fixed equal-quantity barter primitive. Markets are inspectable facilities without separate auction behavior.
- Houses are real constructed shelter facilities; detailed occupancy and a shelter need meter remain future work. Tool production is functional, but tool durability and production chains are limited. Defensive structures are watchtowers, not walls or sieges.
- Food deposits represent simplified plant growth and regeneration, with a seasonal factor; individual plant ages, animal reproduction/feeding, climate, and ecological population balancing are absent.
- Incapacitation is temporary, never permanent death. No wounds, bleeding, ranged combat, group formations, or war campaigns. Equipment is assigned at generation; swapping, looting, and equipment crafting are not implemented.
- Natural escalation requires scarcity plus existing rivalry; ordinary seeded worlds can remain entirely peaceful. No hidden random fights are injected. A player can initiate a dispute to inspect the conflict system. The autonomous hostility trigger is intentionally conservative.
- LLM influence is limited to conversational memories, goals, and safe rest intentions. It is not a full strategic planner. No background agent-to-agent LLM conversations or long-term reflection scheduler yet. Rule-based social observations are labeled as such.
- The map is a full-world 2D observer view. Follow is a selected-agent label rather than a camera pan. There is no 3D environment, audio, art pipeline, minimap, or executable export. Windows source startup is supported in code but not tested here.
- SQLite snapshot writes and current BFS paths target small populations. Long histories and hundreds of agents require incremental event persistence and cached paths before production use. Autosave runs every 100 ticks, so abnormal termination can lose recent unsaved ticks.
- Save version 1 rejects unknown formats; no migrations from future formats or recovery of a corrupt database is promised.

Next work should add a general data-driven action planner, shelter and social utility meters, equipment production/equipping, long-range barter opportunities, and integration tests around those behaviors before adding more presentation detail. Preserve deterministic local authority when expanding LLM intentions.
