# Executed GENESIS 2 validation — 2026-10-21

Runtime: Linux, Python 3.12.14, Godot 4.6.3 stable official. Standard-library Python runtime. Starting commit: `999bc94`; development stays on `feature/genesis-agentic-v2`.

## Test outcomes

Current follow-up base: `b9bbcc6869f07d9afd7f52ac1cd0331c6d6d6eed`.

`python3 -m unittest discover -s tests -v` discovered **92 tests**: **90 passed, 2 skipped, 0 failed**, in **9.768 seconds**. Skips remain the two explicitly opt-in real-inference tests. All previous tests are retained. The offline 10,000-tick regression completed in **6.37 seconds**, keeping 2,048 events and completing eight buildings.

Seventeen new communication regressions exercise plan preservation/append/revision, an autonomous project discussion followed by real construction and save/load, negotiated resource-conserving barter with confirmations, private/partner-relevant memory, active conversation exclusion, stale request refresh/cancellation, agent-to-player contact, courier pauses, commitment expiry, repeated-speech limits and settings-disable recovery. These use explicit fake providers; no real model quality claim is made. A confirmed old routine-construction shortcut now has a regression proving workers must reach the site.

| Scenario | Executed evidence | Limits |
| --- | --- | --- |
| A — independent survival | `test_10000_ticks_offline_bounded_valid_world` removes the player and runs 10,000 ticks; gathering, consumption, construction, HP/stamina, positions, inventories, resource caps, and memory bounds checked. Sleep and recovery have separate tests. | Offline decisions, not model cognition |
| B — construction | `test_plan_builds_structure_with_actual_materials`: executable plan moves to wood, gathers, returns, stores, reserves materials and completes a farm. Council project test votes a hall into the actual builder queue. | Engine/structured-plan and fallback behavior; real model plan quality unverified |
| C — agent communication | `test_agent_initiated_multiturn_dialogue_and_private_information`: fake provider authors a talk plan and four source-labeled turns; only the recipient learns the report. | Real-model test explicitly skipped |
| D — player dialogue | Queued player command returns while inference is pending; private context and conversation supplied to fake provider; reply/memory survives save/load. Separate real local HTTP transport test exercises the actual server/provider route. | The HTTP model fixture is deliberately fake; real-model test explicitly skipped |
| E — trade | Gather/barter conservation, recipient survival/demand refusal, explicit offer acceptance authority, and cargo exchange/failure return tested. | Coarse barter/demand model, no currency |
| F — conflict | Existing six requested combat checks plus defense/stance regressions, NPC strategies, witnesses, mediation, timeout and incapacitation tests pass. | Deterministic non-graphic mechanics; real model strategic quality unverified |
| G — two settlements | Physical cargo escrow, walking, destination exchange, return delivery and stock conservation tested. Actual standalone 10,000-tick archive contains six autonomous shipment/exchange/delivery sequences. | Utility opportunity selection; not a full diplomatic economy |
| H — persistence | Combined active conversation, construction and conflict survives save/load and exact offline continuation. Cargo, governance, path waypoints, private state and original-save compatibility tested. | Pending sockets restart from persisted conversation state; no socket snapshot |
| I — long running | 10,000 offline ticks in the suite; separate archived Simulation run and semantic state inspection described below. | Small-population CPU runtime, not target-GPU benchmark |
| J — model failure | Disabled/network/malformed providers, stale world epochs, invalid plan output and actual fake-HTTP-server disconnection checked; world remains responsive and advances. | Disconnect test uses a fake protocol service, not a running Ollama model |

Additional regressions verify bounded whole-context JSON, private detached requests, per-agent/global budgets and concurrency, engaged listeners staying nearby while inference waits, explicit budget exhaustion while paused, governance withdrawal enforcement, hidden destination restrictions, invalid settings, storage failure pausing visibly, semantically corrupt save rejection, remote bridge construction, and resource-costed practical research.

## Previous milestone standalone archived simulation (b9bbcc6)

Executed:

```sh
python3 run.py --headless --offline --ticks 10000 --save /tmp/genesis-v2-release-check.sqlite
```

Exit 0, **8.19 seconds**, tick 10,000. Observed values:

- 20/20 NPCs survived; eight additional buildings completed.
- 4,249.75 gathered units; 2,856 consumed units; 336 barter units.
- SQLite contains 5,637 archived events, including 1,216 eat events, 1,640 drink events, and six successful settlement cargo exchanges with six completed deliveries.
- Working world retains 2,048 events; maximum episodic working memory is 120 per agent.
- Reloaded the resulting SQLite world and inspected valid state. Also loaded the actual original prototype save at tick 1,000 and advanced it to 1,002 with compatible defaults.

This is an observed cloud CPU measurement. No real reasoning-throughput or RTX 5070 performance claim is made. Runtime cognition metrics expose submitted/completed/failed/stale calls, queue/in-flight counts, latency, throughput and budget use for measurement on a real provider.

## Godot: headless and actual graphical checks

`bash scripts/check_client.sh http://127.0.0.1:8768` passed against an actual backend. This imports the project, runs the main-scene smoke and runs `godot/tests/presentation_check.gd`.

Checks cover live inspector/inventory, focus/zoom/fit, modes, journal, valid numeric settings and non-overlapping popup controls; all terrain/building silhouettes, construction, humans/wildlife, conversations/cargo, one-shot feedback, retained terrain cache, seasonal refresh and safe text formatting.

**Godot was also launched graphically**, using an Xvfb executable extracted into `/tmp` and Mesa llvmpipe software OpenGL. No system package installation or project dependency was required. Actual screenshots were inspected and are included in [the client guide](client-v2.md). Graphical validation caught and corrected terrain hidden below the panel, repeated event feedback, close buttons covering popup contents, and integer settings rendered as decimals.

Actual X11 mouse/keyboard events exercised Player/Observer switching, keyboard movement, focus, wheel zoom, Mind, Journal, actions and Settings. Observer movement did not move the player; Player movement changed backend coordinates from `(9, 11)` to `(10, 11)` in the final input run. Editing the global reasoning budget to 65 and clicking Apply changed the authoritative backend config. Graphical `--smoke --capture=...` also completed successfully with both overview and detail captures.

This is automated graphical/input validation under virtual Linux. It is not a human desktop playtest, Windows/macOS run, accessibility review, hardware-GPU benchmark or exported executable validation. No live model was connected to these visual tests.

## Real inference remains unrun

No Ollama executable/server or responding OpenAI-compatible local model was available. The two real-inference tests are opt-in and were **skipped**, never represented as passed. To run against a genuinely installed model:

```sh
GENESIS_TEST_LIVE_LLM=1 python3 -m unittest discover -s tests -p test_live_llm.py -v
```

The implementation is ready for those local acceptance checks; the full vision is not claimed complete. Remaining feature and validation limits are listed in [architecture.md](architecture.md).
