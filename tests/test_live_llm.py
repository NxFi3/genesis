"""Opt-in real model tests. Never substitute a mock or cached model answer.

GENESIS_TEST_LIVE_LLM=1 python3 -m unittest discover -s tests -p test_live_llm.py -v
Optional GENESIS_MODEL / GENESIS_OLLAMA_URL select an installed local model.
"""
import os
from pathlib import Path
import tempfile
import time
import unittest

from genesis.cognition import Scheduler
from genesis.providers import InferenceConfig
from genesis.server import Simulation
from genesis import persistence

LIVE = os.environ.get('GENESIS_TEST_LIVE_LLM') == '1'


def wait_real(scheduler, world, predicate, timeout=90):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        scheduler.pump(world, schedule=False)
        if predicate():
            return
        if scheduler.metrics['failed']:
            raise AssertionError(scheduler.status())
        time.sleep(.05)
    raise AssertionError('Real model integration timed out: '+str(scheduler.status()))


@unittest.skipUnless(LIVE, 'Real inference unrun: set GENESIS_TEST_LIVE_LLM=1 with a local installed model')
class RealModelTests(unittest.TestCase):
    def config(self):
        return InferenceConfig(enabled=True, model=os.environ.get('GENESIS_MODEL', 'qwen2.5:7b'), endpoint=os.environ.get('GENESIS_OLLAMA_URL', 'http://127.0.0.1:11434'), timeout=30, max_concurrency=1, max_turns=4)

    def test_real_player_dialogue_and_memory_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            sim = Simulation(str(Path(directory)/'world.sqlite'), inference_config=self.config())
            try:
                reply = sim.command({'action': 'talk', 'target': 'a1', 'message': 'I am Traveler. I worry about food for winter. What do you know about your current supplies? Please do not invent distant events.'})
                self.assertTrue(reply['queued'])
                wait_real(sim.cognition, sim.world, lambda: sim.world.conversations[reply['conversation']]['state'] == 'waiting_player')
                sim.save()
                restored = persistence.load(sim.path)
                turns = restored.conversations[reply['conversation']]['turns']
                self.assertEqual(turns[-1]['source'], 'llm')
                self.assertTrue(turns[-1]['text'].strip())
                self.assertTrue(any('winter' in m['content'] for m in restored.agents['a1'].memories))
                print('Real model player-dialogue metrics:', sim.cognition.status()['metrics'])
            finally:
                sim.close()

    def test_real_agent_authored_multiturn_conversation(self):
        from genesis.world import World
        from genesis.planning import execute_plan
        world = World()
        a, b = world.agents['a2'], world.agents['a3']
        a.x, a.y, b.x, b.y = 9, 10, 10, 10
        scheduler = Scheduler(self.config())
        world.dialogue_sink = lambda speaker, target, message, source: scheduler.speak(world, speaker, target, message, source)
        try:
            # Explicit test goal: prose must still come from the actual model.
            scheduler.request(world, a.id, 'For this communication capability check, initiate a brief conversation using a talk action addressed to nearby a3 about your actual food and water supplies. Write your own message from your personality and context; do not invent resources.')
            wait_real(scheduler, world, lambda: a.plan_status == 'active')
            for _ in range(20):
                world.tick += 1
                execute_plan(world, a)
                scheduler.pump(world, schedule=False)
                if world.conversations:
                    break
            self.assertTrue(world.conversations, 'The real model did not create the requested supported conversation action')
            c = next(iter(world.conversations.values()))
            wait_real(scheduler, world, lambda: c['state'] == 'ended', timeout=120)
            self.assertGreaterEqual(len(c['turns']), 2)
            self.assertTrue(all(t['source'] == 'llm' and t['text'].strip() for t in c['turns']))
            self.assertTrue(b.knowledge)
            print('Real model agent-dialogue metrics:', scheduler.status()['metrics'])
        finally:
            scheduler.close()
