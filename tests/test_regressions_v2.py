"""Regressions discovered by the second implementation audit."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from genesis import actions, persistence
from genesis.cognition import Scheduler, SYSTEM, fit_context
from genesis.memory import context
from genesis.providers import InferenceConfig
from genesis.server import Simulation
from genesis.world import World


class RegressionV2Tests(unittest.TestCase):
    def test_long_conversations_fit_whole_configured_context(self):
        w = World()
        for budget in (6000, 14000):
            scheduler = Scheduler(InferenceConfig(enabled=True, context_limit=budget))
            try:
                c = {'id': 'test', 'participants': ['a1', 'player'], 'state': 'active',
                     'turns': [{'speaker': 'player', 'text': 'A detailed question '*100, 'tick': 0, 'source': 'player'} for _ in range(8)]}
                w.conversations['test'] = c
                self.assertTrue(scheduler.request(w, 'a1', 'conversation', conversation='test'))
                body = scheduler.queue[0].context
                self.assertLessEqual(len(SYSTEM)+len(json.dumps(body, ensure_ascii=False)), budget)
                self.assertEqual(body['agent']['identity']['id'], 'a1')
                self.assertTrue(body['conversation']['turns'])
            finally:
                scheduler.close()

    def test_recipient_can_refuse_last_food_and_unwanted_goods(self):
        w = World()
        a, b = w.agents['a2'], w.agents['a3']
        b.x, b.y = a.x, a.y
        a.inventory['wood'] = 10
        b.inventory['food'], b.hunger = 2, 90
        before = dict(b.inventory)
        self.assertFalse(actions.execute(w, {'action': 'trade', 'target': b.id, 'offered': 'wood', 'wanted': 'food', 'amount': 2}, a.id, True)['ok'])
        self.assertEqual(before, b.inventory)
        b.inventory['food'], b.inventory['wood'], b.hunger = 5, 100, 10
        self.assertFalse(w.trade(a, b, 'wood', 'food', 2))

    def test_governance_retrieve_cannot_bypass_sharing_policy(self):
        w = World()
        a = w.agents['a2']
        a.x, a.y, a.hunger = 9, 10, 50
        w.governance['a']['sharing'] = False
        self.assertFalse(actions.execute(w, {'action': 'retrieve', 'kind': 'food', 'amount': 2}, a.id, True)['ok'])
        a.hunger = 90
        self.assertTrue(actions.execute(w, {'action': 'retrieve', 'kind': 'food', 'amount': 1}, a.id, True)['ok'])
        self.assertFalse(actions.execute(w, {'action': 'vote', 'proposal': 'x', 'approve': 'false'}, a.id)['ok'])

    def test_conversation_holds_listener_but_emergency_survival_preempts(self):
        w = World()
        a, p = w.agents['a2'], w.agents['player']
        a.x, a.y, p.x, p.y = 20, 15, 20, 15
        scheduler = Scheduler(InferenceConfig(enabled=True))
        try:
            scheduler.speak(w, p.id, a.id, 'What do you think about winter?', 'player')
            w.step(8)
            self.assertEqual((a.x, a.y), (20, 15))
            self.assertEqual(a.activity, 'converse')
            a.thirst, a.inventory['water'] = 90, 2
            w._routine(a)
            self.assertEqual(a.activity, 'drink')
        finally:
            scheduler.close()

    def test_paused_exhausted_budget_is_explicit_not_an_infinite_queue(self):
        w = World()
        scheduler = Scheduler(InferenceConfig(enabled=True, per_agent_budget=1))
        try:
            scheduler.window = 0
            scheduler.budgets['a1'] = 1
            with self.assertRaisesRegex(ValueError, 'budget exhausted'):
                scheduler.speak(w, 'player', 'a1', 'Another question', 'player')
            self.assertFalse(w.conversations)
        finally:
            scheduler.close()

    def test_hidden_agent_move_does_not_reveal_remote_coordinates(self):
        w = World()
        a = w.agents['a2']
        before = a.x, a.y
        answer = actions.execute(w, {'action': 'move', 'target': 'b2'}, a.id, True)
        self.assertFalse(answer['ok'])
        self.assertIn('perception', answer['message'])
        self.assertEqual((a.x, a.y), before)

    def test_storage_failure_pauses_visible_worker_instead_of_silent_death(self):
        with tempfile.TemporaryDirectory() as directory:
            sim = Simulation(str(Path(directory)/'world.sqlite'))
            sim.world.tick, sim.speed = 99, 20
            with patch.object(sim, 'save', side_effect=OSError('simulated disk failure')):
                worker = threading.Thread(target=sim.run)
                worker.start()
                deadline = time.monotonic()+2
                while not sim.last_error and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertIn('disk failure', sim.last_error)
                self.assertTrue(sim.paused)
                self.assertTrue(worker.is_alive())
                sim.running = False
                worker.join(2)
            sim.close()

    def test_pending_conversation_project_and_conflict_resume_together(self):
        w = World()
        a, b = w.agents['a2'], w.agents['a3']
        a.x, a.y, b.x, b.y = 9, 10, 10, 10
        a.personality.update(aggression=.9, courage=.9)
        b.personality.update(aggression=.9, courage=.9)
        self.assertIsNotNone(w.start_conflict(a.id, b.id))
        builder = w.agents['b1']
        builder.x, builder.y = w.settlements['b'].x, w.settlements['b'].y
        self.assertTrue(w.construct(builder, 'farm'))
        w.conversations['dtest'] = {'id': 'dtest', 'participants': ['player', 'a1'], 'turns': [{'speaker': 'player', 'text': 'Remember this project', 'tick': 0, 'source': 'player'}], 'state': 'active', 'next_speaker': 'a1', 'updated': 0, 'created': 0}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'world.sqlite'
            persistence.save(w, path)
            resumed = persistence.load(path)
            self.assertEqual(w.snapshot(True), resumed.snapshot(True))
            w.step(30)
            resumed.step(30)
            self.assertEqual(w.snapshot(True), resumed.snapshot(True))
            self.assertIn('dtest', resumed.conversations)
            self.assertTrue(resumed.buildings['b_farm'].complete)

    def test_malformed_settings_preserve_config_without_worker_failure(self):
        scheduler = Scheduler(InferenceConfig(enabled=True))
        try:
            for update in ({'endpoint': 5}, {'model': 5}, {'timeout': True}):
                with self.assertRaises(ValueError):
                    scheduler.configure(update)
            self.assertEqual(scheduler.config.model, 'qwen2.5:7b')
        finally:
            scheduler.close()

    def test_semantically_corrupt_save_is_rejected_before_execution(self):
        data = World().snapshot(True)
        data['agents']['a2']['inventory']['food'] = -1
        with self.assertRaisesRegex(ValueError, 'inventory'):
            World.from_snapshot(data)
        data = World().snapshot(True)
        data['agents']['a2']['hp'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'health'):
            World.from_snapshot(data)

    def test_legacy_starting_commit_save_can_load(self):
        # A version-1-style snapshot has no new cognitive or world fields.
        w = World()
        data = w.snapshot(True)
        for key in ('paths', 'conversations', 'agreements', 'cognition_config', 'governance', 'proposals', 'shipments', 'resource_growth', 'next_conflict', 'next_shipment'):
            data.pop(key, None)
        restored = World.from_snapshot(data)
        restored.step(2)
        self.assertEqual(restored.tick, 2)
        self.assertEqual(restored.cognition_config, {})


if __name__ == '__main__':
    unittest.main()
