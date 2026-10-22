# Genesis 4 Artificial Society Laboratory

This development edition preserves the validated Genesis 3 and Dynamic Threats world. The delivered research foundation adds coherent large maps, families/lifecycles/appearance, reproducible experiment execution, explicit action provenance and a local research viewer. Underground mining, diamonds, settlement founding/migration and component-based invention are not implemented by this milestone. Renderer chunk streaming is also unfinished: chunk-addressable terrain generation is not a claim of client streaming.

## Start and observe

New CLI worlds default to 96 × 96 tiles (previously 48 × 30), without resizing existing SQLite saves. In the Godot **New world** dialog choose 48 × 30, 96 × 96, 128 × 128 or the experimental 256 × 256 preset. Use a new save path to prevent replacing an earlier civilization. Larger maps focus the initial camera on Willowmere; the Map button still shows the whole world. Camera clipping and excessive decorative foliage on very large maps are reduced, but full terrain mesh generation, snapshot transfer and renderer chunk streaming remain performance limits. 256 × 256 is not FPS-validated on the target computer.

Regional finite surface mineral veins now appear throughout coherent large worlds. Mining consumes vein stock over multiple simulation ticks, benefits from nearby completed mine sites, and supports recipes for smelting. **Underground tunnels, vertical layers, excavation and cave networks are not implemented.** Existing worlds retain their original geology; create a new world to see the new veins.

```sh
python3 run.py --headless --offline --width 128 --height 128
python3 run.py --offline --width 64 --height 64
python3 -m genesis.experiments experiments/communication.json --output data/research/communication
python3 -m genesis.dashboard data/research/communication
```

Open `http://127.0.0.1:8769` or the Research button in Godot. The separate dashboard is read-only, uses local HTML/JavaScript/SVG and has no CDN or telemetry. It displays actual trial status, population/resources, construction/trade, inference metrics, recorded social networks, per-agent metrics and a filterable event/action log. The displayed log is bounded to the last 2,000 entries per trial; full logs remain on disk. Metrics CSV streams throughout a run; the JSON chart window retains the latest 2,048 samples. Existing output directories are never overwritten.

The normal Godot interface remains the playable world observer. The Family tab shows inherited portraits, parents, children, siblings, partners and deceased family records. Human figures reflect inherited appearance, age and supported equipment. Large maps can also be created through `--width/--height` or the new-world HTTP command. The current GUI new-world dialog still exposes its original small-world defaults.

## Experiment configuration

JSON examples live in `experiments/`. `communication.json` is an **offline deterministic social-communication** ablation, not evidence of LLM intelligence. `generations.json` accelerates demographic time and enables the clearly identified deterministic demographic fallback. `llm-local.json` is an opt-in paced Ollama pilot; install the chosen model and start Ollama first. No paid API is required.

Configuration records map dimensions/generator, initial population per settlement, seed list, repetitions, duration/sampling, resource scaling, settlement stock overrides, personality overrides, climate/threat conditions, demographic rules and provider/model/inference budgets. Group overrides are explicit factors; unspecified settings remain equal. Initial stock overrides are declared starting endowments, not production events. Model conditions require nonzero wall-clock tick pacing, preventing an unpaced headless loop from silently invalidating almost all inference. Budgets, latency, staleness, queued unfinished calls and provider-reported token counts are exported. Unknown token usage remains explicitly unavailable; no monetary costs or performance estimates are invented.

Supported ablations:

| Control | Exact scope |
| --- | --- |
| `communication` | Model dialogue, explicit sharing/teaching/reports/alarms and deterministic social encounters. Physical local perception remains. |
| `memory` | Persistent episodic and learned semantic reports; current plans, relationships, private local perceptions and physiological state remain. This is not total amnesia. |
| `shared_knowledge` | An explicitly artificial shared report pool. Off by default; ordinary worlds keep private knowledge. |
| `cooperation` | Voluntary trade/offers/aid/work pledges/shipments/teaching. Household childcare and communal survival access remain. |
| `planning` | Adoption of new model plans. Low-level routine/survival execution remains available. |

Per-tool access ablations, hierarchical model-generated subgoal graphs, generalized replay and automatic experimental randomization across arbitrary social rules remain future work. Use the manifest to inspect exactly what changed between groups.

## Provenance and scientific interpretation

`actions.jsonl` distinguishes model proposals (`proposed`, `validated`, `rejected`, adopted or preserved plans), authoritative action acceptance, failures, completed immediate actions and linked delayed production completion. It does not equate a valid structured plan with successful execution. Sources distinguish `llm`, `deterministic_fallback`, `player`, `deterministic_engine` and observer interventions. Normal physics and routine plan continuation do not imply fresh model reasoning. Audit records never become agent memories. Direct fallback activity also appears in event provenance and per-agent fallback tick counts; not every internal physiological operation is a tool call.

`events.jsonl` streams real world events. Model calls use one shared asynchronous scheduler; every living adult NPC is individually eligible, while dependent children and nonhuman threats are excluded. Requests operate on detached private context. Invalid, failed or stale proposals do not edit authoritative state. Important threat warnings and all existing non-graphic combat mechanics are retained.

Each trial writes:

- `manifest.json`: full normalized configuration, group factors, seed/repetition, source commit, simulation source hash, dirty-tree flag, Python/platform versions, timestamps, exact offline state fingerprints, outcomes and inference counters.
- `metrics.csv`: complete time series; `metrics.json`: bounded recent chart samples.
- `actions.jsonl`, `events.jsonl`, `models.jsonl`: separate audit streams.
- `agents.json`, `relationships.json`: per-agent state/metrics and actual directed social edges.
- `world.sqlite`: restartable full private world and retained history window.

`index.json` tracks batch progress and failures; `aggregate.json` contains per-seed outcomes, means, sample standard deviations and paired condition-minus-baseline differences. Repetitions of the same seed are averaged before confidence intervals so they do not become fake independent samples. A single seed has no estimated SD or confidence interval. Intervals use Student t with conservative tabulation through 31 independent seeds, then an explicitly labeled normal approximation. These summaries do not establish causal mechanisms, population-level validity or statistical significance. An agent's explanation is not verified causal reasoning.

Offline physics is reproducible for the same configuration, source and seed. Timestamps, execution time and machine throughput naturally differ. External model endpoints and asynchronous completion timing may be nondeterministic; do not claim exact LLM reproduction. `record_model_content` is false by default: model logs retain hashes/status/usage, dialogue export text is redacted and proposal text is suppressed. Opt in to full request/response logging only for data you intend to retain. The **private SQLite save still contains the world's memories and conversations** and should be reviewed before sharing. Credentials come from the existing backend environment and are not collected by the experiment logger.

## Household and demographic rules

Partnerships require adult eligibility, prior interaction/familiarity, proximity and explicit mutual acceptance. Supported tools are `propose_union`, `accept_union`, `decline_union`, `leave_union`, `create_household`, `household_transfer`, `family_plan` and `inherit`. Former household owners retain rights to stores they left behind; unions never merge personal inventories. Deposits/withdrawals and inheritance require physical proximity and validated ownership/quantities.

Birth follows two adults' explicit family intentions and an abstract gestation project. It requires household food/water, a functioning residence, present caregivers, settlement stability and population/shelter limits. It consumes actual supplies; newborn inventories are empty. Dependents cannot work, fight, make adult agreements or enter independent model cognition. Care consumes household food/water, and education transmits supported skills and sourced knowledge. Adults acquire independent cognition identities and routine capabilities. Elder natural death archives a compact identity/genealogy, ends active conflicts and leaves a physically collectable estate. There is no explicit reproductive content or medical model.

Appearance genetics are fictional seeded allele combinations for harmless visual traits only. They do not determine ability, intelligence, morality or social worth. Demographic time is configurable and separate from the retained environmental season clock; the accelerated preset is an experiment, not a realistic historical calendar. Offline household formation uses mutual interaction history and explicit deterministic eligibility, never random proximity pairing. Broader adoption/guardianship, household migration, inheritance of all special equipment/cargo obligations and sophisticated caregiving schedules remain incomplete.

## Measurement

```sh
python3 -m unittest discover -s tests -q
bash scripts/check_client.sh http://127.0.0.1:8765
python3 scripts/benchmark_research.py --size 256 --ticks 1000
```

The benchmark reports generation allocation/time, authoritative tick throughput, actual route/search costs and snapshot size. It does not report an invented rendering FPS or model throughput. See the milestone validation report for executed scenarios and measured limitations.
