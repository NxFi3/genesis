# Genesis 3 development log

Integration branch: `feature/genesis-3-world`.

## Repository audit

Inspected all remote heads on 2026-10-21. Main remains `999bc94`; the latest agentic branch is `813447df76f80eacc04268f08640fbc7baeefc66`, including the validated visual follow-up `52bf873`. No other graphical branch exists remotely. Genesis 3 starts from this latest state, preserving the requested baseline and subsequent fixes.

Priority risks: renderer input must use projected simulation coordinates; new inventories need backward-compatible defaults; new asynchronous production must escrow inputs; climate overrides must remain regional and persist; barriers must invalidate cached paths; God controls must never be exposed as NPC capabilities. Existing LLM queue, private memory, dialogue and SQLite history remain in place.

Milestone checks and final limits will be recorded as they run. No real-model, native-desktop or hardware performance claims are inferred from headless tests.

## Milestone 2 — orthographic 3D foundation

Implemented a SubViewport-based Godot 3D diorama with original reusable low-poly asset generators, shared meshes/materials, batched vegetation, terrain surfaces/elevation, buildings, animated figures, animals, projected picking and camera focus/pan/zoom. Existing polished inspector/journal/settings remain in place. `--flat` preserves the previous validated top-down renderer. Actual Xvfb/Mesa screenshots exposed and corrected terrain face culling; import and live-backend smoke passed. A new synthetic isometric check covers projection, batch count, retained terrain and 21 usable building assets.
