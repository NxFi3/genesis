# GENESIS 2.0 development log

Base: 999bc94. Development branch: feature/genesis-agentic-v2. Main is preserved.

## Audit and implementation priorities

1. No agent reasoning scheduler existed. Player talk blocked a request and only permitted an ineffective rest intention. Implement shared providers, bounded asynchronous inference, private agent contexts, validated executable plans, stale result rejection and observable budgets.
2. No genuine agent-to-agent conversations existed. Add model-authored multi-turn conversations, individual knowledge propagation, voluntary offers and explicit acceptance, persisted turns, and nonblocking player talk.
3. Plans/actions were player-specific, and failed actions had no useful feedback. Add generalized actor/action schemas, multi-tick execution, failure observations and replanning; retain authoritative economy/combat rules.
4. Fractional movement could snap/skip waypoints; exhausted or injured hungry agents could rest forever away from supplies. Add regression tests and correct survival priority/path execution.
5. World events and history rewrites grew without bound. Use bounded working histories/context and incremental SQLite archive persistence. Preserve version-1 saves with defaulted new fields.
6. Governance was metadata, ecology was a regen multiplier, and settlement trade did not exist. Add functional bounded world systems with invariants and tests.
7. Godot had no camera, proper dialogue history, settings, or mode visibility. Expand the existing client and verify what the available display permits.

Milestone outcomes, exact commands and limitations are recorded below as implemented. Mock protocol tests are not real inference. Desktop validation will only be claimed after graphical execution.

## Tested milestones

- Combat (`22f86d2`): removed proactive defensive strikes, applied both stances before contact, made conflict closure idempotent, validated expiring NPC strategies; eight new regressions passed.
- Client (`5cbb6e1`): camera/zoom, modes, private-state tabs, conversation history, asynchronous dialogue display, settings and metrics; actual Godot headless scene smoke passed. No desktop pixel validation claimed.
- World (`dbcad0e`, `f861b88`): corrected fractional movement and hunger/recovery deadlocks, added physical trade cargo and return transport, councils with material policy effects and approved construction, public facilities, sleep/weather/vegetation/teaching, bounded working state. Thirteen world tests passed, including 10,000 offline ticks with player absent.
- Cognition integration: every inhabitant can receive independent structured reasoning through a bounded shared executor. Private contexts, per-agent/global budgets, priority queue, epoch/revision checks, validated plans, model-authored multi-turn conversations, source/confidence-aware belief transfer, explicit offer acceptance, queued player dialogue, and incremental SQLite event archives implemented. Fourteen dedicated cognition tests passed with explicit fake providers. Full suite: **59 tests passed** in 7.591 seconds, including all original tests and the 10,000-tick regression.
- Confirmed launcher defects corrected: alternate ports now reach the matching client/backend, and readiness checks require the launched backend PID instead of accepting an unrelated server. Saved cognition settings restore unless explicitly overridden; `--offline` forces local mode.

No real inference server was installed or listening on local Ollama/OpenAI-compatible ports. Protocol/mocked-provider tests are not model quality evidence. Installing a desktop test display was unavailable due to system package permissions; graphical pixel/input validation remains unrun.

## Integration hardening and acceptance checks

- A second audit exposed and fixed oversized complete conversation contexts, forced direct trades, departing listeners during inference, withdrawals bypassing council policy, indefinitely queued dialogue when paused budgets were exhausted, and silent simulation-worker failure. Added explicit regression cases for each. Model worker shutdown is bounded logically; daemon workers retain HTTP deadlines without retaining world access.
- Extended player UI with offers/accept/reject, crafting, teaching, stock controls, repair, council policies/group projects, voting and tile placement (`d3c244b`). Headless actual-scene smoke passed against the real backend; desktop behavior is unverified.
- Remote roads/bridges consume physically carried personal material, work requires actual site proximity, and bridge completion changes terrain. Two explicit, resource-costed practical methods improve farm yield/build work; unsupported invention remains rejected. Added tests.
- Saved states now reject semantic corruption (negative inventory, invalid health/terrain/ownership), while an actual original prototype save loaded and advanced correctly.
- Final full suite: **75 discovered, 73 passed, 2 real-model tests explicitly skipped**, 8.805 seconds, zero failures. After a final small perception refinement, all 14 relevant cognition tests also passed.
- Standalone archived 10,000-tick Simulation run: 8.19 seconds, 20/20 NPCs survived, eight buildings completed, 5,637 archived events, six autonomous inter-settlement exchanges/deliveries. Working events capped at 2,048 and episodic memory at 120. These are cloud-instance observations, not target-GPU or model-quality claims.
- Both Godot import and final headless scene smoke passed, including cognition settings and action panels. Actual desktop and real local-model validation remain the next external acceptance steps. No main-branch overwrite is authorized or performed.

## Visual and communication follow-up (base b9bbcc6)

Prioritized audit: indistinguishable map entities/raw inspector dumps; no conversational motive/context targeting; reflection replacing unfinished plans; stale offer commitments; duplicate active conversations; queued old observations. Graphical review additionally exposed popup overlap and invalid numeric settings formatting.

- Visual milestone: retained textured/seasonal terrain; ten building silhouettes and construction scaffolding/progress; colored human figures/guards/traveler/incapacitation; deer/boars; conversation/cargo/work/rest/event cues; smooth follow, readable labels and fit/focus controls. Shared theme, formatted inspectors, expanded journal, player-memory section and reply status added. Corrected popup overlay, event replay and settings formatting defects. Godot headless main/presentation checks and real Xvfb rendering/input checks passed; screenshots reviewed.
- Communication milestone: optional local conversation opportunities, partner/query-relevant private context, explicit immediate social actions and engine confirmations, bounded stance effects/repetition, keep/append/reasoned-replace plan semantics, persisted work commitments, synchronized offer states, refreshed queued contexts, reply concurrency and stale-result fixes. Couriers retain cargo while talking; routine builders now walk to actual sites. Seventeen new regressions passed.
- Final suite: **92 discovered, 90 passed, 2 real-model tests skipped**, 9.768 seconds, zero failures. Offline 10,000-tick check: 6.37 seconds, bounded events/memory, eight buildings. Full original test suite retained, including the HTTP player-thread compatibility behavior.
- Actual graphical validation: Xvfb + Mesa software OpenGL, rendered screenshots and real XTest pointer/key events. Verified observer/player movement distinction, camera, inspector, journal, settings/actions; Settings Apply reached the backend. Human playtesting and native desktop platforms remain unverified.
- No live Ollama/OpenAI-compatible server responded at local model endpoints; live inference remains explicitly untested. Broader model quality and civilization scope limits remain documented.
