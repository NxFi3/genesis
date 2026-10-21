# Genesis 3 development log

Integration branch: `feature/genesis-3-world`.

## Repository audit

Inspected all remote heads on 2026-10-21. Main remains `999bc94`; the latest agentic branch is `813447df76f80eacc04268f08640fbc7baeefc66`, including the validated visual follow-up `52bf873`. No other graphical branch exists remotely. Genesis 3 starts from this latest state, preserving the requested baseline and subsequent fixes.

Priority risks: renderer input must use projected simulation coordinates; new inventories need backward-compatible defaults; new asynchronous production must escrow inputs; climate overrides must remain regional and persist; barriers must invalidate cached paths; God controls must never be exposed as NPC capabilities. Existing LLM queue, private memory, dialogue and SQLite history remain in place.

Milestone checks and final limits will be recorded as they run. No real-model, native-desktop or hardware performance claims are inferred from headless tests.

## Milestone 2 — orthographic 3D foundation

Implemented a SubViewport-based Godot 3D diorama with original reusable low-poly asset generators, shared meshes/materials, batched vegetation, terrain surfaces/elevation, buildings, animated figures, animals, projected picking and camera focus/pan/zoom. Existing polished inspector/journal/settings remain in place. `--flat` preserves the previous validated top-down renderer. Actual Xvfb/Mesa screenshots exposed and corrected terrain face culling; import and live-backend smoke passed. A new synthetic isometric check covers projection, batch count, retained terrain and 21 usable building assets.

## Milestones 3–7 — connected world systems

Added a checked JSON registry of resources and abstract recipes; finite timed extraction, owned mass limits, atomic barter capacity checks, resumable production with input escrow/cancellation, food transformation, spoilage, crop seeds/growth/harvest/irrigation, water collection, heating/fuel, equipment wear/repair and expanded construction. Mines improve extraction; walls and gates affect traversability and invalidate cached paths. Original food/metal/craft behavior remains available for compatibility.

Regional deterministic climate now tracks temperature, precipitation, wind, snow, drought, moisture, fertility and flood pressure. God interventions validate fully, record events and persist, including selected rectangular regions and simulation controls. Local observations feed private cognition and optional conversation opportunities; model schemas expose supported world actions, never God controls. Lightweight wildlife additions and optional capped fantasy threats remain engine-owned and disabled by default.

The new tests cover these mechanics and save migration. Long-run review caught legacy gatherers attempting direct stone gathering, missing seed retrieval, failed capacity withdrawals recursing, and workers hoarding production output. Regression fixes retain real stock accounting. Full-pack agents can eat at the communal store and drink from a nearby actual reserve without inventing carry space. A subsequent 10,000-tick run finished with 20/20 NPCs alive.

## Milestone 8 — delivered verification

Final Python suite: 123 discovered, 121 passed, two real-model tests skipped, zero failures (21.867 seconds). Standalone final 10,000 ticks: 20.430 seconds, 20/20 NPCs alive, eight additional buildings, 7,619 archived events. Archive demonstrates mining, harvest, production and actual trade. Working history/memory bounds and semantic reload validated.

Godot import, actual-backend main scene, preserved flat presentation, isometric projection/assets/local-climate checks and flat fallback smoke passed. Actual Xvfb/Mesa rendering and screenshots were reviewed. Real X11 mouse input applied Willowmere drought; after 100 ticks local moisture was 0.309 versus Stonehaven 0.733, and the saved intervention restored after load. Live Ollama, native desktop platforms and target GPU remain unverified. See `validation-v3.md` and `genesis3.md`.

## Separate milestone — Dynamic Threats & Wildlife

Created `feature/genesis-dynamic-threats` from `6c97f9c` after checking all remote heads; no later graphical branch existed. Replaced the minimal optional encounter loop with bounded nocturnal lifecycle/pursuit, safe configurable spawning, territorial predator ecology, private sightings, local alarms, sourced conversational reports and individual validated responses. Kept shared human inference, existing resource accounting, construction and combat independent of rendering. Added plan/production suspension, resource-backed defensive maintenance and save defaults/validation. Regression fixes prevent barriers from trapping nonhumans, destroyed structures from repairing themselves through periodic maintenance decay, and model intention steps from being starved by the safety fallback.

Original procedural assets/UI are preserved and extended with animated zombie/wolf geometry, watch warnings, response labels, sourced Mind reports and a dedicated threat balance tab. A separate test file adds 33 scenarios; all 156 Python tests complete with the same two real-model skips. The enabled 10,000-tick soak keeps 20/20 NPCs conscious while construction, production and trade continue. Detailed commands, evidence and limitations: [validation-threats.md](validation-threats.md).
