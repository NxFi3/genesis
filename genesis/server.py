"""Local HTTP bridge. One lock owns world mutations; LLM calls run outside it."""
import argparse
import json
import math
import os
from pathlib import Path
import threading
import time
import sqlite3
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .world import World
from . import persistence, actions, combat
from .llm import Ollama
from .cognition import Scheduler
from .providers import InferenceConfig


class Simulation:
    def __init__(self, path='data/world.sqlite', seed=42, population=10, ollama=None, inference_config=None, provider=None):
        self.path = path
        self.world = persistence.load(path) if Path(path).exists() else World(seed, population)
        self.lock = threading.RLock()
        self.paused = self.world.climate.get('simulation_paused',False)
        self.speed = self.world.climate.get('simulation_speed',2.0)
        self.running = True
        self.last_ms = 0
        self.ollama = ollama or Ollama()
        self.last_dialogue = 0
        config = inference_config or InferenceConfig(enabled=self.ollama.enabled, endpoint=self.ollama.url, model=self.ollama.model)
        # Explicit command-line configuration wins; otherwise restore the saved settings.
        if inference_config is None and ollama is None and getattr(self.world, 'cognition_config', None):
            config = InferenceConfig(**self.world.cognition_config).validate()
        self.cognition = Scheduler(config, provider)
        self.pending_history = []
        self.last_error = ''
        self.worker_alive = False
        self.attach_world()
        self.pending_history.extend(self.world.events)

    def attach_world(self):
        self.world.event_sink = self.record_event
        self.world.dialogue_sink = lambda speaker, target, message, source='llm': self.cognition.speak(self.world, speaker, target, message, source)
        self.world.cognition_config = self.cognition.config.public()

    def record_event(self, event):
        self.pending_history.append(event)
        if len(self.pending_history) >= 256:
            persistence.append_history(self.pending_history, self.path)
            self.pending_history.clear()

    def save(self):
        self.world.climate['simulation_paused']=self.paused
        self.world.climate['simulation_speed']=self.speed
        self.world.cognition_config = self.cognition.config.public()
        persistence.save(self.world, self.path, pending=self.pending_history)
        self.pending_history.clear()

    def advance(self, count=1):
        for _ in range(count):
            self.world.step()
            self.cognition.pump(self.world)
            if self.world.tick % 100 == 0:
                self.save()

    def close(self):
        self.cognition.close()
        self.save()

    def run(self):
        last = time.monotonic()
        self.worker_alive = True
        try:
            while self.running:
                time.sleep(.02)
                now = time.monotonic()
                with self.lock:
                    try:
                        if not self.last_error:
                            self.cognition.pump(self.world, schedule=not self.paused)
                        if not self.paused and now-last >= 1/self.speed:
                            started = time.perf_counter()
                            self.advance()
                            self.last_ms = (time.perf_counter()-started)*1000
                            last = now
                    except Exception as exc:
                        # Keep diagnostics/control available and stop mutations after an
                        # unexpected engine/storage failure instead of silently losing the worker.
                        self.last_error = f'{type(exc).__name__}: {str(exc)[:300]}'
                        self.paused = True
        finally:
            self.worker_alive = False

    def command(self, command):
        if not isinstance(command, dict):
            raise ValueError('Expected a JSON object')
        action = command.get('action')
        with self.lock:
            if action == 'god':
                if command.get('operation') in ('pause','speed'):
                    operation=command['operation']
                    if operation=='pause':
                        if type(command.get('paused')) is not bool: raise ValueError('Pause requires a boolean')
                        self.paused=command['paused']
                    else:
                        from .environment import number
                        self.speed=number(command.get('value'),.25,20,'speed')
                    self.world.event('god_intervention',f'God Mode: {operation}.',[],intervention={k:v for k,v in command.items() if k!='action'})
                    return {'ok':True,'message':'God Mode '+operation+' applied and recorded'}
                from .environment import intervene
                return intervene(self.world,command)
            if action == 'pause':
                self.paused = bool(command.get('paused', True))
                if not self.paused:
                    self.last_error = ''
                return {'ok': True}
            if action == 'speed':
                value = float(command['speed'])
                if not math.isfinite(value):
                    raise ValueError('Speed must be finite')
                self.speed = min(20, max(.25, value))
                return {'ok': True}
            if action == 'save':
                self.save()
                return {'ok': True, 'message': 'World saved'}
            if action == 'load':
                loaded = persistence.load(self.path)
                self.cognition.invalidate()
                self.pending_history.clear()
                self.world = loaded
                self.paused=loaded.climate.get('simulation_paused',self.paused)
                self.speed=loaded.climate.get('simulation_speed',self.speed)
                if getattr(loaded, 'cognition_config', None):
                    self.cognition.configure(loaded.cognition_config)
                self.attach_world()
                return {'ok': True, 'message': 'World loaded'}
            if action == 'new':
                new_world = World(int(command.get('seed', 42)), int(command.get('population', 10)))
                self.cognition.invalidate()
                self.pending_history.clear()
                self.world = new_world
                self.attach_world()
                self.pending_history.extend(self.world.events)
                return {'ok': True, 'message': 'New world created; save to retain it'}
            if action == 'step':
                self.advance(min(100, max(1, int(command.get('count', 1)))))
                return {'ok': True}
            if action == 'configure_cognition':
                self.cognition.configure(command.get('config', {}))
                self.attach_world()
                return {'ok': True, 'message': 'Cognition settings applied', 'cognition': self.cognition.status()}
            if action == 'request_reasoning':
                ok = self.cognition.request(self.world, command.get('target'), 'explicit reasoning request', 1)
                return {'ok': ok, 'message': 'Reasoning queued' if ok else 'Disabled, unavailable agent, or already queued'}
            if action == 'talk':
                if not self.cognition.config.enabled:
                    return {'ok': False, 'message': 'LLM mode is disabled. Enable it in settings or start with --ollama.'}
                target = command.get('target')
                if target not in self.world.agents or target == 'player':
                    return {'ok': False, 'message': 'Choose an inhabitant'}
                message = str(command.get('message', '')).strip()[:1200]
                if not message:
                    return {'ok': False, 'message': 'Enter a message'}
                try:
                    cid = self.cognition.speak(self.world, 'player', target, message, 'player')
                except ValueError as exc:
                    return {'ok': False, 'message': str(exc)}
                return {'ok': True, 'queued': True, 'conversation': cid, 'message': 'Message delivered; reply queued without pausing simulation'}
            return actions.execute(self.world, command)



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
                state = {'ok': sim.worker_alive and not bool(sim.last_error), 'tick': sim.world.tick, 'pid': os.getpid(), 'worker_alive': sim.worker_alive} if self.path == '/health' else sim.world.snapshot()
                state.update(paused=sim.paused, speed=sim.speed, tick_ms=sim.last_ms, cognition=sim.cognition.status(), error=sim.last_error)
                state = copy.deepcopy(state)
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
            except (ValueError, TypeError, KeyError, OverflowError, OSError, sqlite3.Error) as exc:
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
            sim.close()
        server.server_close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--population', type=int, default=10)
    p.add_argument('--save', default='data/world.sqlite')
    p.add_argument('--ticks', type=int, help='Headless run, save, then exit')
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--ollama', '--llm', action='store_true', help='Enable shared LLM cognition')
    modes.add_argument('--offline', action='store_true', help='Force deterministic mode, overriding saved settings')
    p.add_argument('--provider', choices=['ollama', 'openai'])
    p.add_argument('--endpoint', default=os.environ.get('GENESIS_OLLAMA_URL'))
    p.add_argument('--concurrency', type=int)
    p.add_argument('--context-limit', type=int)
    p.add_argument('--timeout', type=float)
    p.add_argument('--agent-budget', type=int)
    p.add_argument('--global-budget', type=int)
    p.add_argument('--model', default=os.environ.get('GENESIS_MODEL'))
    args = p.parse_args()
    sim = Simulation(args.save, args.seed, args.population)
    overrides = {key: value for key, value in {
        'provider': args.provider, 'endpoint': args.endpoint, 'model': args.model,
        'max_concurrency': args.concurrency, 'context_limit': args.context_limit,
        'timeout': args.timeout, 'per_agent_budget': args.agent_budget, 'global_budget': args.global_budget
    }.items() if value is not None}
    if args.ollama or args.offline:
        overrides['enabled'] = args.ollama
    if overrides:
        sim.cognition.configure(overrides)
        sim.attach_world()
    if args.ticks is not None:
        start = time.perf_counter()
        if args.ticks < 0:
            p.error("ticks cannot be negative")
        sim.advance(args.ticks)
        sim.close()
        print(json.dumps({'tick': sim.world.tick, 'seconds': time.perf_counter()-start, 'stats': sim.world.stats, 'events': len(sim.world.events)}))
    else:
        try:
            serve(sim, port=args.port)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
