import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from genesis.world import World, BUILDINGS
from genesis import combat, persistence, actions
from genesis.llm import Ollama
from genesis.server import Simulation


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.w = World(42)
        self.a, self.b = self.w.agents['a2'], self.w.agents['b2']
        self.a.x, self.a.y = 10, 10
        self.b.x, self.b.y = 11, 10

    def hostile(self):
        for a in (self.a, self.b):
            a.personality.update(aggression=.9, courage=.9)
        return self.w.start_conflict(self.a.id, self.b.id)

    def test_guard_mediation_and_independent_responses(self):
        self.a.personality.update(aggression=.6, courage=.9)
        self.b.personality.update(aggression=.75, courage=.9)
        c = self.w.start_conflict(self.a.id, self.b.id)
        self.assertEqual(combat.choose_response(self.a, self.b), 'defend')
        self.assertEqual(combat.choose_response(self.b, self.a), 'fight')
        self.a.personality['courage'] = .1
        self.assertEqual(combat.choose_response(self.a, self.b), 'avoid')
        guard = self.w.agents['a0']
        guard.x, guard.y, guard.target = 10, 10, c.id
        self.w._routine(guard)
        self.assertEqual(c.outcome, 'guard mediation')

    def test_player_choice_and_incapacitated_help(self):
        p = self.w.agents['player']
        self.b.x, self.b.y = p.x+1, p.y
        self.b.personality.update(aggression=.9, courage=.9)
        c = self.w.start_conflict(p.id, self.b.id)
        self.assertTrue(actions.execute(self.w, {'action': 'defend', 'target': self.b.id})['ok'])
        self.assertEqual(combat.choose_response(p, self.b), 'defend')
        combat.update(self.w)
        self.assertLess(p.hp, p.max_hp)
        self.assertTrue(p.defending)
        combat.finish(self.w, c, 'test truce')
        p.hp, p.hunger, p.thirst, p.incapacitated = 0, 90, 90, True
        p.inventory['food'] = p.inventory['water'] = 0
        self.a.x, self.a.y = p.x, p.y
        self.w._routine(self.a)
        self.assertLess(p.hunger, 90)
        self.assertLess(p.thirst, 90)
        self.assertEqual(self.a.activity, 'help')
        self.assertFalse(actions.execute(self.w, {'action': 'move', 'dx': 1})['ok'])
        self.assertTrue(actions.execute(self.w, {'action': 'rest'})['ok'])
        for _ in range(14):
            combat.recover(p, True)
        self.assertFalse(p.incapacitated)

    def test_player_build_work_and_storage_transfers(self):
        p = self.w.agents['player']
        self.assertTrue(actions.execute(self.w, {'action': 'build', 'kind': 'farm'})['ok'])
        for _ in range(BUILDINGS['farm']['duration']):
            self.assertTrue(actions.execute(self.w, {'action': 'work'})['ok'])
        self.assertTrue(self.w.buildings['a_farm'].complete)
        before = self.w.settlements['a'].inventory['food'] + p.inventory['food']
        self.assertTrue(actions.execute(self.w, {'action': 'retrieve', 'kind': 'food', 'amount': 2})['ok'])
        self.assertEqual(before, self.w.settlements['a'].inventory['food']+p.inventory['food'])
        self.assertFalse(actions.execute(self.w, {'action': 'retrieve', 'kind': 'food', 'amount': float('nan')})['ok'])

    def test_watchtower_damage_reduction(self):
        from genesis.models import Building
        self.b.home = 'a'
        base = combat.damage(self.a, self.b)
        self.w.buildings['a_watchtower'] = Building('a_watchtower', 'watchtower', 'a', self.b.x, self.b.y, 20, True)
        hp = self.b.hp
        combat.strike(self.w, self.a, self.b)
        self.assertLess(hp-self.b.hp, base)

    def test_damage_calculation_equipment_and_defense(self):
        base = combat.damage(self.a, self.b)
        self.b.equipment = ['shield', 'padded_coat']
        self.assertLess(combat.damage(self.a, self.b), base)
        armored = combat.damage(self.a, self.b)
        self.a.equipment = ['staff']
        self.assertGreater(combat.damage(self.a, self.b), armored)
        self.b.defending = True
        defended = combat.damage(self.a, self.b)
        self.b.defending = False
        self.assertLess(defended, combat.damage(self.a, self.b))
        self.assertGreaterEqual(defended, 1)

    def test_stamina_consumption_and_strike_range(self):
        hp, stamina = self.b.hp, self.a.stamina
        self.assertTrue(combat.strike(self.w, self.a, self.b))
        self.assertEqual(self.a.stamina, stamina-combat.STRIKE_COST)
        self.assertLess(self.b.hp, hp)
        self.b.x = 20
        before = self.a.stamina
        self.assertFalse(combat.strike(self.w, self.a, self.b))
        self.assertEqual(before, self.a.stamina)
        self.b.x = 11
        self.a.stamina = 0
        self.assertFalse(combat.strike(self.w, self.a, self.b))

    def test_health_recovery_and_incapacitation(self):
        self.a.hp, self.a.stamina = 0, 10
        self.a.incapacitated = True
        combat.recover(self.a, False)
        self.assertEqual(self.a.hp, 0)
        for _ in range(14):
            combat.recover(self.a, True)
        self.assertFalse(self.a.incapacitated)
        self.assertGreater(self.a.hp, 20)
        self.a.hp = 99.9
        combat.recover(self.a, True)
        self.assertEqual(self.a.hp, self.a.max_hp)
        self.a.hp, self.a.hunger = 50, 100
        combat.recover(self.a, True)
        self.assertEqual(self.a.hp, 50)

    def test_retreat_behavior(self):
        self.a.hp = 15
        self.assertEqual(combat.choose_response(self.a, self.b), 'retreat')
        before = combat.distance(self.a, self.b)
        self.assertTrue(combat.retreat(self.w, self.a, self.b))
        self.assertGreater(combat.distance(self.a, self.b), before)
        self.assertLess(self.a.stamina, 100)

    def test_combat_termination_and_no_post_incapacitation_hit(self):
        c = self.hostile()
        self.b.hp = 1
        combat.update(self.w)
        self.assertEqual(c.state, 'resolved')
        self.assertEqual(c.outcome, 'incapacitation')
        self.assertEqual(self.b.hp, 0)
        hp = self.a.hp
        combat.update(self.w)
        self.assertEqual(self.a.hp, hp)
        self.assertTrue(any(e['kind'] == 'conflict_end' for e in self.w.events))
        self.assertLess(self.w.settlements['a'].stability, 100)

    def test_separation_and_timeout(self):
        c = self.hostile()
        self.b.x = 30
        combat.update(self.w)
        self.assertEqual(c.outcome, 'separation')
        self.w.tick += 101
        self.b.x = 11
        c = self.w.start_conflict(self.a.id, self.b.id)
        self.w.tick += 80
        combat.update(self.w)
        self.assertEqual(c.outcome, 'exhaustion truce')

    def test_negotiation_and_witness_reaction(self):
        self.a.personality['aggression'] = .1
        self.b.personality['aggression'] = .1
        guard = self.w.agents['a0']
        guard.x, guard.y = 9, 10
        c = self.w.start_conflict(self.a.id, self.b.id)
        self.assertEqual(guard.target, c.id)
        self.assertTrue(any(e['kind'] == 'witness' for e in self.w.events))
        combat.update(self.w)
        self.assertEqual(c.outcome, 'negotiated peace')
        self.assertGreater(self.a.relationships[self.b.id]['trust'], 0)
        self.assertEqual(self.w.settlements['a'].conflict, 'peace')

    def test_save_load_during_conflict_exact_continuation(self):
        c = self.hostile()
        combat.update(self.w)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'world.sqlite'
            persistence.save(self.w, path)
            loaded = persistence.load(path)
            self.assertEqual(self.w.snapshot(True), loaded.snapshot(True))
            self.assertEqual(loaded.conflicts[c.id].state, 'active')
            self.w.step(60)
            loaded.step(60)
            self.assertEqual(self.w.snapshot(True), loaded.snapshot(True))
            persistence.save(loaded, path)
            self.assertEqual(loaded.snapshot(True), persistence.load(path).snapshot(True))

    def test_determinism(self):
        a, b = World(42), World(42)
        self.assertEqual(a.snapshot(True), b.snapshot(True))
        a.step(60)
        b.step(60)
        self.assertEqual(a.snapshot(True), b.snapshot(True))
        self.assertNotEqual(World(43).terrain, a.terrain)

    def test_gathering_conservation(self):
        r = self.w.resources['a_r2']
        self.a.x, self.a.y = r.x, r.y
        total = r.quantity+self.a.inventory[r.kind]
        self.assertTrue(self.w.gather(self.a, r))
        self.assertAlmostEqual(total, r.quantity+self.a.inventory[r.kind])
        self.assertLess(self.a.stamina, 100)

    def test_trade_conservation_and_validation(self):
        self.a.inventory['wood'] = 5
        self.b.inventory['food'] = 5
        before = {k: self.a.inventory[k]+self.b.inventory[k] for k in self.a.inventory}
        self.assertTrue(self.w.trade(self.a, self.b))
        self.assertEqual(before, {k: self.a.inventory[k]+self.b.inventory[k] for k in self.a.inventory})
        self.assertFalse(self.w.trade(self.a, self.b, amount=-2))
        self.assertFalse(self.w.trade(self.a, self.b, amount=999))
        self.b.x = 30
        self.assertFalse(self.w.trade(self.a, self.b))

    def test_construction_consumes_and_production(self):
        s = self.w.settlements['a']
        self.a.x, self.a.y = s.x, s.y
        before = s.inventory.copy()
        self.assertTrue(self.w.construct(self.a, 'farm'))
        self.assertEqual(s.inventory['wood'], before['wood']-BUILDINGS['farm']['wood'])
        self.assertFalse(self.w.construct(self.a, 'farm'))
        b = self.w.buildings['a_farm']
        self.assertFalse(b.complete)
        self.w.tick = 10
        b.complete = True
        food = s.inventory['food']
        self.w._ecology()
        self.assertGreater(s.inventory['food'], food)
        s.inventory['wood'] = 0
        self.assertFalse(self.w.construct(self.a, 'workshop'))

    def test_movement_terrain_and_barrier(self):
        self.a.x, self.a.y = 23, 10
        self.assertFalse(self.w.move(self.a, 24, 10))
        self.assertTrue(self.w.move(self.a, 25, 10))
        self.assertTrue(self.w.passable(self.a.x, self.a.y))
        self.assertNotEqual((self.a.x, self.a.y), (25, 10))
        self.a.incapacitated = True
        self.assertFalse(self.w.move(self.a, 25, 10))

    def test_survival_behavior(self):
        self.a.hunger = 90
        stock = self.a.inventory['food']
        self.w._routine(self.a)
        self.assertLess(self.a.hunger, 90)
        self.assertEqual(self.a.inventory['food'], stock-1)
        self.a.thirst = 90
        self.w._routine(self.a)
        self.assertLess(self.a.thirst, 90)

    def test_wildlife_defense_and_guards(self):
        animal = next(iter(self.w.wildlife.values()))
        animal.x, animal.y, animal.species = 10, 10, 'boar'
        # Boxed-in wildlife uses defense when escape cannot open distance.
        animal.threat = self.a.id
        self.a.x, self.a.y = 10, 10
        for x, y in self.w.neighbors(10, 10):
            self.w.terrain[y][x] = 'river'
        hp = self.a.hp
        self.w._ecology()
        self.assertLess(self.a.hp, hp)
        self.assertEqual(animal.activity, 'flee')
        guard = self.w.agents['a0']
        self.w._routine(guard)
        self.assertEqual(guard.activity, 'patrol')

    def test_1000_ticks_no_llm_meaningful_and_consistent(self):
        self.w.step(1000)
        self.assertEqual(self.w.tick, 1000)
        self.assertGreater(self.w.stats['gathered'], 100)
        self.assertGreater(self.w.stats['consumed'], 100)
        self.assertGreater(self.w.stats['built'], 0)
        self.assertTrue(any(e['kind'] == 'social' for e in self.w.events))
        for a in self.w.agents.values():
            self.assertTrue(0 <= a.hp <= a.max_hp)
            self.assertTrue(0 <= a.stamina <= 100)
            self.assertTrue(all(v >= 0 for v in a.inventory.values()))
            self.assertTrue(self.w.passable(a.x, a.y))
        for r in self.w.resources.values():
            self.assertTrue(0 <= r.quantity <= r.capacity)
        self.assertTrue(all(v >= 0 for s in self.w.settlements.values() for v in s.inventory.values()))

    def test_ollama_disabled_unavailable_malformed_and_intentions(self):
        self.assertFalse(Ollama().converse({}, 'Hello')['available'])
        llm = Ollama(enabled=True)
        with patch('urllib.request.urlopen', side_effect=OSError('offline')):
            self.assertFalse(llm.converse({}, 'Hi')['available'])
        with patch('urllib.request.urlopen') as request:
            request.return_value.__enter__.return_value.read.return_value = b'{"response":"oops"}'
            self.assertFalse(llm.converse({}, 'Hi')['available'])
            request.return_value.__enter__.return_value.read.return_value = json.dumps({'response': json.dumps({'speech': 'Hello', 'intention': 'attack_everyone'})}).encode()
            result = llm.converse({}, 'Hi')
            self.assertTrue(result['available'])
            self.assertEqual(result['intention'], 'observe')

    def test_corrupt_save_and_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'bad.sqlite'
            path.write_text('corruption')
            with self.assertRaisesRegex(ValueError, 'Cannot load'):
                persistence.load(path)
        data = self.w.snapshot(True)
        data['version'] = 999
        with self.assertRaises(ValueError):
            World.from_snapshot(data)

    def test_player_claim_trade_and_optional_dialogue(self):
        p = self.w.agents['player']
        target = self.w.agents['a1']
        target.x, target.y = p.x, p.y
        self.assertTrue(actions.execute(self.w, {'action': 'claim', 'target': target.id, 'message': 'Stonehaven has ore'})['ok'])
        self.assertEqual(target.knowledge[-1]['status'], 'unverified')
        self.assertEqual(target.knowledge[-1]['source'], 'player')
        with tempfile.TemporaryDirectory() as directory:
            sim = Simulation(str(Path(directory)/'sim.sqlite'))
            self.assertFalse(sim.command({'action': 'talk', 'target': 'a1', 'message': 'Hello'})['ok'])
            self.assertEqual(sim.world.tick, 0)
            self.assertTrue(sim.command({'action': 'step', 'count': 5})['ok'])
            self.assertEqual(sim.world.tick, 5)
            self.assertTrue(sim.command({'action': 'save'})['ok'])
            sim.command({'action': 'step'})
            sim.command({'action': 'load'})
            self.assertEqual(sim.world.tick, 5)


if __name__ == '__main__':
    unittest.main()
