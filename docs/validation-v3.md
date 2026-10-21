# Genesis 3 validation

Branch: `feature/genesis-3-world`. Integration parent: `813447df76f80eacc04268f08640fbc7baeefc66`, which includes the requested v2 baseline and validated graphical follow-up. Main is preserved. Runtime: Linux, Python 3.12, Godot 4.6.3; no third-party Python runtime dependencies.

## Automated suite

```sh
python3 -m unittest discover -s tests -v
```

**123 discovered; 121 passed, 2 skipped, zero failures**, 21.867 seconds in the recorded final suite. All original tests remain. The two skips are explicitly opt-in real-model integration tests. Thirty-one added tests cover the new world systems, including regressions discovered by long-run execution.

| Requirement | Executed evidence | Boundary |
| --- | --- | --- |
| Finite resources, mining, carrying | Time-gated extraction, depletion, mass refusal, mine-site benefit, player continuation/cancellation, atomic net barter capacity | Abstract game units |
| Production | Ore → ingot → tools with fuel/material accounting; input escrow, pause/resume, cancellation, no duplicate output | Fourteen defined recipes; legacy instant API preserved |
| Food and agriculture | Hunting/fishing yields and stock; cooking/fire; nutrition, decay and protected storage; seeds, water, irrigation and harvest | Simplified animals/crops, not unrestricted ecology |
| Water and cold | Environmental collection, rain collector, full-pack drinking, shelter/warmth, coats/fuel mechanics | Regional reserves, not fluid simulation |
| God Mode | Regional/rectangular effects, atomic rejection, time, pause/speed, expiration, natural resume and persistence | God controls excluded from NPC schemas |
| Adaptive cognition | A fake provider receives actual local drought context and plans irrigation; the engine consumes owned water and changes moisture | Protocol/effect test, not genuine inference |
| Defense | Preserved combat regressions; walls/gates and cached paths; optional threat cap, spawn disable/removal, real HP/stamina defense | Simple non-graphic threats |
| Persistence | Active job/escrow, weather, conversation and exact continuation; old defaults; invalid climate/elevation rejection | Source saves version 2; older clients are not forward-compatible |
| Social behavior | All existing autonomous multi-turn conversation, memory, commitment, trade and failure tests still pass | Fake model providers except opt-in tests, which were skipped |

Long-run review found and corrected direct stone-gathering deadlock, missing seed retrieval, capacity withdrawal recursion, production-output hoarding and inability to drink at a source with a full pack. Tests explicitly guard these cases.

## Standalone 10,000-tick execution

```sh
python3 run.py --headless --offline --ticks 10000 --save /tmp/genesis-3-benchmark.sqlite
```

Exit 0, **20.430 seconds** in this cloud runtime, tick 10,000. Reloaded the save and ran semantic validation:

- **20/20 NPCs alive**; eight additional buildings completed.
- 3,515.87 gathered units; 2,801 consumption events/units; 576 barter units.
- Archive: **7,619 events**, including 639 mining outcomes, five harvests, 13 completed production jobs and 144 actual exchanges.
- Working events: **2,048**; maximum episodic memories: **120** per agent.
- Inventories, resources, health, climate and saved jobs passed semantic validation.

A separate test removes the player and runs another 10,000 ticks. Earlier diagnostic runs exposed defects and were not used as the successful acceptance result. Cross-settlement transport conservation remains covered by the preserved physical-shipment tests; this final seed/run is not claimed to contain a successful autonomous shipment.

This is a measured small-population cloud CPU run. No RTX 5070, large-population FPS or inference-throughput claim is made.

## Godot and real graphical execution

```sh
bash scripts/check_client.sh http://127.0.0.1:8768
godot --headless --path godot -- --smoke --flat --api=http://127.0.0.1:8768
```

Passed import, main scene against a real Python backend, the preserved 2D presentation checks and the new isometric checks. They cover inspectors, camera/focus/zoom, modes, God panel controls, settings/action popup geometry, batched vegetation, retained landscape, projected picking, local climate, 21 building assets and role figure nodes. The fallback main-scene smoke also passes.

**Actual Godot graphical execution was performed** under Xvfb and Mesa llvmpipe OpenGL. The real 3D viewport rendered and screenshots were inspected; final `--smoke --capture=...` succeeded. No concept art is presented as the implementation.

Using actual X11 pointer events, opened God Mode, chose Willowmere and drought, and clicked Apply. After advancing 100 ticks, Willowmere moisture was **0.309**, versus **0.733** in Stonehaven. The panel showed differing actual crop growth and water reserves. Saved, restored natural weather, loaded, and verified that the saved drought returned. The action is recorded in persistent history. [Screenshot](images/genesis3-regional-drought.png).

This is automated graphical/input testing in virtual Linux. A hands-on native desktop playtest, Windows/macOS run, accessibility/high-DPI review and hardware-GPU benchmark remain unverified. Software-renderer VSync reports an unsupported-mode warning; rendering and checks complete successfully.

## Live model testing

No Ollama executable/server or responding model endpoint was available at localhost ports 11434/1234. The two genuine-model checks remain **skipped**, not passed. To run them with a real installed model:

```sh
GENESIS_TEST_LIVE_LLM=1 python3 -m unittest discover -s tests -p test_live_llm.py -v
```

The full acceptance scenario involving a real player conversation and independent model-generated drought strategies therefore remains unverified. See [genesis3.md](genesis3.md) for supported systems, installation and remaining scope limits.
