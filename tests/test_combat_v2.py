"""Regression tests for defensive stance, intent expiry, and conflict lifecycle."""
import unittest

from genesis import combat
from genesis.world import World


class CombatV2Tests(unittest.TestCase):
    def setUp(self):
        self.world = World(42)
        self.a = self.world.agents['a2']
        self.b = self.world.agents['b2']
        self.a.x, self.a.y = 10, 10
        self.b.x, self.b.y = 11, 10
        for agent in (self.a, self.b):
            agent.personality.update(aggression=.5, courage=.9)
        self.conflict = self.world.start_conflict(self.a.id, self.b.id)

    def test_defensive_agents_do_not_attack_each_other(self):
        combat.update(self.world)
        self.assertEqual(self.a.hp, 100)
        self.assertEqual(self.b.hp, 100)
        self.assertFalse(any(event['kind'] == 'damage' for event in self.world.events))
        self.assertEqual(self.conflict.state, 'resolved')

    def test_defender_stance_applies_before_first_attack(self):
        self.a.personality['aggression'] = .9
        self.b.defending = True
        expected = combat.damage(self.a, self.b)
        self.b.defending = False
        combat.update(self.world)
        self.assertAlmostEqual(self.b.hp, 100-expected)
        self.assertLess(self.a.hp, 100, 'A defender may counter an actual strike')
        self.assertTrue(self.b.defending)

    def test_defender_never_pursues_avoiding_agent(self):
        self.b.personality['courage'] = .1
        before = self.a.x, self.a.y
        combat.update(self.world)
        self.assertEqual((self.a.x, self.a.y), before)
        self.assertEqual(self.a.hp, 100)
        self.assertEqual(self.b.hp, 100)
        self.assertEqual(self.conflict.state, 'resolved')

    def test_cognitive_intent_expires_and_cannot_override_survival(self):
        self.a.combat_intent = {'choice': 'negotiate', 'expires': 10}
        self.a.personality['aggression'] = .9
        self.assertEqual(combat.choose_response(self.a, self.b, 5), 'negotiate')
        self.assertEqual(combat.choose_response(self.a, self.b, 11), 'fight')
        self.a.hp = 10
        self.a.combat_intent = {'choice': 'fight', 'expires': 100}
        self.assertEqual(combat.choose_response(self.a, self.b, 12), 'retreat')

    def test_invalid_intent_is_ignored(self):
        self.a.combat_intent = {'choice': 'invent_damage', 'expires': 100}
        self.assertEqual(combat.choose_response(self.a, self.b, 1), 'defend')
        self.a.combat_intent = {'choice': 'fight', 'expires': 'forever'}
        self.assertEqual(combat.choose_response(self.a, self.b, 1), 'defend')

    def test_conflict_finish_is_idempotent(self):
        self.assertTrue(combat.finish(self.world, self.conflict, 'peace'))
        ended = self.conflict.ended
        self.world.tick += 5
        self.assertFalse(combat.finish(self.world, self.conflict, 'replaced outcome'))
        self.assertEqual(self.conflict.ended, ended)
        self.assertEqual(self.conflict.outcome, 'peace')
        events = [e for e in self.world.events if e['kind'] == 'conflict_end']
        self.assertEqual(len(events), 1)

    def test_missing_participant_closes_without_world_crash(self):
        del self.world.agents[self.b.id]
        combat.update(self.world)
        self.assertEqual(self.conflict.state, 'resolved')
        self.assertEqual(self.conflict.outcome, 'participant unavailable')
        self.assertEqual(self.world.settlements['a'].conflict, 'peace')

    def test_incapacitated_defender_never_counterstrikes(self):
        self.a.personality['aggression'] = .9
        # HP low normally triggers retreat; a cornered retreat still cannot strike back.
        self.b.hp = 1
        self.b.stamina = 0
        self.world.neighbors = lambda *_: []
        combat.update(self.world)
        self.assertTrue(self.b.incapacitated)
        self.assertEqual(self.a.hp, 100)
        self.assertEqual(self.conflict.outcome, 'incapacitation')
