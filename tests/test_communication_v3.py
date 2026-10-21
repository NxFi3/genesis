"""Behavioral scenarios use explicit scripted providers, not claims of live inference."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest

from genesis import actions, persistence
from genesis.cognition import Scheduler, SYSTEM
from genesis.communication import opportunities
from genesis.memory import context, learn, remember
from genesis.planning import adopt_plan, execute_plan, validate_plan
from genesis.providers import InferenceConfig
from genesis.social import upkeep, work_commitments
from genesis.world import World
from test_cognition_v2 import drain, result


class CommunicationV3Tests(unittest.TestCase):
    def setUp(self):
        self.w = World(42)
        self.a, self.b = self.w.agents['a2'], self.w.agents['a3']
        self.a.x, self.a.y, self.b.x, self.b.y = 9, 10, 10, 10
        self.schedulers = []

    def tearDown(self):
        for scheduler in self.schedulers:
            scheduler.close()

    def scheduler(self, provider, **kwargs):
        scheduler = Scheduler(InferenceConfig(enabled=True, **kwargs), provider)
        self.schedulers.append(scheduler)
        self.w.dialogue_sink = lambda speaker, target, message, source: scheduler.speak(self.w, speaker, target, message, source)
        return scheduler

    def test_conversation_preserves_running_plan_and_goal(self):
        self.a.plan = [{'action': 'work', 'building': 'a_farm', '_started': 2}, {'action': 'rest'}]
        self.a.plan_status, self.a.plan_goal = 'active', 'Finish the farm'
        before = copy.deepcopy(self.a.plan)
        scheduler = self.scheduler(lambda *args: result(goal='Greet the traveler', speech='I can talk while working.', plan=[{'action': 'observe'}]))
        scheduler.speak(self.w, 'player', self.a.id, 'How is your work?')
        drain(scheduler, self.w, lambda: scheduler.metrics['completed'] == 1)
        self.assertEqual(self.a.plan, before)
        self.assertEqual(self.a.plan_goal, 'Finish the farm')
        self.assertIn('Preserved', self.a.plan_feedback)

    def test_append_keeps_started_step_and_replace_requires_reason(self):
        self.a.plan = [{'action': 'observe'}, {'action': 'rest', '_started': 10}]
        self.a.plan_status, self.a.plan_index = 'active', 1
        self.assertTrue(adopt_plan(self.w, self.a, validate_plan({'plan': [{'action': 'eat'}], 'plan_policy': 'append'})))
        self.assertEqual(self.a.plan[0], {'action': 'rest', '_started': 10})
        self.assertEqual(self.a.plan_index, 0)
        with self.assertRaisesRegex(ValueError, 'revision_reason'):
            validate_plan({'plan': [{'action': 'observe'}], 'plan_policy': 'replace'})
        self.assertTrue(adopt_plan(self.w, self.a, validate_plan({'goal': 'Seek water', 'plan': [{'action': 'drink'}], 'plan_policy': 'replace', 'revision_reason': 'New information: my water supply is nearly exhausted.'})))
        self.assertEqual(self.a.plan_goal, 'Seek water')
        self.assertEqual(self.w.events[-1]['kind'], 'plan_revised')

    def test_autonomous_project_conversation_leads_to_real_persistent_work(self):
        self.assertTrue(self.w.construct(self.a, 'farm'))
        before_stocks = dict(self.w.settlements['a'].inventory)
        captured = []
        def provider(config, system, payload):
            captured.append(payload)
            if 'conversation' not in payload:
                return result(plan=[], conversation={'target': self.b.id, 'topic': 'farm project', 'message': 'Could you help finish the farm we can see here?'})
            return result(plan=[], speech='I can contribute once I finish looking around.',
                          dialogue_actions=[{'action': 'commit_work', 'target': self.a.id, 'building': 'a_farm'}], end_conversation=True)
        scheduler = self.scheduler(provider)
        self.b.plan, self.b.plan_status = [{'action': 'observe'}], 'active'
        for agent in self.w.agents.values():
            agent.next_reason_tick = 999
            scheduler.events_seen[agent.id] = self.w.events[-1]['id']
        self.a.next_reason_tick = 0
        drain(scheduler, self.w, lambda: bool(self.w.conversations) and next(iter(self.w.conversations.values()))['state'] == 'ended', schedule=True)
        self.assertTrue(captured[0]['social_opportunities'])
        self.assertEqual(self.b.plan, [{'action': 'observe'}])
        self.assertTrue(any(c.get('building') == 'a_farm' and c['state'] == 'active' for c in self.b.commitments))
        execute_plan(self.w, self.b)
        for _ in range(30):
            self.w.tick += 1
            work_commitments(self.w, self.b)
        self.assertTrue(self.w.buildings['a_farm'].complete)
        commitment = next(c for c in self.b.commitments if c.get('building') == 'a_farm')
        self.assertEqual(commitment['state'], 'fulfilled')
        self.assertGreater(commitment['contributed'], 0)
        self.assertEqual(self.w.settlements['a'].inventory, before_stocks)
        self.assertGreater(self.a.relationships[self.b.id]['cooperation'], 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'project.sqlite'
            persistence.save(self.w, path)
            loaded = persistence.load(path)
            self.assertEqual(loaded.agents[self.b.id].commitments, self.b.commitments)
            self.assertEqual(loaded.conversations, self.w.conversations)

    def test_multiturn_negotiation_exchanges_real_goods_and_syncs_commitments(self):
        self.a.inventory['wood'], self.b.inventory['food'] = 8, 8
        totals = {k: self.a.inventory[k]+self.b.inventory[k] for k in self.a.inventory}
        def provider(config, system, payload):
            if payload['agent']['identity']['id'] == self.b.id:
                return result(plan=[], speech='I offer two food for two wood; you can decline.', dialogue_actions=[{'action': 'offer', 'target': self.a.id, 'offered': 'food', 'wanted': 'wood', 'amount': 2}])
            agreement = payload['pending_offers'][0]
            self.assertTrue(payload['conversation']['outcomes'][0]['ok'])
            return result(plan=[], speech='I accept that exchange.', dialogue_actions=[{'action': 'accept', 'agreement': agreement['id']}], end_conversation=True)
        scheduler = self.scheduler(provider)
        cid = scheduler.speak(self.w, self.a.id, self.b.id, 'Would you exchange food for some of my wood?', 'llm', 'trade')
        drain(scheduler, self.w, lambda: self.w.conversations[cid]['state'] == 'ended')
        self.assertEqual(totals, {k: self.a.inventory[k]+self.b.inventory[k] for k in totals})
        self.assertEqual(self.a.inventory['wood'], 6)
        self.assertEqual(self.b.inventory['food'], 6)
        for person in (self.a, self.b):
            self.assertEqual(len(person.commitments), 1)
            self.assertEqual(person.commitments[0]['state'], 'fulfilled')
            self.assertTrue(any(m['source'] == 'engine_confirmation' for m in person.memories))
        self.assertTrue(all(turn['source'] == 'llm' for turn in self.w.conversations[cid]['turns']))
        self.assertEqual(len(self.w.conversations[cid]['outcomes']), 2)

    def test_trade_expiry_and_rejection_do_not_leave_false_commitments(self):
        self.a.inventory['wood'] = 4
        offer = actions.execute(self.w, {'action': 'offer', 'target': self.b.id, 'offered': 'wood', 'wanted': 'food'}, self.a.id)
        self.assertTrue(actions.execute(self.w, {'action': 'reject', 'agreement': offer['agreement']}, self.b.id)['ok'])
        self.assertTrue(all(c['state'] == 'rejected' for person in (self.a, self.b) for c in person.commitments))
        second = actions.execute(self.w, {'action': 'offer', 'target': self.b.id, 'offered': 'wood', 'wanted': 'food'}, self.a.id)
        self.w.tick += 101
        upkeep(self.w)
        self.assertEqual(self.w.agreements[second['agreement']]['state'], 'expired')
        self.assertEqual(self.a.commitments[-1]['state'], 'expired')
        self.assertEqual(self.b.commitments[-1]['state'], 'expired')
        self.assertEqual(self.a.inventory['wood'], 4)

    def test_partner_context_retrieves_old_relevant_memory_not_private_inventories(self):
        learn(self.a, 0, 'Traveler promised oak beams for the workshop', 'player', .4)
        remember(self.a, 0, 'Traveler asked me to remember oak beams', 'dialogue', 3)
        for i in range(25):
            learn(self.a, i+1, f'An unrelated report {i}', self.b.id)
        self.b.inventory['wood'] = 987654
        payload = context(self.w, self.a, 'oak beams workshop', 14000, partner_id='player')
        self.assertIn('oak beams', payload['knowledge'][0]['claim'])
        self.assertIn('oak beams', payload['memories'][0]['content'])
        self.assertNotIn('987654', json.dumps(payload))
        self.assertIn('oak beams', json.dumps(payload))

    def test_overlapping_conversations_rejected_without_losing_a_turn(self):
        scheduler = self.scheduler(lambda *args: result(speech='Hello', plan=[]))
        cid = scheduler.speak(self.w, 'player', self.a.id, 'First question')
        for target in (self.a.id, self.b.id):
            with self.assertRaisesRegex(ValueError, 'already speaking'):
                scheduler.speak(self.w, 'player', target, 'Duplicate question')
        self.assertEqual(len(self.w.conversations), 1)
        self.assertEqual(len(self.w.conversations[cid]['turns']), 1)
        drain(scheduler, self.w, lambda: self.w.conversations[cid]['state'] == 'waiting_player')
        self.assertEqual(scheduler.speak(self.w, 'player', self.a.id, 'Follow-up question'), cid)

    def test_context_refreshes_after_queued_world_change(self):
        captured = []
        scheduler = self.scheduler(lambda config, system, payload: (captured.append(payload) or result(plan=[])))
        scheduler.request(self.w, self.a.id)
        self.a.inventory['wood'] = 19
        self.w.tick += 1
        drain(scheduler, self.w, lambda: scheduler.metrics['completed'] == 1)
        self.assertEqual(captured[0]['agent']['inventory']['wood'], 19)
        self.assertEqual(captured[0]['agent']['perception']['tick'], 1)

    def test_new_dialogue_invalidates_inflight_old_reflection(self):
        gate, entered = threading.Event(), threading.Event()
        def provider(config, system, payload):
            if 'conversation' not in payload:
                entered.set()
                gate.wait(2)
                return result(goal='Obsolete thought', plan=[{'action': 'observe'}])
            return result(plan=[], speech='I heard the new question.')
        scheduler = self.scheduler(provider)
        try:
            scheduler.request(self.w, self.a.id)
            scheduler.pump(self.w, schedule=False)
            self.assertTrue(entered.wait(1))
            cid = scheduler.speak(self.w, 'player', self.a.id, 'Something changed; can we discuss?')
            gate.set()
            drain(scheduler, self.w, lambda: self.w.conversations[cid]['state'] == 'waiting_player')
            self.assertGreaterEqual(scheduler.metrics['stale'], 1)
            self.assertFalse(any(g['description'] == 'Obsolete thought' for g in self.a.goals))
        finally:
            gate.set()

    def test_social_cooldown_and_cross_settlement_context_use_local_contact(self):
        visitor = self.w.agents['b2']
        visitor.x, visitor.y = self.a.x, self.a.y
        candidate = next(x for x in opportunities(self.w, self.a) if x['target'] == visitor.id)
        self.assertEqual(candidate['topic'], 'cross-settlement contact')
        visitor.inventory['metal'] = 765432
        self.assertNotIn('765432', json.dumps(candidate))
        self.a.social_contacts[visitor.id] = self.w.tick
        self.assertNotIn(visitor.id, [x['target'] for x in opportunities(self.w, self.a)])
        visitor.x, visitor.y = 40, 20
        self.w.tick += 100
        self.assertNotIn(visitor.id, [x['target'] for x in opportunities(self.w, self.a)])

    def test_conversational_actions_cannot_target_uninvolved_third_party(self):
        outsider = self.w.agents['a4']
        outsider.x, outsider.y = self.a.x, self.a.y
        before = outsider.inventory['food']
        scheduler = self.scheduler(lambda *args: result(plan=[], speech='I have an offer.', dialogue_actions=[{'action': 'help', 'target': outsider.id, 'kind': 'food', 'amount': 1}], end_conversation=True))
        cid = scheduler.speak(self.w, self.b.id, self.a.id, 'Can you help me?', 'llm')
        drain(scheduler, self.w, lambda: self.w.conversations[cid]['state'] == 'ended')
        self.assertEqual(outsider.inventory['food'], before)
        self.assertFalse(self.w.conversations[cid]['outcomes'][0]['ok'])

    def test_idle_builder_must_reach_remote_site_before_contributing(self):
        # This caught the legacy routine shortcut that incremented progress at the store.
        self.a.inventory['wood'], self.a.inventory['stone'] = 10, 10
        self.a.x = 12
        self.assertTrue(self.w.construct(self.a, 'road', 15, 10))
        self.a.x = 9
        building = next(b for b in self.w.buildings.values() if b.kind == 'road')
        self.a.occupation = 'builder'
        before = building.progress
        self.w._routine(self.a)
        self.assertEqual(building.progress, before)
        self.assertGreater(self.a.x, 9)
        for _ in range(30):
            self.w._routine(self.a)
        self.assertTrue(building.complete)

    def test_courier_keeps_real_cargo_while_talking_then_resumes(self):
        self.w.settlements['a'].inventory['wood'] = 40
        self.w.settlements['b'].inventory['metal'] = 40
        self.assertTrue(self.w.request_shipment(self.a, 'b', 'wood', 'metal', 2))
        shipment = next(iter(self.w.shipments.values()))
        visitor = self.w.agents['b2']
        self.a.x, self.a.y, visitor.x, visitor.y = 25, 15, 26, 15
        scheduler = self.scheduler(lambda *args: result(plan=[], speech='Safe travels.', end_conversation=True))
        cid = scheduler.speak(self.w, visitor.id, self.a.id, 'Can we discuss your shipment?', 'llm', 'trade contact')
        before = copy.deepcopy(shipment['cargo'])
        self.w.step(3)
        self.assertEqual((self.a.x, self.a.y), (25, 15))
        self.assertEqual(shipment['cargo'], before)
        drain(scheduler, self.w, lambda: self.w.conversations[cid]['state'] == 'ended')
        self.w.step(1)
        self.assertNotEqual((self.a.x, self.a.y), (25, 15))
        self.assertEqual(shipment['cargo'], before)

    def test_repeated_agreement_is_not_unbounded_trust_or_endless_dialogue(self):
        scheduler = self.scheduler(lambda *args: result(plan=[], speech='Yes, I agree with that suggestion.', stance='agree'), max_turns=16, per_agent_budget=10)
        cid = scheduler.speak(self.w, self.a.id, self.b.id, 'Should we discuss the project?', 'llm')
        drain(scheduler, self.w, lambda: self.w.conversations[cid]['state'] == 'ended')
        conversation = self.w.conversations[cid]
        self.assertIn('Repeated', conversation['closure'])
        self.assertLess(len(conversation['turns']), 16)
        self.assertAlmostEqual(self.a.relationships[self.b.id]['trust'], .025)
        self.assertAlmostEqual(self.b.relationships[self.a.id]['trust'], .025)

    def test_agent_can_address_player_who_can_reply_without_deadlock(self):
        scheduler = self.scheduler(lambda *args: result(plan=[], speech='Thanks for your answer.'))
        cid = scheduler.speak(self.w, self.a.id, 'player', 'Would you help at the farm?', 'llm', 'help')
        self.assertEqual(self.w.conversations[cid]['state'], 'waiting_player')
        self.assertFalse(scheduler.queue)
        scheduler.speak(self.w, 'player', self.a.id, 'What materials do you need?')
        drain(scheduler, self.w, lambda: scheduler.metrics['completed'] == 1)
        self.assertEqual(self.w.conversations[cid]['state'], 'waiting_player')
        self.assertEqual(len(self.w.conversations[cid]['turns']), 3)

    def test_disabling_inference_closes_pending_conversation_visibly(self):
        scheduler = self.scheduler(lambda *args: result(plan=[]))
        cid = scheduler.speak(self.w, 'player', self.a.id, 'Are you there?')
        scheduler.configure({'enabled': False})
        scheduler.pump(self.w)
        self.assertEqual(self.w.conversations[cid]['state'], 'failed')
        self.assertIn('disabled', self.w.conversations[cid]['error'])
        self.w._routine(self.a)
        self.assertNotEqual(self.a.activity, 'converse')

    def test_small_context_preserves_latest_turn_and_bounds_serialized_payload(self):
        scheduler = self.scheduler(lambda *args: result(plan=[]), context_limit=6000)
        for i in range(40):
            remember(self.a, i, 'Long private memory '*60, 'player')
        cid = scheduler.speak(self.w, 'player', self.a.id, 'Do you remember the old willow?')
        body = scheduler.queue[0].context
        self.assertLessEqual(len(SYSTEM)+len(json.dumps(body, ensure_ascii=False)), 6000)
        self.assertIn('old willow', body['conversation']['turns'][-1]['text'])
        self.assertEqual(body['conversation']['id'], cid)


if __name__ == '__main__':
    unittest.main()
