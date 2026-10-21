"""Exercise the real transport, process startup and shutdown persistence."""
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from genesis.persistence import load


class HTTPIntegrationTests(unittest.TestCase):
    def test_live_world_conflict_save_load_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'live.sqlite'
            with socket.socket() as available:
                available.bind(('127.0.0.1', 0))
                port = available.getsockname()[1]
            process = subprocess.Popen([sys.executable, '-m', 'genesis.server', '--port', str(port), '--save', str(path)], cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            base = f'http://127.0.0.1:{port}'
            def request(endpoint, data=None):
                req = urllib.request.Request(base+endpoint, None if data is None else json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=3) as response:
                    return json.load(response)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        self.fail('Backend exited during startup')
                    try:
                        self.assertTrue(request('/health')['ok'])
                        break
                    except OSError:
                        time.sleep(.03)
                else:
                    self.fail('Backend readiness timed out')
                request('/command', {'action': 'pause'})
                request('/command', {'action': 'new', 'seed': 42})
                state = request('/state')
                self.assertEqual(len(state['agents']), 21)
                self.assertEqual(len(state['settlements']), 2)
                self.assertTrue(request('/command', {'action': 'challenge', 'target': 'a1'})['ok'])
                request('/command', {'action': 'save'})
                request('/command', {'action': 'step', 'count': 4})
                request('/command', {'action': 'load'})
                restored = request('/state')
                self.assertEqual(restored['tick'], 0)
                self.assertEqual(restored['conflicts']['c1']['state'], 'active')
                self.assertTrue(any(e['kind'] == 'conflict_start' for e in restored['events']))
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('/command', {'action': 'speed', 'speed': 'nan'})
                self.assertEqual(error.exception.code, 400)
                request('/command', {'action': 'step', 'count': 3})
            finally:
                if process.poll() is None:
                    if sys.platform == 'win32':
                        request('/command', {'action': 'save'})
                        process.terminate()
                    else:
                        process.send_signal(signal.SIGINT)
                try:
                    output, _ = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    output, _ = process.communicate()
                    self.fail('Backend did not shut down cleanly: '+output)
            self.assertEqual(load(path).tick, 3)
            if sys.platform != 'win32':
                self.assertEqual(process.returncode, 0, output)


if __name__ == '__main__':
    unittest.main()
