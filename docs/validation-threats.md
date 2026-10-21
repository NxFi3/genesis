# Dynamic threats validation

Milestone branch: `feature/genesis-dynamic-threats`; baseline `6c97f9c`. Checks run on 2026-10-21 using Python 3.12 and Godot 4.6.3 in this cloud environment.

## Automated simulation

`python3 -m unittest discover -s tests -q`: **156 discovered, 154 passed, 2 skipped, zero failures**, 29.364 seconds. All original 123 tests remain. The 33 new scenarios cover local perception, opaque barriers, alarms, pursuit and escape, day/night behavior, safe spawn regions, grace/caps/intensity, immediate disabling while paused, personal choices and safety overrides, model intent execution, plan/production continuity, cooldown/armor outcomes, guard defense, construction/repair costs, nonhuman barrier occupancy, wolves, provider disconnection and deterministic persistence.

The conversation protocol scenario uses an explicit fixture provider: two human agents exchange multiple turns and a validated `report_threat` action transfers one sourced location into the recipient's private memory and survives SQLite reload. This is not real inference. The two real-model tests remain skipped: neither local Ollama (`11434`) nor the local OpenAI-compatible endpoint (`1234`) was reachable.

The existing 10,000-tick offline regression also passed (23.34 seconds during concurrent checks). A separate enabled-zombie soak is reproducible with:

```sh
python3 scripts/benchmark_threats.py --ticks 10000 --seed 42 --intensity 1
```

Measured result: **28.166 seconds**, 20/20 NPCs conscious at completion, peak three zombies, eight newly completed buildings, 21 completed production jobs, 244 individual trades, six settlement shipments delivered, nine repairs, 15 settlement warnings, 13 zombie spawns, five dispersed threats, two pursuit escapes and two non-graphic contact events. The run validated all world invariants every 250 ticks, saved/reloaded at tick 5,000 and continued. Working history stayed at 2,048 events and individual episodic memory at 120. No resource-quantity, physical-state or reload failures occurred. Timings include validation/checkpoint work and concurrent graphical/check activity; they are not target-hardware claims.

## Client

`bash scripts/check_client.sh http://127.0.0.1:8768` runs import, the actual main scene against the backend, preserved flat presentation, isometric assets/projection and threat-control checks. Added checks create/remove actual state-backed zombie/wolf models, select a zombie in both renderers, verify animation parts, restore saved control values and verify command payloads including the off switch.

Actual graphical execution used **Xvfb + Mesa llvmpipe**, not just the headless renderer. Real X11 pointer input changed zombie enable, intensity (1.25), cap (2), interval (60), grace (0) and a custom spawn rectangle; the corresponding authoritative HTTP state was checked. Advancing actual simulation produced a wilderness zombie, which was selected and focused in the client. Warning badges, wolf hunting labels and the original 3D landscape were visually inspected. This establishes graphical rendering/control integration in this Linux software-rendered environment, not a native Windows/macOS playtest or target-GPU FPS claim.

The final-source graphical run also disabled zombies through the visible checkbox while paused: threats disappeared without advancing tick 840. Loading the prior SQLite save restored the active threat and settings. Captured running-client evidence: [God Mode controls](images/dynamic-threats-controls.png) and [selected world zombie](images/dynamic-threat-zombie.png). These are implemented game screenshots, not concept art.

Remaining limits and supported rules are documented in [the feature guide](dynamic-threats.md). Live Ollama conversation quality, broad multi-seed balance and human usability testing remain unverified.
