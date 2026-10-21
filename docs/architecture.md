# GENESIS 2 architecture and limits

## Authority and independent agents

The existing simulation is retained. `models.py` holds persistent identity, personality, needs, skills, occupation, relationships, episodic/semantic memory, knowledge/beliefs, long/short goals, plans, commitments, observations, inventory, equipment, property and location. No neural network is created per agent.

`world.py` owns deterministic geography, movement, ecology, survival, institutions and production. `actions.py` accepts a command for an explicit actor; the HTTP API always binds player actions to Traveler. `planning.py` lists supported flat action schemas and validates structured proposals. Goals are free-form text; plans compose capabilities, not fixed life scripts. `combat.py` owns all non-graphic mechanics. `technology.py` defines a small explicit catalogue of practical methods; it does not pretend to invent arbitrary technology.

`providers.py` supports Ollama chat and OpenAI-compatible chat completions. `cognition.py` schedules a bounded priority queue, caps simultaneous requests, and enforces per-agent and global call budgets per simulation window. All human NPCs are eligible. Conversations and important information outrank ordinary goal revision. Plans continue between requests. Failure observations are fed into subsequent reasoning. Emergency survival/recovery overrides ordinary plans. Expiring validated strategic conflict responses can influence deterministic combat but cannot set damage.

Requests use detached JSON contexts and worker threads that receive no World. Daemon inference workers cannot strand process exit. In-flight HTTP requests finish or hit a timeout; cancellation invalidates their epoch, rather than claiming to abort an already-running socket. Completed proposals apply only on the simulation thread under its lock, after epoch, individual revision, age and interaction checks. World replacement/load/configuration invalidates old work. Network response sends occur outside the world lock.

The default mode is offline. Offline utility behavior is explicitly distinct from LLM planning. The source implementation and protocol tests demonstrate the mechanism; absent real inference testing, they do not establish the quality or reliability of a chosen model's decisions.

## Perception, memory and dialogue

Each context contains the agent's own personality, needs, inventory, goals, retrieved memories, beliefs, local actors/buildings, and personally observed deposits with observation timestamps. Remote agents' private state is not supplied. Guessed remote entity IDs cannot resolve hidden destinations in planned movement. Public home stores/methods are available when visiting them; nearby appearances are not another agent's private thoughts.

The complete system+serialized request has a configurable character cap. Context fitting removes old conversation records/optional detail as whole JSON fields, preserving a valid bounded request. This is a character budget, not an exact tokenizer measurement. Output is bounded and validated; unsupported steps produce meaningful errors/replanning instead of arbitrary execution.

Agent-initiated `talk` actions open conversations with model-authored speech. A responder receives its own private context plus actual recent turns. Multi-turn sessions are bounded, participants normally remain engaged locally, and emergency survival still preempts conversation. Player speech is delivered immediately and persisted; a model reply appears asynchronously. Agents may reject, question or disagree. Bounded engine interpretation of an assessment updates relationships after actual dialogue. Incoming statements are uncertain reports with source, time and confidence, not automatic truth. No omniscient knowledge broadcast occurs.

Episodic working memory is capped at 120 entries. Retrieved records rank importance, query overlap and recency. Evicted details contribute to a bounded deterministic summary; optional model reflections update bounded semantic memory and personal reflection. Knowledge, beliefs, goals, commitments, observations, working conversations and resolved social state have explicit caps. This is relevance-based retrieval and bounded consolidation, not vector search or a claim of human memory.

## Economy, world and governance

Resource transactions validate quantities, ownership, finite numbers and proximity. Direct exchange uses recipient demand/survival reserves. Explicit offers require recipient acceptance before a mechanically validated atomic exchange. Settlement trade reserves cargo in a settlement-owned shipment, transports it with a real courier, exchanges at destination and returns goods home; accounting includes shipment cargo. Food/wood regeneration and farms are explicit production sources; finite ore/stone deplete.

Construction reserves materials and completes through work. Remote roads/bridges consume carried inventory and require site proximity. Completed roads/bridges change actual terrain. Farms, workshops, storage, markets, halls, wells and defensive structures have bounded mechanical effects. Repairs consume resources. Recipes consume inputs; research consumes personal inputs and skill prerequisites at a workshop, and adds a supported public production method. Teaching transmits a skill or an actually known claim.

Councils start with community leaders and can vote on sharing, rationing, defense, open trade, and group projects. Approved policies change resource rules and guard assignments; approved construction enters a real builder queue. In LLM mode a short deliberation window allows model votes before fallback council decisions. There are no scripted political storylines or forced wars.

Terrain, roads, bridge routes, weather, seasons, day/night, vegetation phases, shelter and social/safety needs influence behavior. Wildlife uses lightweight movement, flee/defense, and births with a fixed carrying cap, rather than inference.

## Persistence and operations

SQLite saves are atomic versioned snapshots. New model fields and world fields default when restoring original version-1 worlds; unsupported versions are rejected. RNG and current path waypoints persist for exact offline continuation. Active plans, conversations, agreements, proposals, projects, cargo and conflicts survive reload. Pending inference sockets are not persisted; active conversations are eligible to be rescheduled from their latest persisted turns.

Snapshots carry a bounded 2,048-event ring. Simulation event sinks incrementally archive complete history in SQLite; saving an older world deletes its abandoned future, not its past. Corrupt saves surface errors. Autosave is every 100 ticks, so abnormal termination can lose recent unsaved state. Unexpected simulation/storage worker errors pause the world and surface in health/state. Inference errors are isolated and fall back to local behavior.

## Remaining limits

- Real Ollama player/agent dialogue and model quality were not exercised in this runtime. Opt-in real-model tests are supplied. Model-produced plans can still fail or be poor; engine rejection and replan feedback preserve world integrity.
- Godot was exercised headlessly against real HTTP state. No actual desktop display or Windows run was available. Pixel quality and desktop interaction are unverified; this is not an executable binary release.
- Initial occupations/leaders are seeded. Agents may specialize and councils make consequential decisions, but there are no elections, births/deaths of humans, migration, settlement founding, constitutions or unrestricted institutional evolution.
- Economic negotiation is resource barter, explicit offers/commitments and cargo, not currency, a full price market, debt or a contract-law simulator. Equal-quantity offers and coarse demand heuristics are intentional current limits.
- Practical research has two predefined methods. New recipes/technologies require definitions and engine support. There is no unrestricted technological invention or autonomous source-code generation.
- Agent safety and shelter meters are simplified; shelter has no detailed occupancy allocation. Equipment is a held/active list, not a complete paper-doll inventory, durability, looting or armor-slot system.
- Wildlife births are bounded and vegetation has phases, but detailed animal nutrition, aging, predator/prey balancing, climate and hydrology are absent.
- There are guards, council defense policy and local conflicts, not tactical armies, elections about war, sieges, formations or a full group-war planner. Incapacitation remains reversible; no gore or permanent combat death.
- Model reflections and free-form goals exist, but there is no embedding database, long-horizon theorem-like reasoning, or guarantee of complex emergence. Keep claims grounded in observed logs.
- Context limits are characters; budgets are calls per simulation-tick window. With time paused and budget exhausted, dialogue reports a refusal until time advances or budgets change. Actual throughput is exposed rather than predicted.
- Default testing targets about 20 inhabitants. Cached BFS paths, bounded contexts and shared inference improve scaling, but large-population and target-GPU performance have not been benchmarked. SQLite archive disk usage grows with retained history.

Prioritize genuine local-model acceptance runs, desktop interaction validation, and improvements based on observed failed plans before extending the supported action/recipe catalogue.
