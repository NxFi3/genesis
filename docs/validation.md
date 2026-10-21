# Executed validation — 2026-10-21

Runtime: Linux, Python 3.12.14, Godot 4.6.3 stable official. No third-party Python dependencies. No live Ollama server.

| Check | Actual outcome |
| --- | --- |
| `python3 -m unittest discover -s tests -v` | **24 tests passed**, 5.878 seconds; no skipped tests |
| Required six combat checks | Damage, recovery, stamina, retreat, termination, active-conflict save/load all passed |
| 1,000-tick no-model test | Executed as part of the suite; meaningful gathering, consumption, social events, construction, valid positions and nonnegative stocks asserted |
| `python3 run.py --headless --ticks 1000 --save /tmp/genesis-final-validation.sqlite` | Exit 0; tick 1000 in 4.30 seconds, 3,818 events, eight completed buildings, 2,286.83 gathered units, 268 consumed units, 436 barter units |
| Real HTTP backend test | Started separate process, fetched health/state, created a dispute, saved, stepped, loaded the active conflict, rejected invalid speed, and checked shutdown persistence |
| `godot --headless --path godot --editor --import --quit` | Completed successfully after assigning writable XDG data/config/cache directories |
| `godot --headless --path godot -- --smoke` | Exit 0 against the latest real backend; client scene, 21 world agents, 30 terrain rows, inspector and scene loop checked; backend held an actual active dispute |
| `bash scripts/setup.sh` | Completed; Godot version and Python suite passed. Subsequent HTTP test increased suite total from 23 to 24 |
| Optional Ollama `/api/tags` probe | Unavailable (URLError). Live generated dialogue not verified. Disabled, network-error, malformed-response, and unsafe-intention handling passed via automated tests |
| Desktop graphical interaction / Windows | **Not run**; this machine has no desktop display. Headless scene tests do not verify actual pixel rendering, input usability, or Windows runtime behavior |

No GitHub publication or binary export was performed. Source and a local source archive are the deliverables. Reusable install_script and start_skill were saved to the cloud environment draft; draft saving is separate from publication and fresh-task restoration.

Earlier Godot attempts reported unwritable default home directories. Runtime initialization now places XDG data/config/cache beneath writable workspace paths. No verification checks were bypassed, and no source dependencies required download.
