# GENESIS — The Living World

A playable first vertical slice of a medieval civilization sandbox. Python owns the deterministic simulation; Godot 4 displays the actual world and sends validated player commands. SQLite preserves individuals, memories, inventories, RNG state, and active conflicts. Routine life and combat work entirely offline.

This is an initial implementation in an empty repository, not the complete long-term civilization vision. See [scope and limitations](docs/architecture.md).

## Run

Requires Python **3.11+** and **Godot 4.x** on PATH (`godot`, `godot4`, or `godot.exe`). Tested here with Python 3.12.14 and Godot 4.6.3. There are **no pip dependencies**, cloud subscriptions, or API keys.

```sh
python3 run.py
```

On Windows use `python run.py`. Alternatively start `python -m genesis.server` and open `godot/project.godot` in Godot. The launcher owns and stops its backend, saving on normal shutdown. Keep the default backend port 8765 when using the graphical client. Backend-only commands can use `--port`.

For the cloud environment, `bash scripts/setup.sh` prepares writable runtime directories and runs the tests. A desktop display is needed for a visible window. Headless commands work without one:

```sh
python3 run.py --headless --ticks 1000 --save data/validation.sqlite
python3 run.py --headless
python3 -m unittest discover -s tests -v
```

`--seed 42 --population 10` configures a new world (population is **per settlement**). A saved world takes precedence over these generation flags. Use the New World UI or a different `--save` path to generate again. The new-world UI replaces the in-memory world; save first if you wish to retain it. Named save paths allow multiple worlds. Normal autosave is every 100 ticks; Save and Load are available in the UI. Save version 1 is atomic SQLite with queryable event history. Corrupt or unsupported saves report an error rather than silently generating over the file.

## Play and observe

- **WASD/arrows:** move the gold Traveler. Water blocks movement; the central road has a bridge. Forests and mountains slow travel.
- **Click:** inspect inhabitants, settlements, buildings, wildlife, or resource deposits. Agent inspection shows needs, reason for action, inventories, equipment, relationships, goals, and recent memories. Scroll the inspector for details.
- **Pause/Resume, Step, 1×, 5×:** observer controls. Follow highlights and labels the selected inhabitant on the full-world map.
- **Gather, Eat, Drink, Rest:** act in the world. Resource markers are harvestable within 1.6 tiles. Eat/drink consume your inventory; near home they can draw from settlement stores. Rest gradually heals when fed and hydrated.
- **Plan farm, Build work, Store wood, Get food:** settlement economy actions requiring proximity and real materials. Autonomous builders also construct facilities. Completed farms grow food; workshops consume wood and metal to produce tools; storage raises capacity; houses mark shelter; watchtowers reduce nearby damage. Initial supplies are explicit world state.
- **Trade wood/food:** offer two wood in exchange for two food to a selected nearby inhabitant. Both sides must have the stock. Rule-based autonomous trade uses the same primitive.
- **Talk:** optional real Ollama dialogue. A clear unavailable message appears if disabled or offline.
- **Share claim:** records an explicitly unverified claim, source, time, and trust-weighted confidence in the target's knowledge. Claims do not automatically become facts.
- **Dispute:** voluntarily open a nearby dispute as the player. It starts with a peaceful player intention. The target independently chooses its response. This button is not used by autonomous agents.
- **Negotiate, Retreat, Defend, Fight:** choose your response while in a conflict. The engine, not the LLM, validates and resolves all mechanics. NPCs may refuse peace, avoid contact, mediate, or disengage. No agents are forced into fights by a demonstration script.

Active disputes are drawn as amber links with a label. Actual positions and range determine contact; health bars reflect damage. Incapacitation is non-graphic and reversible through recovery. There are no gore or death effects. Nearby witnesses retain memories and adjust trust; guards patrol and can mediate. Conflicts affect settlement alert states, diplomacy, and stability, and are preserved in the event timeline and save file.

## Optional local Ollama

Install Ollama separately, start it, and pull a model, for example:

```sh
ollama pull qwen2.5:7b
python3 run.py --ollama --model qwen2.5:7b
```

Default endpoint: `http://127.0.0.1:11434`. Override with `GENESIS_OLLAMA_URL`; `GENESIS_MODEL` selects the default model. These are non-secret settings. No token is needed for a local Ollama server. The endpoint must be reachable from the machine running Python. In cloud tasks, your own computer's localhost is a different machine.

Requests have bounded context, a four-second timeout, one retry, structured JSON validation, and limited output. High-level intentions are allowlisted. Safe rest intentions can influence local decisions; dialogue never executes attacks or transfers items. Without a model, social encounters use explicitly rule-based events, not fabricated LLM speech. Live model dialogue was **not verified** in this environment; failure handling was tested.

## Validation

The automated suite covers damage, equipment, recovery, stamina, retreat, incapacitation, termination, negotiation, witness/guard response, wildlife defense, active-conflict save/load with exact continuation, movement, resource conservation, needs, construction, trade, determinism, corrupt saves, player claims, and LLM failures. It includes an actual 1,000-tick run with no model.

Godot can be checked against a running backend:

```sh
# Terminal 1
python3 -m genesis.server
# Terminal 2 (use writable XDG directories in a restricted cloud machine)
godot --headless --path godot --editor --import --quit
godot --headless --path godot -- --smoke
```

The smoke check loads the real client scene, requests the real world, and checks the inspector. Headless validation does not establish desktop visual quality or Windows compatibility. See [validation report](docs/validation.md) for executed checks.
