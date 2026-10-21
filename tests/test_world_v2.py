"""World regression scenarios: physical accounting, institutions, ecology, long runs."""
from collections import Counter
import json
from pathlib import Path
import tempfile
import time
import unittest

from genesis.world import World, BUILDINGS, EVENT_LIMIT
from genesis.models import Building
from genesis import persistence, combat


class WorldV2Tests(unittest.TestCase):
    def setUp(self):
        self.w = World(42)
        self.a = self.w.agents['a2']

    def totals(self, w):
        result = Counter()
        for a in w.agents.values():
            result.update(a.inventory)
        for s in w.settlements.values():
            result.update(s.inventory)
        for shipment in w.shipments.values():
            result.update(shipment['cargo'])
        return dict(result)

    def test_fractional_movement_arrives_and_never_cuts_water_corner(self):
        a = self.a
        a.speed = .2
        a.x, a.y = 22, 12
        target = (25, 12)
        for _ in range(300):
            previous = (a.x, a.y)
            moved = self.w.move(a, *target)
            a.stamina = 100
            if not moved:
                break
            self.assertTrue(self.w.passable(a.x, a.y))
            self.assertTrue(abs(a.x-previous[0]) < .00001 or abs(a.y-previous[1]) < .00001)
        self.assertEqual((a.x, a.y), target)

    def test_slow_movement_exact_save_continuation(self):
        a = self.a
        a.speed = .2
        self.w.move(a, 16, 10)
        state = json.loads(json.dumps(self.w.snapshot(True)))
        restored = World.from_snapshot(state)
        for _ in range(30):
            self.w.move(a, 16, 10)
            restored.move(restored.agents[a.id], 16, 10)
        self.assertEqual(self.w.snapshot(True), restored.snapshot(True))

    def test_injured_hungry_agent_does_not_rest_forever_without_food(self):
        self.a.hp = 45
        self.a.hunger = 90
        self.a.inventory['food'] = 0
        s = self.w.settlements['a']
        self.a.x, self.a.y = s.x+4, s.y
        start = combat.distance(self.a, s)
        self.w._routine(self.a)
        self.assertEqual(self.a.activity, 'move')
        self.assertLess(combat.distance(self.a, s), start)
        for _ in range(10):
            self.w._routine(self.a)
        self.assertLess(self.a.hunger, 90)
        self.assertGreater(self.a.hp, 45)

    def test_sleep_uses_real_shelter_and_restores_fatigue(self):
        self.a.x, self.a.y = 9, 10
        self.a.fatigue = 90
        self.a.shelter = 30
        self.w._routine(self.a)
        self.assertEqual(self.a.activity, 'sleep')
        self.assertLess(self.a.fatigue, 85)
        self.assertLess(self.a.shelter, 30)

    def test_council_votes_change_resource_sharing_rules(self):
        for aid in self.w.settlements['a'].council:
            self.w.agents[aid].personality['aggression'] = .1
        pid = self.w.propose_policy(self.a, 'share_surplus')
        self.assertIsNotNone(pid)
        self.assertFalse(self.w.vote(self.w.agents['b0'], pid, True))
        self.w._institutions()
        self.assertEqual(self.w.proposals[pid]['state'], 'passed')
        self.assertTrue(self.w.governance['a']['sharing'])
        s = self.w.settlements['a']
        s.inventory['food'] = 100
        pid = self.w.propose_policy(self.a, 'ration')
        for aid in s.council:
            self.assertTrue(self.w.vote(self.w.agents[aid], pid, True))
        self.w._institutions()
        self.assertEqual(s.policy, 'rationing')
        self.assertFalse(self.w.governance['a']['sharing'])
        self.a.x, self.a.y = s.x, s.y
        self.a.hunger, self.a.inventory['food'] = 50, 0
        self.assertFalse(self.w._consume(self.a, 'food', 'hunger'))
        self.a.hunger = 90
        self.assertTrue(self.w._consume(self.a, 'food', 'hunger'))

    def test_collective_project_approval_drives_real_builder_work(self):
        s = self.w.settlements['a']
        s.inventory.update(wood=100, stone=100)
        proposal = self.w.propose_policy(self.a, 'share_surplus', 'hall')
        self.assertIsNotNone(proposal)
        for aid in s.council:
            self.w.vote(self.w.agents[aid], proposal, True)
        self.w._institutions()
        self.assertIn('hall', self.w.governance['a']['projects'])
        builder = self.w.agents['a1']
        builder.x, builder.y = s.x, s.y
        before = s.inventory.copy()
        self.w._routine(builder)
        self.assertIn('a_hall', self.w.buildings)
        self.assertEqual(s.inventory['wood'], before['wood']-BUILDINGS['hall']['wood'])
        self.assertNotIn('hall', self.w.governance['a']['projects'])
        for _ in range(BUILDINGS['hall']['duration']):
            self.w._routine(builder)
            builder.stamina = 100
        self.assertTrue(self.w.buildings['a_hall'].complete)

    def test_shipment_cargo_physical_and_conserved(self):
        a, b = self.w.settlements['a'], self.w.settlements['b']
        a.inventory['food'], a.inventory['metal'] = 120, 0
        b.inventory['food'], b.inventory['metal'] = 5, 100
        self.a.x, self.a.y = a.x, a.y
        before = self.totals(self.w)
        sid = self.w.request_shipment(self.a, 'b', 'food', 'metal', 4)
        self.assertIsNotNone(sid)
        shipment = self.w.shipments[sid]
        self.assertEqual(shipment['cargo']['food'], 4)
        self.assertEqual(a.inventory['food'], 116)
        self.assertEqual(b.inventory['food'], 5)
        self.assertEqual(before, self.totals(self.w))
        # Advance only transport to isolate conservation from consumption/production.
        for _ in range(300):
            target = b if shipment['state'] == 'in_transit' else a
            self.w.move(self.a, target.x, target.y)
            self.a.stamina = 100
            self.w._institutions()
            if shipment['state'] == 'delivered':
                break
        self.assertEqual(shipment['state'], 'delivered')
        self.assertEqual(a.inventory['metal'], 4)
        self.assertEqual(b.inventory['food'], 9)
        self.assertEqual(before, self.totals(self.w))

    def test_failed_shipment_returns_original_property(self):
        a, b = self.w.settlements['a'], self.w.settlements['b']
        a.inventory['food'], b.inventory['food'], b.inventory['metal'] = 120, 5, 100
        self.a.x, self.a.y = a.x, a.y
        sid = self.w.request_shipment(self.a, 'b', 'food', 'metal', 4)
        shipment = self.w.shipments[sid]
        b.inventory['metal'] = 0  # Different event depleted what was expected for barter.
        self.a.x, self.a.y = b.x, b.y
        before = self.totals(self.w)
        self.w._institutions()
        self.assertEqual(shipment['state'], 'returning')
        self.assertTrue(shipment['failed'])
        self.a.x, self.a.y = a.x, a.y
        self.w._institutions()
        self.assertEqual(shipment['state'], 'cancelled')
        self.assertEqual(before, self.totals(self.w))
        self.assertEqual(a.inventory['food'], 120)

    def test_construction_road_bridge_public_hall_have_effects(self):
        s = self.w.settlements['a']
        s.inventory['wood'], s.inventory['stone'] = 100, 100
        self.a.x, self.a.y = s.x, s.y
        self.assertTrue(self.w.construct(self.a, 'hall'))
        hall = self.w.buildings['a_hall']
        self.assertIn('shelter', BUILDINGS[hall.kind])
        # A complete bridge changes an actual river cell into passable road terrain.
        self.w.terrain[10][11] = 'river'
        self.assertTrue(self.w.construct(self.a, 'bridge', 11, 10))
        bridge = self.w.buildings['a_bridge']
        bridge.complete = True
        self.w.tick = 10
        self.w._ecology()
        self.assertTrue(self.w.passable(11, 10))
        self.assertEqual(self.w.terrain[10][11], 'road')

    def test_crafting_consumes_inputs_and_teaching_changes_skill(self):
        self.w.buildings['a_workshop'] = Building('a_workshop', 'workshop', 'a', self.a.x, self.a.y, 20, True)
        self.a.inventory.update(wood=10, metal=3, tools=1)
        self.assertTrue(self.w.craft(self.a, 'shield'))
        self.assertIn('shield', self.a.equipment)
        self.assertEqual(self.a.inventory['wood'], 6)
        self.assertEqual(self.a.inventory['metal'], 2)
        self.assertFalse(self.w.craft(self.a, 'shield'))
        learner = self.w.agents['a3']
        learner.x, learner.y = self.a.x, self.a.y
        self.a.skills['gather'], learner.skills['gather'] = 3, 1
        self.assertTrue(self.w.teach(self.a, learner, 'gather'))
        self.assertGreater(learner.skills['gather'], 1)
        self.assertFalse(self.w.teach(learner, self.a, 'gather'))

    def test_events_bounded_and_sink_receives_all_history(self):
        captured = []
        self.w.event_sink = captured.append
        for i in range(EVENT_LIMIT+30):
            self.w.event('test', str(i), [self.a.id])
        self.assertEqual(len(self.w.events), EVENT_LIMIT)
        self.assertEqual(len(captured), EVENT_LIMIT+30)
        self.assertLessEqual(len(self.a.memories), 120)
        self.assertEqual(self.w.events[-1]['id'], self.w.next_event-1)

    def test_governance_shipments_ecology_persist(self):
        self.w.propose_policy(self.a, 'guarded')
        self.w.step(10)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'v2.sqlite'
            persistence.save(self.w, path)
            restored = persistence.load(path)
            self.assertEqual(self.w.snapshot(True), restored.snapshot(True))
            self.w.step(30)
            restored.step(30)
            self.assertEqual(self.w.snapshot(True), restored.snapshot(True))

    def test_10000_ticks_offline_bounded_valid_world(self):
        w = World(9)
        del w.agents['player']  # Independent survival has no player supplying goods.
        start = time.perf_counter()
        w.step(10000)
        duration = time.perf_counter()-start
        self.assertEqual(w.tick, 10000)
        self.assertGreater(w.stats['built'], 0)
        self.assertGreater(w.stats['gathered'], 1000)
        self.assertGreater(w.stats['consumed'], 1000)
        self.assertLessEqual(len(w.events), EVENT_LIMIT)
        self.assertLessEqual(len(w.wildlife), 16)
        self.assertLessEqual(len(w.conflicts), len(w.agents)*500)
        for a in w.agents.values():
            self.assertTrue(0 <= a.hp <= a.max_hp)
            self.assertTrue(0 <= a.stamina <= 100)
            self.assertTrue(w.passable(a.x, a.y))
            self.assertLessEqual(len(a.memories), 120)
            self.assertTrue(all(v >= 0 for v in a.inventory.values()))
        for s in w.settlements.values():
            self.assertTrue(all(v >= 0 for v in s.inventory.values()))
        for r in w.resources.values():
            self.assertTrue(0 <= r.quantity <= r.capacity)
        self.assertGreater(sum(a.hp > 0 for a in w.agents.values()), len(w.agents)//2)
        print(f'\nWorld v2 offline regression: 10000 ticks, {duration:.2f}s, {len(w.events)} retained events, {w.stats["built"]} buildings')


if __name__ == '__main__':
    unittest.main()
