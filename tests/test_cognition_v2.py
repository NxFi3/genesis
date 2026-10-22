"""Protocol/scheduler tests use explicit fake providers, never claim real inference."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from genesis.cognition import Scheduler, SYSTEM
from genesis.memory import context, learn
from genesis.providers import InferenceConfig, generate
from genesis.planning import validate_plan, execute_plan
from genesis.server import Simulation
from genesis.world import World
from genesis import actions, persistence


def result(goal='Secure food for a difficult winter', plan=None, speech='', **extra):
    return {'ok': True, 'data': {'goal': goal, 'plan': plan if plan is not None else [{'action': 'observe'}], 'speech': speech, **extra}}


def drain(scheduler, world, predicate, timeout=3, schedule=False):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        scheduler.pump(world, schedule=schedule)
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError('Scheduler did not reach expected state: '+str(scheduler.status()))


class CognitionV2Tests(unittest.TestCase):
    def setUp(self):
        self.w = World(42)
        self.schedulers = []

    def scheduler(self, provider, **config):
        scheduler = Scheduler(InferenceConfig(enabled=True, **config), provider)
        self.schedulers.append(scheduler)
        return scheduler

    def tearDown(self):
        for scheduler in self.schedulers:
            scheduler.close()

    def test_every_inhabitant_has_independent_context_and_reasoning(self):
        seen = []
        def provider(config, system, payload):
            seen.append(payload['agent']['identity']['id'])
            return result()
        scheduler = self.scheduler(provider, max_concurrency=3)
        drain(scheduler, self.w, lambda: scheduler.metrics['completed'] >= 20, schedule=True)
        self.assertEqual(set(seen), set(self.w.agents)-{'player'})
        self.assertTrue(all(a.reasoning_count >= 1 for a in self.w.agents.values() if not a.player))
        self.w.agents['a0'].goals[-1]['description'] = 'My private goal'
        self.assertNotEqual(self.w.agents['a1'].goals[-1]['description'], 'My private goal')

    def test_nonblocking_inference_concurrency_and_budget(self):
        gate = threading.Event()
        active, maximum = 0, 0
        lock = threading.Lock()
        def provider(*args):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(active, maximum)
            gate.wait(1)
            with lock:
                active -= 1
            return result()
        scheduler = self.scheduler(provider, max_concurrency=2, global_budget=2)
        try:
            before = time.monotonic()
            scheduler.pump(self.w)
            self.w.step(20)
            scheduler.pump(self.w)
            self.assertLess(time.monotonic()-before, .5)
            self.assertEqual(self.w.tick, 20)
            self.assertLessEqual(len(scheduler.inflight), 2)
            gate.set()
            drain(scheduler, self.w, lambda: scheduler.metrics['completed'] == 2)
            self.assertLessEqual(maximum, 2)
            self.assertEqual(scheduler.metrics['submitted'], 2)
            self.assertLessEqual(len(scheduler.queue), scheduler.config.max_queue)
        finally:
            gate.set()

    def test_private_knowledge_context_and_detached_request(self):
        a, b = self.w.agents['a2'], self.w.agents['b2']
        learn(a, 0, 'The old oak marks a hidden spring', 'player', .4)
        self.assertNotIn('hidden spring', json.dumps(context(self.w, b)))
        scheduler = self.scheduler(lambda *args: result())
        scheduler.request(self.w, a.id)
        original = copy.deepcopy(scheduler.queue[0].context)
        a.personality['aggression'] = 1
        a.inventory['wood'] += 100
        self.assertEqual(scheduler.queue[0].context, original)
        self.assertNotIn('stores', context(self.w, b)['settlement'] if abs(b.x-self.w.settlements[b.home].x)>3 else {})

    def test_invalid_model_output_rejected_and_replans(self):
        scheduler = self.scheduler(lambda *args: result(plan=[{'action': 'set_hp', 'hp': 999}]))
        a = self.w.agents['a2']
        scheduler.request(self.w, a.id)
        drain(scheduler, self.w, lambda: scheduler.metrics['failed'] == 1)
        self.assertEqual(a.hp, 100)
        self.assertFalse(a.plan)
        self.assertIn('rejected', a.plan_error)
        with self.assertRaises(ValueError):
            validate_plan({'goal': 'cheat', 'plan': [{'action': 'observe', 'inventory': 999}]})

    def test_failed_plan_error_triggers_reconsideration(self):
        a = self.w.agents['a2']
        a.plan, a.plan_status = [{'action': 'gather', 'resource': 'missing'}], 'active'
        # Move away from all deposits so generic gather cannot hide missing IDs.
        a.x, a.y = 4, 4
        self.assertTrue(execute_plan(self.w, a))
        self.assertEqual(a.plan_status, 'failed')
        self.assertTrue(a.plan_error)
        self.assertEqual(a.next_reason_tick, self.w.tick)

    def test_stale_result_after_world_reset_and_agent_revision(self):
        gate = threading.Event()
        def provider(*args):
            gate.wait(1)
            return result(goal='Old world goal')
        scheduler = self.scheduler(provider)
        try:
            scheduler.request(self.w, 'a2')
            scheduler.pump(self.w, schedule=False)
            scheduler.invalidate()
            gate.set()
            drain(scheduler, self.w, lambda: not scheduler.inflight)
            self.assertFalse(self.w.agents['a2'].goals)
            self.assertGreaterEqual(scheduler.metrics['stale'], 1)
        finally:
            gate.set()

    def test_model_failure_does_not_stop_survival(self):
        scheduler = self.scheduler(lambda *args: {'ok': False, 'error': 'Ollama disconnected'})
        scheduler.request(self.w, 'a2')
        self.w.step(100)
        drain(scheduler, self.w, lambda: scheduler.metrics['failed'] == 1)
        self.w.step(100)
        self.assertEqual(self.w.tick, 200)
        self.assertGreater(self.w.stats['gathered'], 0)
        self.assertIn('disconnected', scheduler.metrics['last_error'])

    def test_agent_initiated_multiturn_dialogue_and_private_information(self):
        a, b, outsider = self.w.agents['a2'], self.w.agents['a3'], self.w.agents['b2']
        a.x, a.y, b.x, b.y = 9, 10, 10, 10
        learn(a, 0, 'Stonehaven needs wood', 'observation', .8)
        def provider(config, system, payload):
            aid = payload['agent']['identity']['id']
            if 'conversation' not in payload:
                return result(plan=[{'action': 'talk', 'target': b.id, 'message': 'I heard Stonehaven needs wood. Shall we trade?'}])
            return result(goal='Explore a trade proposal', plan=[{'action': 'observe'}], speech=f'{aid}: I will consider that report, but want evidence.', stance='question', end_conversation=False)
        scheduler = self.scheduler(provider, max_turns=4)
        self.w.dialogue_sink = lambda speaker, target, message, source: scheduler.speak(self.w, speaker, target, message, source)
        scheduler.request(self.w, a.id)
        drain(scheduler, self.w, lambda: a.plan_status == 'active')
        self.assertTrue(execute_plan(self.w, a))
        c = next(iter(self.w.conversations.values()))
        drain(scheduler, self.w, lambda: c['state'] == 'ended')
        self.assertEqual(len(c['turns']), 4)
        self.assertTrue(all(t['source'] == 'llm' for t in c['turns']))
        self.assertTrue(any('Stonehaven needs wood' in x['claim'] for x in b.knowledge))
        self.assertFalse(any('Stonehaven needs wood' in x['claim'] for x in outsider.knowledge))
        self.assertLess(b.relationships[a.id]['trust'], 0)

    def test_player_dialogue_queued_context_and_persisted_memory(self):
        gate = threading.Event()
        seen = []
        def provider(config, system, payload):
            seen.append(payload)
            gate.wait(1)
            return result(speech='I remember your concern about the winter stores.', stance='question')
        with tempfile.TemporaryDirectory() as directory:
            sim = Simulation(str(Path(directory)/'world.sqlite'), inference_config=InferenceConfig(enabled=True), provider=provider)
            try:
                start = time.monotonic()
                answer = sim.command({'action': 'talk', 'target': 'a1', 'message': 'Please inspect the winter stores, not rumors.'})
                self.assertTrue(answer['queued'])
                sim.cognition.pump(sim.world, schedule=False)
                self.assertLess(time.monotonic()-start, .2)
                sim.world.step(1)
                gate.set()
                drain(sim.cognition, sim.world, lambda: sim.cognition.metrics['completed'] == 1)
                self.assertEqual(seen[0]['agent']['identity']['id'], 'a1')
                self.assertIn('personality', seen[0]['agent']['identity'])
                self.assertIn('winter stores', seen[0]['conversation']['turns'][0]['text'])
                sim.save()
                loaded = persistence.load(sim.path)
                self.assertTrue(any('winter stores' in m['content'] for m in loaded.agents['a1'].memories))
                c = loaded.conversations[answer['conversation']]
                self.assertEqual(c['state'], 'waiting_player')
                self.assertEqual(c['turns'][-1]['source'], 'llm')
            finally:
                gate.set()
                sim.close()

    def test_plan_builds_structure_with_actual_materials(self):
        a = self.w.agents['a2']
        a.x, a.y = 9, 10
        self.w.settlements[a.home].inventory['wood'] = 0
        r = self.w.resources['a_r2']
        a.plan = [{'action': 'move', 'target': r.id}] + [{'action': 'gather', 'resource': r.id}]*3 + [
            {'action': 'move', 'target': a.home}, {'action': 'store', 'kind': 'wood', 'amount': 8},
            {'action': 'build', 'kind': 'farm'}, {'action': 'work', 'building': 'a_farm'}]
        a.plan_status = 'active'
        quantity = r.quantity
        for _ in range(150):
            self.w.tick += 1
            execute_plan(self.w, a)
            # Rest is a real engine action; test avoids other agents consuming materials.
            if a.stamina < 10:
                from genesis.combat import recover
                recover(a, True)
            if a.plan_status != 'active':
                break
        self.assertEqual(a.plan_status, 'completed', a.plan_error)
        self.assertTrue(self.w.buildings['a_farm'].complete)
        self.assertLess(r.quantity, quantity)
        self.assertEqual(self.w.settlements[a.home].inventory['wood'], 0)

    def test_offer_accept_conservation_and_authority(self):
        a, b = self.w.agents['a2'], self.w.agents['a3']
        a.x, a.y, b.x, b.y = 9, 10, 10, 10
        a.inventory['wood'], b.inventory['food'] = 10, 10
        before = {k: a.inventory[k]+b.inventory[k] for k in a.inventory}
        offer = actions.execute(self.w, {'action': 'offer', 'target': b.id, 'offered': 'wood', 'wanted': 'food', 'amount': 2}, a.id)
        self.assertTrue(offer['ok'])
        self.assertFalse(actions.execute(self.w, {'action': 'accept', 'agreement': offer['agreement']}, a.id)['ok'])
        self.assertTrue(actions.execute(self.w, {'action': 'accept', 'agreement': offer['agreement']}, b.id)['ok'])
        self.assertEqual(before, {k: a.inventory[k]+b.inventory[k] for k in a.inventory})
        self.assertFalse(actions.execute(self.w, {'action': 'accept', 'agreement': offer['agreement']}, b.id)['ok'])

    def test_archive_retains_events_beyond_working_ring_and_rewind(self):
        with tempfile.TemporaryDirectory() as directory:
            sim = Simulation(str(Path(directory)/'world.sqlite'))
            try:
                for i in range(2600):
                    sim.world.event('test_history', f'event {i}', [])
                sim.save()
                self.assertLessEqual(len(sim.world.events), 2048)
                with sqlite3.connect(sim.path) as db:
                    count = db.execute('SELECT count(*) FROM history').fetchone()[0]
                # Initial event remains in ring until archived? Save must retain it too.
                self.assertGreaterEqual(count, 2600)
                restored = persistence.load(sim.path)
                self.assertEqual(sim.world.snapshot(True), restored.snapshot(True))
            finally:
                sim.close()

    def test_legacy_save_defaults_and_configuration_validation(self):
        data = self.w.snapshot(True)
        for a in data['agents'].values():
            for key in ('plan', 'plan_status', 'beliefs', 'cognition_revision', 'observations'):
                a.pop(key)
        loaded = World.from_snapshot(data)
        self.assertEqual(loaded.agents['a2'].plan_status, 'idle')
        scheduler = self.scheduler(lambda *args: result())
        with self.assertRaises(ValueError):
            scheduler.configure({'max_concurrency': 0})
        with self.assertRaises(ValueError):
            scheduler.configure({'endpoint': 'http://user:secret@example.test'})
        self.assertEqual(scheduler.config.max_concurrency, 2)

    def test_provider_protocol_validation_and_bounded_context(self):
        config = InferenceConfig(enabled=True, retries=0)
        with patch('urllib.request.urlopen') as request:
            request.return_value.__enter__.return_value.read.return_value = json.dumps({'message': {'content': json.dumps({'goal': 'Observe', 'plan': []})}}).encode()
            self.assertTrue(generate(config, 'System', {'private': 'context'})['ok'])
            sent = json.loads(request.call_args.args[0].data)
            self.assertEqual(sent['model'], config.model)
            self.assertEqual(sent['think'], False)
            self.assertEqual(sent['format'], 'json')
            self.assertEqual(sent['messages'][0]['role'], 'system')
            request.return_value.__enter__.return_value.read.return_value = json.dumps({'message': {'content': '', 'thinking': 'reasoning without an answer'}}).encode()
            empty = generate(config, 'System', {})
            self.assertFalse(empty['ok'])
            self.assertIn('empty JSON content',empty['error'])
            config.provider = 'openai'
            request.return_value.__enter__.return_value.read.return_value = json.dumps({'choices': [{'message': {'content': '{"goal":"Observe","plan":[]}'}}]}).encode()
            self.assertTrue(generate(config, 'System', {})['ok'])
            self.assertTrue(request.call_args.args[0].full_url.endswith('/v1/chat/completions'))
            request.return_value.__enter__.return_value.read.return_value = b'{}'
            self.assertFalse(generate(config, 'System', {})['ok'])
        self.assertFalse(generate(config, SYSTEM, {'huge': 'x'*20000})['ok'])


if __name__ == '__main__':
    unittest.main()
