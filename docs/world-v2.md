# World, economy and institutions — v2 milestone

The original Python world is retained. This milestone adds connected mechanics, not separate demonstration scenes.

## Confirmed defects corrected

- Fractional movement previously rounded the actor into a different tile before reaching its waypoint. Replanning could cut a river corner, change both axes at once, or stop a slow actor short of its destination. Paths now retain the current waypoint until arrival; target changes first align a fractional actor with its grid segment. Cached path state is saved so loaded movement continues exactly.
- Injured agents previously prioritized rest ahead of obtaining food/water even with empty inventories, creating a permanent starvation/rest loop. Emergency needs now precede recovery, and an actor can walk to real stores or deposits before resting. Incapacitated actors still rest and rely on available supplies or neighbors.
- World event history and resolved conflicts previously grew without bound. The in-memory timeline is now a 2,048-event ring, significant per-agent memories remain capped at 120, resolved conflicts expire after their cooldown/history window, and event IDs remain monotonic after pruning. An optional event sink receives every event for server-side history persistence; standalone World use intentionally retains only the ring unless a sink is attached.
- Construction is no longer restricted to one house/storage or decorative roads. Additional houses/storage/road/bridge projects have distinct IDs and real coordinates. Construction validates land, occupancy, distance, and reserved costs.

## Mechanics

Survival includes hunger, thirst, fatigue, sleep, shelter, safety and social need. Completed houses/halls are shelter destinations; fatigued agents seek nearby shelter and sleep there. Safety reacts to local active disputes. Rule-based social encounters and actual co-presence in a public hall reduce social need. The scheduler may execute validated individual plans after emergency survival and recovery, before fallback employment routines.

World time exposes an hour/daylight cycle. A deterministic weather cycle influences movement and regeneration. Food vegetation has seedling/growing/mature/dormant growth phases; forests have regrowth stages. Winter and drought reduce production, rain improves it. Wildlife retains lightweight flee/defense behavior and births under a hard carrying capacity of 16. Detailed animal nutrition, aging and ecological balancing remain future work.

New building capabilities:

| Building | Actual effect |
| --- | --- |
| Road / bridge | On completion, changes its tile into passable road terrain; bridges must be placed on water |
| Hall | Shelter and a social venue for physically present inhabitants |
| Well | Transfers water from a nearby real water deposit into stores, limited by quantity and capacity |
| Market | Improves relationship benefit of voluntary nearby exchanges |
| Workshop | Existing resource-consuming tool production plus validated individual equipment recipes |

Completed facilities slowly lose condition; farm output scales with condition. Existing repair actions restore condition using wood. No blanket resource generation is used for equipment. Crafting consumes explicit recipe inputs at a completed nearby workshop; duplicate equipment crafting is refused. Skill teaching requires a more knowledgeable nearby teacher. Teaching a known claim transfers only that claim and its uncertainty/source, not the teacher's full private state. Supported recipes and skill progression are predefined capabilities, not unrestricted invention.

Council proposals and votes now change actual policy. Canonical policies are `share_surplus`, `rationing`, `open_trade`, and `defense`; legacy `ration`/`guarded` names are accepted as aliases. A majority of the local council must approve. Sharing/rationing controls nonemergency store withdrawals; urgent hunger still permits aid. Defense policy assigns guards to actual home-settlement disputes without creating fights. Proposals, votes, governance and policy persist. Leadership is still initially assigned; elections and constitutional design are not implemented.

Settlements can exchange relative surpluses through a courier. A shipment reserves actual origin stock into a physically carried cargo record owned by that settlement. The courier walks through the world, exchanges goods only on reaching the destination and only if stock/demand still permit it, then returns the cargo home. Failed exchanges return original property. Cargo is not duplicated into personal inventory and cannot be accidentally eaten. Resource-accounting tools must include `shipment['cargo']`. Incapacitated couriers wait and resume on recovery. Nearby nonbuilder/nonguard inhabitants can voluntarily choose a demand-scored cross-settlement opportunity every 200 ticks. This is a utility opportunity, not a scripted mandatory caravan.

## APIs for validated action execution

- `construct(agent, kind, x=None, y=None)`
- `craft(agent, item)`
- `teach(teacher, learner, topic)`
- `propose_policy(agent, policy)` → proposal ID or `None`
- `vote(agent, proposal_id, approve)`
- `request_shipment(agent, destination, offered='food', wanted='metal', amount=4)` → shipment ID or `None`

World snapshots retain conversations, agreements, governance, proposals, shipments/cargo, vegetation state, monotonic IDs, and movement waypoints. Missing new fields in v1 snapshots receive compatible defaults.

## Executed checks

`python3 -m unittest discover -s tests -p test_world_v2.py -v`: 12 tests passed. Includes a real 10,000-tick offline run with the player removed, physical shipment conservation/failure, shelter/sleep, starvation-loop regression, council policy, equipment input consumption, teaching, bridge terrain changes, bounded events, and exact save continuation.

The most recent standalone world run completed 10,000 ticks in approximately 6.06 seconds on this cloud instance, retaining 2,048 events and completing eight buildings. This is an observed local measurement, not a claim about target-machine performance or LLM throughput. The pre-existing and combat regression suite also passed after the world changes (32 tests before the added world suite).
