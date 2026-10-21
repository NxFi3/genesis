"""Real local HTTP transport with a deliberately fake model protocol server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request


class ProviderHTTPTests(unittest.TestCase):
    def test_async_player_reply_over_real_http_and_model_disconnect(self):
        calls = []
        class FakeModel(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append(body)
                time.sleep(.12)
                content = {'goal': 'Protocol test goal', 'plan': [{'action': 'observe'}], 'speech': 'This is a fake-provider protocol test reply.', 'end_conversation': True}
                raw = json.dumps({'message': {'content': json.dumps(content)}}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except BrokenPipeError:
                    pass
        fake = ThreadingHTTPServer(('127.0.0.1', 0), FakeModel)
        fake_thread = threading.Thread(target=fake.serve_forever, daemon=True)
        fake_thread.start()
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as available:
                available.bind(('127.0.0.1', 0))
                port = available.getsockname()[1]
            path = Path(directory)/'world.sqlite'
            process = subprocess.Popen([sys.executable, '-m', 'genesis.server', '--port', str(port), '--save', str(path), '--ollama', '--model', 'fake-protocol-test', '--endpoint', f'http://127.0.0.1:{fake.server_port}', '--timeout', '.2'], cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            def request(endpoint, data=None):
                req = urllib.request.Request(f'http://127.0.0.1:{port}'+endpoint, None if data is None else json.dumps(data).encode(), {'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=3) as response:
                    return json.load(response)
            try:
                deadline = time.monotonic()+5
                while True:
                    if process.poll() is not None:
                        self.fail('Backend exited early')
                    try:
                        request('/health')
                        break
                    except OSError:
                        if time.monotonic()>deadline:
                            raise
                        time.sleep(.02)
                request('/command', {'action': 'pause'})
                start = time.monotonic()
                reply = request('/command', {'action': 'talk', 'target': 'a1', 'message': 'Remember the silver orchard report.'})
                self.assertTrue(reply['queued'])
                self.assertLess(time.monotonic()-start, .2)
                deadline = time.monotonic()+5
                while time.monotonic()<deadline:
                    state = request('/state')
                    c = state['conversations'][reply['conversation']]
                    if c['state'] == 'waiting_player':
                        break
                    time.sleep(.03)
                self.assertEqual(c['state'], 'waiting_player', c)
                self.assertEqual(c['turns'][-1]['source'], 'llm')
                self.assertIn('fake-provider', c['turns'][-1]['text'])
                self.assertTrue(calls)
                request('/command', {'action': 'save'})
                fake.shutdown()
                fake.server_close()
                request('/command', {'action': 'configure_cognition', 'config': {'per_agent_budget': 100, 'reasoning_interval': 5}})
                request('/command', {'action': 'talk', 'target': 'a1', 'message': 'Will you reply after the test server disconnects?'})
                deadline = time.monotonic()+3
                while time.monotonic()<deadline:
                    state = request('/state')
                    if state['cognition']['metrics']['failed']:
                        break
                    time.sleep(.02)
                self.assertGreater(state['cognition']['metrics']['failed'], 0)
                before = state['tick']
                request('/command', {'action': 'step', 'count': 10})
                self.assertEqual(request('/state')['tick'], before+10)
                self.assertTrue(request('/health')['ok'])
            finally:
                fake.shutdown()
                fake.server_close()
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
                    self.fail(output)
            if sys.platform != 'win32':
                self.assertEqual(process.returncode, 0, output)
