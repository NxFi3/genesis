# Genesis 2 client milestone

The Godot client remains a presentation/input layer over the Python simulation. Its camera and interpolated display positions never mutate authoritative positions.

## Interaction

- Player / Observer switches input modes. Player mode moves the Traveler using held WASD/arrows. Observer mode pans the camera with the same keys and disables player action buttons.
- Mouse wheel zooms around the cursor. Middle drag pans. Follow centers the selected inhabitant; Reset camera restores the complete world map. Map drawing is clipped to its viewport so zoomed terrain cannot obscure controls.
- Click entities or use the selector. Agent, Mind, Player, and Town inspector tabs separate needs/activity, private goals/plans/memories, player inventory/equipment/property, and settlement state.
- The Conversations tab displays persisted turns from the selected inhabitant's conversations, including speaker, tick, and source. It labels generated turns by source and never fabricates a model response. Talk opens this history tab and queues a request; polling, camera control, and rendering continue while inference runs.
- The Settings popup controls provider, model, backend endpoint, context limit, timeout, concurrency, per-agent budget, and global budget. Apply uses the engine's `configure_cognition` command; the backend validates settings. Credentials are deliberately absent from this form. Cognition mode and measured request counts/latency/throughput are visible in the header. An enabled mode alone does not prove a model is reachable.
- Player actions include gathering, consumption, rest, trade, negotiation and combat responses, supplies, building selection, and construction work. The engine remains responsible for eligibility, resources, duration, and outcomes.
- New World explicitly replaces in-memory state; Save first to preserve it. Save and Load controls remain available in either mode.

Default backend: `http://127.0.0.1:8765`. To point the Godot client at another local backend, use `godot --path godot -- --api=http://127.0.0.1:8767`.

## Executed checks

Godot 4.6.3 on Linux imported the project and executed the actual main scene against a running Python backend with a fresh two-settlement world. The headless smoke request retrieved live state and asserted that the inspector and player inventory populated, zoom changed correctly, player/observer switches worked, and the cognition settings popup opened with a model value.

```sh
# Start a separate backend with an independent test save.
python3 -m genesis.server --port 8767 --save /tmp/genesis-v2-client-agent-final.sqlite
# In another shell, assign writable XDG directories if required by the machine.
godot --headless --path godot -- --smoke --api=http://127.0.0.1:8767
```

Result: exit 0, `GENESIS 2 client smoke passed: live state, inspector, inventory, camera, modes and cognition settings`.

No desktop display or Xvfb is installed in this execution environment. Actual pixel rendering, mouse/keyboard usability in a graphical window, and desktop Windows execution are **not verified**. The scene smoke is not represented as graphical acceptance or real-model integration.
