import unittest
from genesis import actions
from genesis.models import Building
from genesis.world import World, BUILDINGS
from genesis.technology import research


class TechnologyTests(unittest.TestCase):
    def test_research_cost_effect_ownership_and_private_learning(self):
        w = World()
        a = w.agents['a2']
        a.x, a.y, a.skills['gather'] = 9, 10, 2
        a.inventory.update(food=10, tools=2)
        w.buildings['a_workshop'] = Building('a_workshop', 'workshop', 'a', 9, 10, 20, True)
        w.buildings['a_farm'] = Building('a_farm', 'farm', 'a', 10, 11, 10, True)
        w.tick = 10
        before = w.settlements['a'].inventory['food']
        w._ecology()
        base_yield = w.settlements['a'].inventory['food']-before
        self.assertTrue(research(w, a, 'crop_rotation'))
        self.assertEqual(a.inventory['food'], 4)
        self.assertEqual(a.inventory['tools'], 1)
        self.assertFalse(research(w, a, 'crop_rotation'))
        self.assertTrue(any('crop_rotation' in k['claim'] for k in a.knowledge))
        self.assertFalse(any('crop_rotation' in k.get('claim', '') for k in w.agents['b2'].knowledge))
        before = w.settlements['a'].inventory['food']
        w._ecology()
        self.assertAlmostEqual(w.settlements['a'].inventory['food']-before, base_yield*1.2)
        self.assertFalse(research(w, a, 'invent_unrestricted_magic'))

    def test_remote_bridge_uses_carried_materials_and_site_work(self):
        w = World()
        a = w.agents['player']
        a.x, a.y = 23, 10
        a.inventory.update(wood=20, stone=8)
        store = w.settlements['a'].inventory.copy()
        self.assertTrue(actions.execute(w, {'action': 'build', 'kind': 'bridge', 'x': 24, 'y': 10})['ok'])
        self.assertEqual(a.inventory['wood'], 0)
        self.assertEqual(a.inventory['stone'], 0)
        self.assertEqual(store, w.settlements['a'].inventory)
        self.assertIn('a_bridge', a.property)
        a.x, a.y = 9, 10
        self.assertFalse(actions.execute(w, {'action': 'work', 'building': 'a_bridge'})['ok'])
        a.x, a.y = 23, 10
        for _ in range(BUILDINGS['bridge']['duration']):
            self.assertTrue(actions.execute(w, {'action': 'work', 'building': 'a_bridge'})['ok'])
        self.assertTrue(w.passable(24, 10))
        self.assertEqual(w.terrain[10][24], 'road')
