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
