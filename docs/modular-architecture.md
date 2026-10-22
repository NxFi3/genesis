# Genesis — emergent modular architecture (development branch)

**Purpose:** Allow a human/LLM resident to invent layouts from neutral parts rather
than adding a scripted castle/hut decision tree. This extends existing houses,
farms, walls, mines, roads, gates, and economic/work systems; it does not replace them.

## Simulation contract

An author proposes a text layout of up to 96 parts anchored at a nearby grid tile.
Each part has **dx,dy,z,material** relative coordinates, separated by semicolons.
Heights are 0–5 inclusive. Part materials are `stone`, `wood`, `bricks`,
`planks`, `door`, `stairs`. Parts are validated for bounds, ground occupation,
overlap with real buildings/active plans, and at least one support route to the ground.
Plans choose arbitrary geometry: corridors, enclosures, towers, courtyards, stairs,
decorations, or other creative arrangements. A proposed design changes **no**
physical block or stock on its own.

An example model-produced **plan action** is:

```json
{
  "action": "design_structure",
  "title": "A sheltered courtyard",
  "purpose": "Keep household goods sheltered",
  "x": 16,
  "y": 16,
  "layout": "0,0,0,stone;1,0,0,door;2,0,0,stone;0,0,1,bricks;1,0,1,planks"
}
```

A single plan action can register this layout; the author or other builders can
execute `{"action":"work_structure","project":"structure_1"}` once per work tick,
subject to reach, stamina, supported geometry and **owned/shared stock**. The world
stores the design, planned parts, progress and contributors across save/reload.
Buildings are genuinely completed one part at a time and material counts fall.
Builder NPCs automatically contribute to available home projects; other residents
can intentionally decide to join with `work_structure`. The LLM chooses **what,
where and why**, while the engine enforces material accounting and validity.

Additional commands: `place_block` for a single part, `remove_block`
(without refunded stock), `toggle_modular_door` (updates ground-level
passability), and `cancel_structure` (leaves already-built blocks intact).

## World integration

- Godot draws physically placed parts using instanced meshes for bulk solid
  materials, and doors/stairs as low-poly shapes. Unbuilt part locations have
  small ground/height markers. Both remain separate from legacy buildings.
- The existing 2-D fallback view and Godot action menu have structure support.
  Designs appear in the entity selector and inspector.
- LLM contexts include personally observable nearby building plans and a small
  local terrain legend, not omniscient complete maps.
- Persistence and semantic save validation include modular blocks and projects.
  Legacy saves receive empty modular collections.

## Known, intentional limits

- The authoritative locomotion/world remains 2-D tile-based. Stacked geometry
  is **visual**, not Minecraft's fully walkable 3-D voxel environment.
  Stairs do not yet provide 3-D traversal between floors.
- Ground parts block movement only when their material is solid, or when their
  door is closed. Pathfinding invalidates on placements, removals and door toggles.
- Block design size is 96 parts, global capacity 4,096 finished/reserved pieces,
  and 256 retained project records. Large blueprints may impact CPU and draw cost.
- There is no inherent predefined castle algorithm, no unrestricted crafting of
  new materials, no electricity, water piping or full structural load simulation.
- An LLM may decide to design and participate, but this is *not* a guarantee
  that a particular local model will reliably reason across long construction.
  Actual Ollama and native GPU Godot performance remain to be verified.

## Validation

```sh
python3 -m unittest discover -s tests -q
python3 -m unittest tests.test_architecture_v5 -v
python3 run.py --offline --width 96 --height 96 --save data/modular-world.sqlite
```

Open **More actions → Architecture** to author an arbitrary layout in the
graphical client. NPC-driven designs require local model mode, whereas manually
registered designs can be built collaboratively in offline mode.
