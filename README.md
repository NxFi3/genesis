# GENESIS 4 — Artificial Society Research Edition

A persistent artificial-society laboratory with a 2.5D medieval world with independent human agents, a Python simulation, a Godot 4 client, and SQLite persistence. The simulation engine remains authoritative. Shared asynchronous local inference can generate each inhabitant's own goals, executable plans, and conversations; survival and combat continue without a model.

**Research integration:** `feature/genesis-4-research`, based on validated Dynamic Threats commit `b479449`. Adds large-world generation/navigation, mutual households, generations and inherited appearance, controlled experiments, provenance-separated analytics and a local research dashboard. This is an incremental research build: underground mining, migration/founding, component invention and renderer chunk streaming remain unfinished. [Research guide](docs/research.md) · [Development log](docs/development-v4.md).

```sh
python3 -m genesis.experiments experiments/communication.json --output data/research/communication
python3 -m genesis.dashboard data/research/communication
```

Open `http://127.0.0.1:8769` for actual recorded charts and comparisons. Ollama remains optional. Offline presets measure deterministic simulation behavior, not model intelligence.

**Preserved Genesis 3 integration branch:** `feature/genesis-3-world`, preserving `813447d` and the v2 baseline. This is a tested development implementation, not a claim that the entire civilization research roadmap is complete. [Current validation](docs/validation-v3.md) · [Genesis 3 systems and remaining limits](docs/genesis3.md) · [Development log](docs/development-v3.md).

**Dynamic threats milestone:** `feature/genesis-dynamic-threats`, based on the validated Genesis 3 build `6c97f9c`. Adds optional nocturnal zombies, territorial wolves, local warnings, individual defensive choices, guarded settlements and original animated threat figures. Zombies remain **off by default**. Use **God Mode → Threats & wildlife** to enable them, adjust balance/spawn areas, or remove them immediately. [Feature guide](docs/dynamic-threats.md) · [Milestone validation](docs/validation-threats.md).

The latest version adds an orthographic 3D world, original low-poly assets, timed mining/production, crops/cooking/heat, regional weather and a persistent God Mode panel. [Genesis 3 guide and screenshots](docs/genesis3.md) · [Preserved conversation behavior](docs/communication-update.md).

## Emergent modular structures (experimental)

AI or player-authored building designs can now combine ground-level blocks and
stacked materials into original layouts without a pre-scripted "castle" action.
Builders consume physical supplies, collaborate on persistent designs, and see
the results rendered in Godot. The authoritative movement grid is still 2-D,
so this is **not** a complete Minecraft-style 3-D physics/voxel engine.
See [modular architecture details](docs/modular-architecture.md).

## Start locally

On this experimental development branch new command-line worlds default to **96 × 96** tiles; existing saves are never resized. The Godot **New world** dialog offers 48 × 30, 96 × 96, 128 × 128 and experimental 256 × 256 worlds. Use `--width 128 --height 128 --save data/large-world.sqlite` to keep a separate 128² world. Camera range and very-large-map decorative instance density were adjusted, but chunk-streamed rendering is not finished. Regional *surface* ore veins are finite and mineable; underground excavation is still missing. See [research guide](docs/research.md).

Install **Python 3.11+** and **Godot 4.x** on PATH (`godot`, `godot4`, or `godot.exe`). Python uses only its standard library; no pip packages or cloud subscriptions are needed.

```sh
git clone --branch feature/genesis-3-world https://github.com/NxFi3/genesis.git
cd genesis
python3 run.py
```

On Windows, use `python` instead of `python3`. Windows has not been exercised here. The launcher starts its own backend, waits for that process's health response, launches Godot, and saves/stops its backend when the client exits. Use `--port 8768` if another instance occupies the default 8765; the client follows the selected port.

### Two honest operating modes

**Offline deterministic mode:** local utility decisions, real survival/economy/construction/social events, and deterministic combat. It is not LLM intelligence. A fresh world defaults to this mode.

```sh
python3 run.py --offline
python3 run.py --headless --offline --ticks 10000 --save data/regression.sqlite
```

**LLM civilization mode:** every NPC is individually eligible for planning and conversation through one shared provider. Start Ollama locally and install a model:

```sh
ollama pull qwen2.5:7b
# Start `ollama serve` if your installation does not already run the service.
python3 run.py --ollama --model qwen2.5:7b
```

The default Ollama endpoint is `http://127.0.0.1:11434`. For an OpenAI-compatible local server:

```sh
python3 run.py --llm --provider openai --endpoint http://127.0.0.1:1234/v1 --model YOUR_MODEL
```

The Settings panel controls provider, endpoint, model, context character budget, timeout, concurrency, and per-agent/global budgets. Settings persist in the world save; startup flags override specified settings, and `--offline` explicitly disables saved inference. Optional `GENESIS_MODEL` and `GENESIS_OLLAMA_URL` select defaults. Optional OpenAI-compatible authentication uses `GENESIS_LLM_API_KEY` from the backend process environment, never a saved credential or chat message. Local Ollama needs no key.

Model endpoints run on the **backend machine**. A cloud machine's localhost is different from your PC's localhost. Unavailable inference is reported; ordinary simulation continues. Real Ollama dialogue was **not verified in the cloud runtime** because no model server was available. Mock and local HTTP protocol tests do not establish model quality.

## Play

- **WASD/arrows:** move Traveler in Player mode; pan the camera in Observer mode. Mouse wheel zooms, middle drag pans. Follow tracks smoothly; Focus/F centers the selection; Map/Home restores the whole map.
- **Select any inhabitant:** click a marker or use the selector. Agent/Mind/Player/Town tabs expose needs, personality, skills, goals, active plan, private memories/knowledge, relationships, equipment, inventories and settlement state.
- **Send message:** type any message to a selected inhabitant within three tiles. The reply is queued immediately; the world and UI remain responsive. Read persisted turns in Conversations. NPCs may question or disagree with you. Agent-initiated model-authored conversations appear there too. Offline social events are not presented as model dialogue.
- **Gather/Eat/Drink/Rest:** change real deposits, inventory and needs. Injured or exhausted inhabitants obtain supplies and recover without a rest/starvation deadlock. Houses/halls provide shelter and sleep destinations.
- **Build:** choose a building type and plan a project near your home store. Build Work advances a nearby real site; materials are reserved at start. Road/bridge placement lets you click a tile. Remote roads/bridges use carried personal materials rather than teleporting settlement stock; work requires site proximity. Bridges make actual water tiles traversable.
- **More actions:** offer an exchange, accept/reject pending offers, craft supported equipment at a workshop, store/retrieve resources, teach a skill or known claim, repair a selected building, propose council policies/group construction, or cast a council vote. Preconditions and refusal reasons appear in status. Direct trades use demand and survival reserves; an accepted explicit offer authorizes the exact exchange.
- **Share news:** transmits an unverified, sourced report only to the recipient. Private knowledge does not become globally known. Speaking also creates uncertain reported knowledge and individual memories. No automatic truth or obedience is implied.
- **Negotiate/Retreat/Defend/Fight:** choose your response to an actual dispute. Dispute voluntarily initiates a player encounter. Health, stamina, range, equipment, witnesses, guards and watchtowers have engine-owned consequences. No gore or forced random wars.
- **God Mode:** open the dedicated panel for regional drought/weather, temperature/intensity/duration, time/season/speed, wildlife and optional threats. Changes alter actual simulation conditions and persist in history. Survival and Industry tabs in More Actions expose the new resource chains; see the [play guide](docs/genesis3.md).
- **Observer controls:** pause, step, speed, inspect events, and switch modes. Reason Now requests cognition for one inhabitant. If a paused world's reasoning budget is exhausted, dialogue reports this instead of waiting forever; advance time or raise the budget.

Settlements can physically transport and exchange relative surpluses, complete council-approved group projects, and enact sharing/rationing/defense policies. Farms, workshops, storage, halls, wells, markets, roads and watchtowers have mechanical effects. Weather, day/night, seasons and vegetation stages affect local conditions. Agents can teach skills and reported knowledge; two predefined practical research methods improve farms or construction through real resource costs. These methods are extensible definitions, not unrestricted invention.

## Saves and headless operation

```sh
python3 run.py --headless --offline
python3 run.py --headless --ollama --model qwen2.5:7b
python3 -m genesis.server --help
```

Default save: `data/world.sqlite`. Autosave occurs every 100 ticks; Save/Load are in the client. Ctrl-C saves normal backend shutdown. `--seed 42 --population 10` selects generation settings for **new saves** (population is per settlement). Existing saves take precedence. Use a different `--save` path or New World to generate again; save first before replacing a world. Unknown or corrupt save formats report errors instead of overwriting data silently.

Version-1 worlds migrate by defaulting new fields; new saves write version 2. Snapshots retain RNG/path state, needs, private cognition/plans, active conversations, offers, cargo, projects and conflicts. In-memory events are bounded; a running Simulation incrementally archives all events to SQLite `history`. Direct `World` embedding retains only recent events unless a sink is attached. Long event archives consume disk, not growing working memory.

The local HTTP bridge exposes `GET /health`, `GET /state`, and `POST /command`. Commands are validated; model proposals cannot set inventories, coordinates, HP, or relationships directly. A storage/engine worker failure pauses the world and appears in health/state instead of silently reporting success.

## Test

```sh
python3 -m unittest discover -s tests -v
# Linux/cloud runtime checks (Godot needs writable XDG runtime directories here):
bash scripts/setup.sh
# Start a separate backend, then validate the real Godot scene:
bash scripts/check_client.sh http://127.0.0.1:8765
```

Real inference checks are opt-in and fail if the selected real model cannot complete the scenarios:

```sh
GENESIS_TEST_LIVE_LLM=1 python3 -m unittest discover -s tests -p test_live_llm.py -v
```

They are explicitly skipped in normal offline CI. Actual Godot rendering and automated mouse/keyboard input were additionally exercised under Xvfb/software OpenGL; a human desktop playtest and Windows compatibility remain unverified. For restricted cloud shells, `scripts/setup.sh` initializes writable XDG directories; the launcher does this automatically for Linux graphical startup.
