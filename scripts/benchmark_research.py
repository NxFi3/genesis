#!/usr/bin/env python3
"""Measure this runtime; generation uses tracemalloc, tick timing does not."""
import argparse
import json
from pathlib import Path
import sys
import time
import tracemalloc
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from genesis.world import World
from genesis.navigation import route
from genesis.validation import validate_world

parser=argparse.ArgumentParser();parser.add_argument('--size',type=int,default=256);parser.add_argument('--ticks',type=int,default=1000);parser.add_argument('--population',type=int,default=10)
args=parser.parse_args()
tracemalloc.start();start=time.perf_counter();w=World(42,args.population,args.size,args.size);generation=time.perf_counter()-start
current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
start=time.perf_counter();s=w.settlements['a'];d=w.settlements['b'];path=route(w,(s.x,s.y),(d.x,d.y));path_seconds=time.perf_counter()-start
start=time.perf_counter();w.step(args.ticks);ticks_seconds=time.perf_counter()-start;validate_world(w)
print(json.dumps({'size':[args.size,args.size],'population_per_initial_settlement':args.population,'ticks':args.ticks,'generation_seconds_traced':generation,
 'generation_current_python_bytes':current,'generation_peak_python_bytes':peak,'ticks_seconds_untraced':ticks_seconds,'ticks_per_second':args.ticks/ticks_seconds,
 'cross_settlement_route_length':len(path) if path else None,'cross_settlement_path_seconds':path_seconds,'navigation':w.navigation,
 'live_npcs':sum(not a.player for a in w.agents.values()),'serialized_snapshot_bytes':len(json.dumps(w.snapshot(True))),'rendering_fps':None,'inference_tested':False},indent=2))
