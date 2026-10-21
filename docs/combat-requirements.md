# Additional modular physical health, combat and defense requirements

The simulation brief in project-brief.txt remains the base project. Combat must be additive, non-graphic, and work without any LLM connection. It must occur in the actual graphical simulation world, with real positions, health/stamina changes, social consequences, nearby reactions, and persistent event history. Agents independently choose negotiation, avoidance, retreat, defense, or fighting; combat must not be inevitable.

Each agent needs HP, maximum HP, stamina, hunger, thirst, fatigue, movement speed, defense rating, and basic equipment inventory. Implement recovery, damage/incapacitation, stamina costs and recovery, equipment attributes, retreat, agent combat, wildlife defense, guards and patrols, settlement conflict states, and peaceful resolution. Engine-owned mechanics must validate optional high-level model intentions.

Automated tests must cover damage calculation, health recovery, stamina consumption, retreat behavior, combat termination, and save/load during conflicts.

Implementation: genesis/models.py, genesis/combat.py, genesis/world.py, genesis/actions.py, genesis/persistence.py, and godot/main.gd. Tests: tests/test_simulation.py and tests/test_http.py. Current scope and exclusions are in architecture.md.
