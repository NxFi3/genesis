# Genesis 4 research development log

Baseline: `b479449fe3ac1e8b9b1e9fc01d320e3396293294`. Remote heads inspected on 2026-10-21: no existing Genesis 4 branch. The complete threats and 3D development lines are retained; main is unchanged.

Audit priorities: full-grid BFS and tile-by-tile noise limit larger worlds; no age progression, households or inheritance exist; wildlife lacks livestock accounting; no controlled experiment runner or provenance-separated action analytics exists. Existing async cognition, authoritative transactions and SQLite archives are usable extension points. New systems must retain additive save defaults and the original regression suite. Milestone results and precise remaining scope are recorded below as implementation proceeds.

## Milestone 1 — scalable simulation foundation

Added coordinate-seeded chunk-addressable coherent terrain, correlated deposits and deterministic exact A* for larger maps. CLI and new-world API accept map dimensions up to 512 per side; 64/128/256 maps use the coherent generator, while existing/default small worlds retain their generator and saves. Five new tests exercise terrain chunk order, river gradients, geographical resources, 256-square survival/reload and barrier-respecting routes. Full suite: 161 discovered, 159 passed, two real-model skips (25.613 s). Renderer chunk streaming and large-world rendering measurements remain outstanding; generating terrain by chunks does not imply client streaming.
