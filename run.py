#!/usr/bin/env python3
"""Single-command launcher for Linux and Windows. No Python packages required."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import os
import json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--headless', action='store_true')
    p.add_argument('--flat', action='store_true', help='Use the preserved top-down client')
    p.add_argument('--ollama', action='store_true')
    p.add_argument('--port', type=int, default=8765)
    args, extra = p.parse_known_args()
    root = Path(__file__).resolve().parent
    backend = [sys.executable, '-m', 'genesis.server'] + (['--ollama'] if args.ollama else []) + ['--port', str(args.port)] + extra
    if args.headless:
        os.chdir(root)
        os.execv(sys.executable, backend)
    godot = shutil.which('godot') or shutil.which('godot4') or shutil.which('godot.exe')
    if not godot:
        p.error('Godot 4.x is required for graphics. Install it or use --headless.')
    if os.name == 'posix':
        runtime = root / 'data' / 'runtime'
        for key, folder in [('XDG_DATA_HOME', 'data'), ('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache')]:
            (runtime / folder).mkdir(parents=True, exist_ok=True)
            os.environ.setdefault(key, str(runtime / folder))
    process = subprocess.Popen(backend, cwd=root)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError('Backend failed to start; inspect the error above')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/health', timeout=.5) as response:
                    if json.load(response).get('pid') == process.pid:
                        break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError('Backend did not become ready')
        subprocess.run([godot, '--path', str(root/'godot'), '--', f'--api=http://127.0.0.1:{args.port}']+(['--flat'] if args.flat else []), check=True)
    finally:
        if process.poll() is None:
            # SIGINT gives Python an opportunity to atomically save before shutdown.
            if os.name == 'posix':
                import signal
                process.send_signal(signal.SIGINT)
            else:
                try:
                    req = urllib.request.Request(f'http://127.0.0.1:{args.port}/command', b'{"action":"save"}', {'Content-Type': 'application/json'})
                    urllib.request.urlopen(req, timeout=5).close()
                except OSError:
                    pass
                process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
