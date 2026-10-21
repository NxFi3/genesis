"""Seeded world, resource economy and autonomous utility-based daily life."""
from collections import deque
from dataclasses import asdict
from math import hypot
import random
import math

from .models import Agent, Settlement, Resource, Building, Wildlife, Conflict
from . import combat

BUILDINGS = {
    'house': {'wood': 12, 'stone': 4, 'duration': 12, 'shelter': 6},
    'farm': {'wood': 8, 'stone': 2, 'duration': 10, 'production': 5},
    'storage': {'wood': 15, 'stone': 5, 'duration': 15, 'capacity': 600},
    'workshop': {'wood': 15, 'stone': 12, 'duration': 18},
    'market': {'wood': 12, 'stone': 6, 'duration': 12},
    'watchtower': {'wood': 15, 'stone': 15, 'duration': 20, 'defense': 3},
}
PASSABLE = {'plains': 1, 'farmland': 1, 'forest': .7, 'mountain': .5, 'road': 1.3}


class World:
    def __init__(self, seed=42, population=10, width=48, height=30):
        if not 1 <= population <= 100 or width < 32 or height < 24:
            raise ValueError('population must be 1..100; world at least 32 by 24')
        self.seed, self.width, self.height = seed, width, height
        self.rng = random.Random(seed)
        self.tick = 0
        self.agents, self.settlements, self.resources, self.buildings = {}, {}, {}, {}
        self.wildlife, self.conflicts, self.events = {}, {}, []
        self.stats = {'gathered': 0, 'consumed': 0, 'produced': 0, 'traded': 0, 'built': 0}
        self.next_event = 1
        self.terrain = []
        self._generate(population)

    @property
    def season(self):
        return ('spring', 'summer', 'autumn', 'winter')[(self.tick // 250) % 4]

    def _generate(self, population):
        river = self.width // 2
        for y in range(self.height):
            row = []
            for x in range(self.width):
                if x == river and y != self.height // 2:
                    t = 'river'
                elif hypot(x - 4, y - (self.height - 5)) < 3:
                    t = 'lake'
                elif x > self.width * .72 and self.rng.random() < .6:
                    t = 'mountain'
                elif self.rng.random() < .26:
                    t = 'forest'
                else:
                    t = 'plains'
                if y == self.height // 2:
                    t = 'road'
                row.append(t)
            self.terrain.append(row)
        for sid, name, x, y in [('a', 'Willowmere', 9, 10), ('b', 'Stonehaven', self.width - 10, 18)]:
            s = Settlement(sid, name, x, y)
            self.settlements[sid] = s
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    self.terrain[y + dy][x + dx] = 'farmland' if sid == 'a' else 'plains'
            for kind in ('house', 'storage'):
                bid = f'{sid}_{kind}'
                self.buildings[bid] = Building(bid, kind, sid, x, y, 100, True)
            # Initial materials are explicit starting stock, not conjured by construction.
            for i in range(population):
                aid = f'{sid}{i}'
                a = Agent(aid, f'{name[:3]} {i+1}', x + i % 3 - 1, y + i // 3 % 3 - 1, sid)
                a.personality = {'aggression': self.rng.uniform(.05, .85), 'courage': self.rng.random(), 'sociability': self.rng.random()}
                a.occupation = 'guard' if i == 0 else ('builder' if i == 1 else 'gatherer')
                if i == 0:
                    a.equipment = ['staff', 'shield', 'padded_coat']
                self.agents[aid] = a
            s.council = [f'{sid}0', f'{sid}{min(1, population-1)}']
            s.diplomacy = {'b' if sid == 'a' else 'a': 'peace'}
            for n, (kind, dx, dy, qty, regen) in enumerate([
                ('food', -3, 0, 160 if sid == 'a' else 80, .45),
                ('water', 0, -3, 1000, 3), ('wood', 3, 0, 240, .12),
                ('stone', 0, 3, 220, 0), ('metal', 4, 3, 40 if sid == 'a' else 240, 0)]):
                rid = f'{sid}_r{n}'
                self.resources[rid] = Resource(rid, kind, x + dx, y + dy, qty, qty, regen)
                self.terrain[y + dy][x + dx] = 'forest' if kind == 'wood' else self.terrain[y + dy][x + dx]
        self.agents['player'] = Agent('player', 'Traveler', 9, 11, 'a', player=True, equipment=['boots'])
        for i in range(6):
            x, y = self.rng.randrange(2, self.width-2), self.rng.randrange(2, self.height-2)
            if self.passable(x, y):
                self.wildlife[f'w{i}'] = Wildlife(f'w{i}', x, y, species='boar' if i % 3 == 0 else 'deer')
        self.event('world_created', 'Two settlements begin independently. Peace is possible.', [])

    def passable(self, x, y):
        ix, iy = round(x), round(y)
        return 0 <= ix < self.width and 0 <= iy < self.height and self.terrain[iy][ix] in PASSABLE

    def neighbors(self, x, y):
        x, y = round(x), round(y)
        return [(x+dx, y+dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if self.passable(x+dx, y+dy)]

    def move(self, a, x, y, retreating=False):
        if a.incapacitated or a.stamina < 1 or not self.passable(x, y):
            return False
        start, goal = (round(a.x), round(a.y)), (round(x), round(y))
        if start == goal:
            return False
        queue, prev = deque([start]), {start: None}
        while queue and goal not in prev:
            p = queue.popleft()
            for n in self.neighbors(*p):
                if n not in prev:
                    prev[n] = p
                    queue.append(n)
        if goal not in prev:
            return False
        step = goal
        while prev[step] != start:
            step = prev[step]
        dx, dy = step[0] - a.x, step[1] - a.y
        dist = hypot(dx, dy)
        factor = PASSABLE[self.terrain[step[1]][step[0]]]
        weight = max(.5, 1 - combat.attributes(a, 'weight') * .03)
        speed = (a.speed + combat.attributes(a, 'speed')) * factor * weight
        amount = min(dist, speed)
        if dist:
            a.x += dx / dist * amount
            a.y += dy / dist * amount
        a.stamina = max(0, a.stamina - (2 if retreating else 1) * amount)
        a.activity = 'retreat' if retreating else 'move'
        return True

    def event(self, kind, text, actors, **extra):
        e = {'id': self.next_event, 'tick': self.tick, 'kind': kind, 'text': text, 'actors': actors, **extra}
        self.next_event += 1
        self.events.append(e)
        for aid in actors:
            if aid in self.agents:
                self.agents[aid].memories.append({'tick': self.tick, 'content': text, 'importance': 3 if kind in ('damage', 'conflict_start', 'conflict_end') else 1, 'source': kind, 'confidence': 1})
                # Recent details plus retained significant experiences; full history is in SQLite.
                memories = self.agents[aid].memories
                if len(memories) > 120:
                    index = next((i for i, m in enumerate(memories) if m['importance'] < 3), 0)
                    memories.pop(index)
        return e

    def memories_for(self, aid, query='', limit=8):
        words = set(query.lower().split())
        return sorted(self.agents[aid].memories, key=lambda m: (m['importance'] + len(words & set(m['content'].lower().split())), m['tick']), reverse=True)[:limit]

    def relate(self, a, b, change):
        r = a.relationships.setdefault(b.id, {'trust': 0, 'familiarity': 0, 'cooperation': 0, 'rivalry': 0, 'reputation': 0})
        r['trust'] = max(-1, min(1, r['trust'] + change))
        r['familiarity'] = min(1, r['familiarity'] + .02)
        r['cooperation'] = max(0, min(1, r['cooperation'] + max(0, change)))
        r['rivalry'] = max(0, min(1, r['rivalry'] - change))
        r['reputation'] = r['trust']

    def active(self, aid):
        return any(c.state == 'active' and aid in (c.a, c.b) for c in self.conflicts.values())

    def start_conflict(self, a_id, b_id, cause='dispute'):
        if a_id == b_id or a_id not in self.agents or b_id not in self.agents:
            return None
        a, b = self.agents[a_id], self.agents[b_id]
        if a.incapacitated or b.incapacitated or self.active(a_id) or self.active(b_id) or combat.distance(a, b) > 4:
            return None
        recent = [c for c in self.conflicts.values() if {c.a, c.b} == {a_id, b_id} and c.ended is not None and self.tick - c.ended < 100]
        if recent:
            return None
        cid = f'c{len(self.conflicts) + 1}'
        self.conflicts[cid] = Conflict(cid, a_id, b_id, self.tick, cause)
        self.event('conflict_start', f'{a.name} and {b.name}: {cause}.', [a_id, b_id], conflict=cid)
        for sid in {a.home, b.home}:
            self.settlements[sid].stability = max(0, self.settlements[sid].stability - 3)
            self.settlements[sid].conflict = 'alert'
        # Witnesses remember what they saw; guards intervene, others avoid danger.
        for witness in self.agents.values():
            if witness.id not in (a_id, b_id) and combat.distance(witness, a) < 5:
                self.event('witness', f'{witness.name} witnessed a dispute involving {a.name}.', [witness.id])
                self.relate(witness, a, -.03)
                if witness.occupation == 'guard' and not witness.player:
                    witness.target = cid
        return self.conflicts[cid]

    def construct(self, agent, kind):
        if kind not in BUILDINGS or agent.incapacitated:
            return False
        s = self.settlements[agent.home]
        if combat.distance(agent, s) > 2:
            return False
        bid = f'{s.id}_{kind}'
        if bid in self.buildings:
            return False
        recipe = BUILDINGS[kind]
        if any(s.inventory[k] < v for k, v in recipe.items() if k in s.inventory):
            return False
        for k, v in recipe.items():
            if k in s.inventory:
                s.inventory[k] -= v
        self.buildings[bid] = Building(bid, kind, s.id, s.x + 1, s.y + 1)
        self.event('construction', f'{agent.name} started a {kind}; materials reserved.', [agent.id])
        return True

    def capacity(self, s):
        return 250 + sum(BUILDINGS[b.kind].get('capacity', 0) for b in self.buildings.values() if b.home == s.id and b.complete)

    def transfer(self, source, destination, kind, amount):
        if kind not in source or kind not in destination or not math.isfinite(amount) or amount <= 0 or source[kind] < amount:
            return False
        source[kind] -= amount
        destination[kind] += amount
        return True

    def trade(self, a, b, offered='wood', wanted='food', amount=2):
        if (a.id == b.id or a.incapacitated or b.incapacitated or combat.distance(a, b) > 2
                or not math.isfinite(amount) or amount <= 0 or offered == wanted or offered not in a.inventory or wanted not in b.inventory):
            return False
        if a.inventory[offered] < amount or b.inventory[wanted] < amount:
            return False
        self.transfer(a.inventory, b.inventory, offered, amount)
        self.transfer(b.inventory, a.inventory, wanted, amount)
        self.stats['traded'] += amount * 2
        self.relate(a, b, .03)
        self.relate(b, a, .03)
        self.event('trade', f'{a.name} exchanged {amount} {offered} for {wanted} with {b.name}.', [a.id, b.id])
        return True

    def _consume(self, a, kind, need):
        if a.inventory[kind] >= 1:
            a.inventory[kind] -= 1
            setattr(a, need, max(0, getattr(a, need) - 38))
            self.stats['consumed'] += 1
            a.activity = 'eat' if kind == 'food' else 'drink'
            self.event(a.activity, f'{a.name} consumed {kind}.', [a.id])
            return True
        s = self.settlements[a.home]
        if combat.distance(a, s) <= 2 and s.inventory[kind] >= 1:
            self.transfer(s.inventory, a.inventory, kind, 1)
            return self._consume(a, kind, need)
        return False

    def gather(self, a, r):
        if a.incapacitated or combat.distance(a, r) > 1.6 or a.stamina < 4 or r.quantity <= 0:
            return False
        amount = min(3 + a.skills['gather'] * .2, r.quantity)
        r.quantity -= amount
        a.inventory[r.kind] += amount
        a.stamina -= 4
        a.skills['gather'] = min(5, a.skills['gather'] + .002)
        a.activity = 'gather'
        self.stats['gathered'] += amount
        self.event('gather', f'{a.name} gathered {amount:.1f} {r.kind}.', [a.id])
        return True

    def _routine(self, a):
        s = self.settlements[a.home]
        a.defending = False
        if a.incapacitated or a.hp < a.max_hp * .55 or a.stamina < 25 or a.fatigue > 75:
            a.activity, a.reason = 'rest', 'Recovering health, stamina or fatigue'
            self._consume(a, 'food', 'hunger') if a.hunger > 55 else None
            self._consume(a, 'water', 'thirst') if a.thirst > 55 else None
            combat.recover(a, True)
            return
        # Optional model intentions enter the same validated local decision layer.
        if a.goals and a.goals[-1].get('source') == 'ollama' and self.tick - a.goals[-1]['tick'] < 12:
            intent = a.goals[-1]['intention']
            if intent == 'rest' and a.hunger < 45 and a.thirst < 45:
                a.activity, a.reason = 'rest', 'Accepted a safe high-level model intention'
                combat.recover(a, True)
                return
        # Survival has higher utility than work or social goals.
        for kind, need in (('water', 'thirst'), ('food', 'hunger')):
            if getattr(a, need) > 45:
                a.reason = f'{need.title()} has highest urgency'
                if self._consume(a, kind, need):
                    return
                nearby = min((r for r in self.resources.values() if r.kind == kind and r.quantity > 0), key=lambda r: combat.distance(a, r), default=None)
                if nearby:
                    if not self.gather(a, nearby):
                        self.move(a, nearby.x, nearby.y)
                    return
        injured = next((b for b in self.agents.values() if b.id != a.id and b.incapacitated and not self.active(b.id) and combat.distance(a, b) <= 2), None)
        if injured:
            assisted = False
            for kind, need in (('food', 'hunger'), ('water', 'thirst')):
                if getattr(injured, need) > 45 and a.inventory[kind] >= 1:
                    self.transfer(a.inventory, injured.inventory, kind, 1)
                    self._consume(injured, kind, need)
                    assisted = True
            if assisted:
                a.activity, a.reason = 'help', 'Providing supplies to an incapacitated neighbor'
                self.relate(injured, a, .05)
                self.event('help', f'{a.name} helped {injured.name} recover.', [a.id, injured.id])
                return
        if a.occupation == 'guard':
            a.reason = 'Patrolling and protecting nearby inhabitants'
            if a.target in self.conflicts and self.conflicts[a.target].state == 'active':
                c = self.conflicts[a.target]
                first, second = self.agents[c.a], self.agents[c.b]
                if combat.distance(a, first) > 2:
                    self.move(a, first.x, first.y)
                elif first.personality['aggression'] < .8 or second.personality['aggression'] < .8:
                    self.relate(first, second, .05)
                    self.relate(second, first, .05)
                    combat.finish(self, c, 'guard mediation')
                else:
                    # Protection absorbs attacks through stance/armor without forcing a new duel.
                    first.defending = second.defending = True
                    self.event('guard_warning', f'{a.name} called for a truce.', [a.id, first.id, second.id])
            else:
                points = [(s.x-3, s.y-3), (s.x+3, s.y-3), (s.x+3, s.y+3), (s.x-3, s.y+3)]
                x, y = points[a.patrol_index % 4]
                if hypot(a.x-x, a.y-y) < 1:
                    a.patrol_index += 1
                self.move(a, x, y)
                a.activity = 'patrol'
            return
        carried = sum(v for k, v in a.inventory.items() if k not in ('food', 'water'))
        if carried >= 10 or (a.occupation == 'builder' and self.tick % 30 < 15):
            a.reason = 'Delivering materials or constructing settlement facilities'
            if combat.distance(a, s) > 1.5:
                self.move(a, s.x, s.y)
                return
            for k in a.inventory:
                keep = 4 if k in ('food', 'water') else 0
                amount = min(max(0, a.inventory[k] - keep), max(0, self.capacity(s) - sum(s.inventory.values())))
                if amount:
                    self.transfer(a.inventory, s.inventory, k, amount)
            a.activity = 'store'
            pending = [b for b in self.buildings.values() if b.home == a.home and not b.complete]
            if pending:
                b = pending[0]
                b.progress += 1
                a.stamina = max(0, a.stamina - 3)
                a.activity = 'build'
                if b.progress >= BUILDINGS[b.kind]['duration']:
                    b.complete = True
                    self.stats['built'] += 1
                    self.event('built', f'{s.name} completed a {b.kind}.', [a.id])
            else:
                for kind in ('farm', 'workshop', 'market', 'watchtower'):
                    if self.construct(a, kind):
                        break
            return
        if self.tick % 17 == 0 and a.personality['sociability'] > .2:
            others = [b for b in self.agents.values() if b.id != a.id and combat.distance(a, b) < 3 and not b.incapacitated]
            if others:
                b = self.rng.choice(others)
                self.relate(a, b, .02)
                self.relate(b, a, .02)
                a.activity, a.reason = 'talk', 'Building familiarity with a nearby inhabitant (rule-based interaction)'
                self.event('social', f'{a.name} and {b.name} shared local observations.', [a.id, b.id])
                if not self.trade(a, b):
                    self.trade(a, b, 'stone', 'water')
                return
        # Resource demand and comparative geography drive work selection.
        candidates = [r for r in self.resources.values() if r.quantity > 0 and r.kind in ('food', 'wood', 'stone', 'metal')]
        def utility(r):
            demand = max(1, 80 - s.inventory[r.kind])
            if r.kind == 'food':
                demand *= 1.5
            if r.kind == 'metal' and not self.buildings.get(f'{a.home}_workshop', Building('', '', '', 0, 0)).complete:
                demand *= .1
            return demand / (3 + combat.distance(a, r)) / (1 + a.inventory[r.kind])
        if candidates:
            r = max(candidates, key=utility)
            a.reason = f'Gathering {r.kind}: supply, distance and carried stock'
            if not self.gather(a, r):
                self.move(a, r.x, r.y)

    def _ecology(self):
        factor = .25 if self.season == 'winter' else 1
        for r in self.resources.values():
            amount = min(r.capacity-r.quantity, r.regeneration*factor)
            r.quantity += amount
            self.stats['produced'] += amount
        if self.tick % 10 == 0:
            for b in self.buildings.values():
                if not b.complete:
                    continue
                s = self.settlements[b.home]
                if b.kind == 'farm':
                    amount = min(5*factor, max(0, self.capacity(s)-sum(s.inventory.values())))
                    s.inventory['food'] += amount
                    self.stats['produced'] += amount
                if b.kind == 'workshop' and s.inventory['wood'] >= 2 and s.inventory['metal'] >= 1:
                    s.inventory['wood'] -= 2
                    s.inventory['metal'] -= 1
                    s.inventory['tools'] += 1
                    self.event('craft', f'{s.name} crafted a tool.', [])
        for animal in self.wildlife.values():
            if animal.hp <= 0:
                animal.activity = 'incapacitated'
                continue
            threat = self.agents.get(animal.threat)
            if threat is None:
                # Wildlife interprets close crowding as a threat, never seeks fights.
                threat = next((a for a in self.agents.values() if not a.incapacitated and combat.distance(animal, a) < .8), None)
                if threat:
                    animal.threat = threat.id
            if threat and combat.distance(animal, threat) < 5 and not threat.incapacitated:
                animal.activity = 'flee'
                choices = self.neighbors(animal.x, animal.y)
                if choices:
                    animal.x, animal.y = max(choices, key=lambda p: hypot(p[0]-threat.x, p[1]-threat.y))
                if animal.species == 'boar' and combat.distance(animal, threat) <= 1.5 and animal.stamina >= 8:
                    threat.hp = max(0, threat.hp - max(1, 5-threat.defense*.5))
                    threat.incapacitated = threat.hp <= 0
                    animal.stamina -= 8
                    self.event('wildlife_defense', 'A threatened boar defended itself.', [threat.id])
            else:
                animal.threat = None
                animal.activity = 'graze'
                animal.stamina = min(70, animal.stamina+2)
                if self.tick % 8 == 0:
                    options = self.neighbors(animal.x, animal.y)
                    if options:
                        animal.x, animal.y = self.rng.choice(options)

    def step(self, count=1):
        for _ in range(count):
            self.tick += 1
            self._ecology()
            combat.update(self)
            for a in self.agents.values():
                a.hunger = min(100, a.hunger + .22)
                a.thirst = min(100, a.thirst + .3)
                a.fatigue = min(100, a.fatigue + .16)
                if a.hunger >= 95 or a.thirst >= 95:
                    a.hp = max(0, a.hp - .4)
                    a.incapacitated = a.hp <= 0
                if not self.active(a.id):
                    if a.player:
                        combat.recover(a, a.activity == 'rest' or a.incapacitated)
                    else:
                        self._routine(a)
                        combat.recover(a, False)
                # Only genuinely hostile, scarce-resource encounters can escalate.
                if not a.player and not a.incapacitated and self.tick % 23 == 0 and a.personality['aggression'] > .7:
                    for b in self.agents.values():
                        if b.id != a.id and combat.distance(a, b) < 2 and a.relationships.get(b.id, {}).get('trust', 0) < -.35 and a.hunger > 55:
                            self.start_conflict(a.id, b.id, 'scarcity and unresolved rivalry')
                            break
            if self.tick % 50 == 0:
                for s in self.settlements.values():
                    s.stability = min(100, s.stability + .5) if s.conflict == 'peace' else max(0, s.stability-.2)

    def snapshot(self, full=False):
        result = {'version': 1, 'seed': self.seed, 'width': self.width, 'height': self.height, 'tick': self.tick, 'season': self.season,
                  'terrain': self.terrain, 'stats': self.stats, 'next_event': self.next_event}
        for name in ('agents', 'settlements', 'resources', 'buildings', 'wildlife', 'conflicts'):
            result[name] = {k: asdict(v) for k, v in getattr(self, name).items()}
        result['events'] = self.events if full else self.events[-80:]
        if full:
            result['rng_state'] = self.rng.getstate()
        return result

    @classmethod
    def from_snapshot(cls, data):
        if data.get('version') != 1:
            raise ValueError('Unsupported save version')
        w = cls.__new__(cls)
        for name in ('seed', 'width', 'height', 'tick', 'terrain', 'stats', 'next_event', 'events'):
            setattr(w, name, data[name])
        for name, model in [('agents', Agent), ('settlements', Settlement), ('resources', Resource), ('buildings', Building), ('wildlife', Wildlife), ('conflicts', Conflict)]:
            setattr(w, name, {k: model(**v) for k, v in data[name].items()})
        def tuples(v):
            return tuple(tuples(x) for x in v) if isinstance(v, list) else v
        w.rng = random.Random()
        w.rng.setstate(tuples(data['rng_state']))
        return w
