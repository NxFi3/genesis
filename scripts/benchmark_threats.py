#!/usr/bin/env python3
"""Reproducible offline threat soak, invariant checks and SQLite checkpoint.

Run from the repository: python3 scripts/benchmark_threats.py --ticks 10000
No inference is performed. Results describe this machine and seed only.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from genesis import environment, persistence
from genesis.validation import validate_world
from genesis.world import World


def run(ticks, seed, intensity):
    world = World(seed)
    counts = Counter()
    world.event_sink = lambda event: counts.update([event['kind']])
    environment.intervene(world, {'operation':'threats','enabled':True,'settings':{'intensity':intensity}})
    peak = 0
    checkpoints = 0
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'threat-soak.sqlite'
        for i in range(ticks):
            world.step()
            peak = max(peak, len(world.threats))
            if (i+1) % 250 == 0: validate_world(world)
            if (i+1) == ticks//2:
                persistence.save(world,path)
                loaded = persistence.load(path)
                assert loaded.snapshot(True) == world.snapshot(True), 'Checkpoint changed state'
                world = loaded
                world.event_sink = lambda event: counts.update([event['kind']])
                checkpoints += 1
        validate_world(world)
    return {'ticks':ticks,'seed':seed,'intensity':intensity,'seconds':round(time.perf_counter()-started,3),
            'mode':'offline deterministic; no inference','conscious_npcs':sum(not a.incapacitated for a in world.agents.values() if not a.player),
            'npc_count':sum(not a.player for a in world.agents.values()),'completed_buildings':sum(b.complete for b in world.buildings.values()),
            'peak_zombies':peak,'working_events':len(world.events),'max_agent_memories':max(len(a.memories) for a in world.agents.values()),
            'checkpoints':checkpoints,'events':dict(sorted(counts.items()))}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ticks',type=int,default=10000)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--intensity',type=float,default=1.)
    args=parser.parse_args()
    if args.ticks<2:parser.error('Use at least two ticks')
    print(json.dumps(run(args.ticks,args.seed,args.intensity),indent=2))
