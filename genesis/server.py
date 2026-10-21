"""Local HTTP bridge. One lock owns world mutations; LLM calls run outside it."""
import argparse
import json
import math
import os
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .world import World
from . import persistence, actions, combat
from .llm import Ollama


class Simulation:
    def __init__(self, path='data/world.sqlite', seed=42, population=10, ollama=None):
        self.path = path
        self.world = persistence.load(path) if Path(path).exists() else World(seed, population)
        self.lock = threading.RLock()
        self.paused = False
        self.speed = 2.0
        self.running = True
        self.last_ms = 0
        self.ollama = ollama or Ollama()
        self.last_dialogue = 0

    def run(self):
        last = time.monotonic()
        while self.running:
            time.sleep(.02)
            now = time.monotonic()
            with self.lock:
                if not self.paused and now-last >= 1/self.speed:
                    started = time.perf_counter()
                    self.world.step()
                    self.last_ms = (time.perf_counter()-started)*1000
                    last = now
                    if self.world.tick % 100 == 0:
                        persistence.save(self.world, self.path)

    def command(self, command):
        if not isinstance(command, dict):
            raise ValueError('Expected a JSON object')
        action = command.get('action')
        with self.lock:
            if action == 'pause':
                self.paused = bool(command.get('paused', True))
                return {'ok': True}
            if action == 'speed':
                value = float(command['speed'])
                if not math.isfinite(value):
                    raise ValueError('Speed must be finite')
                self.speed = min(20, max(.25, value))
                return {'ok': True}
            if action == 'save':
                persistence.save(self.world, self.path)
                return {'ok': True, 'message': 'World saved'}
            if action == 'load':
                self.world = persistence.load(self.path)
                return {'ok': True, 'message': 'World loaded'}
            if action == 'new':
                self.world = World(int(command.get('seed', 42)), int(command.get('population', 10)))
                return {'ok': True, 'message': 'New world created; save to retain it'}
            if action == 'step':
                self.world.step(min(100, max(1, int(command.get('count', 1)))))
                return {'ok': True}
            if action != 'talk':
                return actions.execute(self.world, command)
            target = self.world.agents.get(command.get('target'))
            player = self.world.agents['player']
            if not target or target.id == player.id or combat.distance(target, player) > 3:
                return {'ok': False, 'message': 'Move within three tiles of an inhabitant'}
            if time.monotonic() - self.last_dialogue < 2:
                return {'ok': False, 'message': 'Please wait before another model request'}
            self.last_dialogue = time.monotonic()
            message = str(command.get('message', ''))[:1000]
            context = {'name': target.name, 'needs': {'hunger': target.hunger, 'thirst': target.thirst}, 'activity': target.activity, 'memories': self.world.memories_for(target.id, message), 'relationships': target.relationships, 'season': self.world.season}
            world = self.world
        result = self.ollama.converse(context, message)
        with self.lock:
            if result['available'] and self.world is world:
                # High-level goal only; no model-triggered attack, transfer, or direct mutation.
                target.goals = [{'intention': result['intention'], 'source': 'ollama', 'tick': world.tick}]
                world.relate(target, player, .02)
                world.event('dialogue', f'{player.name}: {message}\n{target.name}: {result["message"]}', [target.id, player.id])
        return {'ok': result['available'], **result}


def serve(sim, host='127.0.0.1', port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, code, data):
            payload = json.dumps(data, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path not in ('/state', '/health'):
                return self.send(404, {'error': 'Unknown endpoint'})
            with sim.lock:
                state = {'ok': True, 'tick': sim.world.tick} if self.path == '/health' else sim.world.snapshot()
                state.update(paused=sim.paused, speed=sim.speed, tick_ms=sim.last_ms)
                self.send(200, state)

        def do_POST(self):
            if self.path != '/command':
                return self.send(404, {'error': 'Unknown endpoint'})
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 8192:
                    raise ValueError('Body must be 1..8192 bytes')
                data = json.loads(self.rfile.read(length), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite number')))
                result = sim.command(data)
                self.send(200, result)
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                self.send(400, {'ok': False, 'message': str(exc)})
    server = ThreadingHTTPServer((host, port), Handler)
    worker = threading.Thread(target=sim.run, daemon=True)
    worker.start()
    try:
        print(f'GENESIS backend listening on {host}:{server.server_port}', flush=True)
        server.serve_forever()
    finally:
        sim.running = False
        worker.join(timeout=5)
        with sim.lock:
            persistence.save(sim.world, sim.path)
        server.server_close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--population', type=int, default=10)
    p.add_argument('--save', default='data/world.sqlite')
    p.add_argument('--ticks', type=int, help='Headless run, save, then exit')
    p.add_argument('--ollama', action='store_true')
    p.add_argument('--model', default=os.environ.get('GENESIS_MODEL', 'qwen2.5:7b'))
    args = p.parse_args()
    ollama = Ollama(os.environ.get('GENESIS_OLLAMA_URL', 'http://127.0.0.1:11434'), args.model, args.ollama)
    sim = Simulation(args.save, args.seed, args.population, ollama)
    if args.ticks is not None:
        start = time.perf_counter()
        sim.world.step(args.ticks)
        persistence.save(sim.world, sim.path)
        print(json.dumps({'tick': sim.world.tick, 'seconds': time.perf_counter()-start, 'stats': sim.world.stats, 'events': len(sim.world.events)}))
    else:
        try:
            serve(sim, port=args.port)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
