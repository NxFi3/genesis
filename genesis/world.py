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
    'road': {'wood': 2, 'stone': 3, 'duration': 4},
    'bridge': {'wood': 20, 'stone': 8, 'duration': 18},
    'hall': {'wood': 20, 'stone': 12, 'duration': 20, 'shelter': 10, 'social': 1},
    'well': {'wood': 8, 'stone': 15, 'duration': 15, 'water': 3},
}
RECIPES = {
    'tools': {'inputs': {'wood': 2, 'metal': 1}, 'output': 1, 'skill': 'craft'},
    'staff': {'inputs': {'wood': 3, 'tools': 1}, 'equipment': True, 'skill': 'craft'},
    'shield': {'inputs': {'wood': 4, 'metal': 1}, 'equipment': True, 'skill': 'craft'},
    'padded_coat': {'inputs': {'food': 3, 'tools': 1}, 'equipment': True, 'skill': 'craft'},
}
EVENT_LIMIT = 2048
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
        self.conversations, self.agreements = {}, {}
        self.cognition_config = {}
        self.proposals, self.shipments, self.resource_growth = {}, {}, {}
        self.governance = {}
        self.next_conflict = 1
        self.next_shipment = 1
        self.event_sink = None
        self._paths = {}
        self._generate(population)

    @property
    def season(self):
        return ('spring', 'summer', 'autumn', 'winter')[(self.tick // 250) % 4]

    @property
    def hour(self):
        return (self.tick % 240) / 10

    @property
    def weather(self):
        # Weather is deterministic from seed and day, without consuming decision RNG.
        return ('clear', 'rain', 'clear', 'wind', 'clear', 'drought')[(self.seed + self.tick // 120) % 6]

    @property
    def daylight(self):
        return 6 <= self.hour < 20

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
            self.governance[sid] = {'leader': None, 'tax': .1, 'sharing': True, 'defense': 'peaceful', 'technology': ['gathering', 'construction'], 'last_election': 0}
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
            s.council = list(dict.fromkeys([f'{sid}0', f'{sid}{min(1, population-1)}']))
            self.governance[sid]['leader'] = s.council[0]
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
        for r in self.resources.values():
            if r.kind in ('food', 'wood'):
                self.resource_growth[r.id] = {'age': 0, 'stage': 'mature' if r.quantity > r.capacity * .5 else 'growing'}
        self.event('world_created', 'Two settlements begin independently. Peace is possible.', [])

    def passable(self, x, y):
        ix, iy = round(x), round(y)
        return 0 <= ix < self.width and 0 <= iy < self.height and self.terrain[iy][ix] in PASSABLE

    def neighbors(self, x, y):
        x, y = round(x), round(y)
        return [(x+dx, y+dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if self.passable(x+dx, y+dy)]

    def move(self, a, x, y, retreating=False):
        if a.incapacitated or a.stamina < 1 or not all(math.isfinite(v) for v in (x, y)) or not self.passable(x, y):
            return False
        goal = (round(x), round(y))
        # Keep the current waypoint until reached. Rounding a half-step and replanning
        # otherwise cuts diagonal corners and can strand slow actors on river banks.
        cached = self._paths.get(a.id)
        current = (round(a.x), round(a.y))
        if cached and cached[0] == goal:
            path = cached[1]
            while path and hypot(a.x-path[0][0], a.y-path[0][1]) < .001:
                path.pop(0)
            if path and not self.passable(*path[0]):
                cached = None
        else:
            cached = None
        if not cached:
            start = current
            if start == goal:
                if hypot(a.x-x, a.y-y) < .001:
                    return False
                path = [goal]
            else:
                queue, prev = deque([start]), {start: None}
                while queue and goal not in prev:
                    p = queue.popleft()
                    for n in self.neighbors(*p):
                        if n not in prev:
                            prev[n] = p
                            queue.append(n)
                if goal not in prev:
                    return False
                path, step = [], goal
                while step != start:
                    path.append(step)
                    step = prev[step]
                path.reverse()
                # A fractional actor must first finish the previous grid segment.
                if abs(a.x-start[0]) > .001 or abs(a.y-start[1]) > .001:
                    path.insert(0, start)
            self._paths[a.id] = (goal, path)
        if not path:
            return False
        step = path[0]
        dx, dy = step[0]-a.x, step[1]-a.y
        dist = hypot(dx, dy)
        factor = PASSABLE[self.terrain[step[1]][step[0]]]
        weight = max(.5, 1-combat.attributes(a, 'weight')*.03)
        speed = max(.05, (a.speed+combat.attributes(a, 'speed'))*factor*weight)
        if self.weather == 'rain' and self.terrain[step[1]][step[0]] != 'road':
            speed *= .85
        amount = min(dist, speed, a.stamina/(2 if retreating else 1))
        if dist:
            a.x += dx/dist*amount
            a.y += dy/dist*amount
        if dist-amount < .001:
            a.x, a.y = step
            path.pop(0)
        a.stamina = max(0, a.stamina-(2 if retreating else 1)*amount)
        a.activity = 'retreat' if retreating else 'move'
        return amount > 0

    def event(self, kind, text, actors, **extra):
        e = {'id': self.next_event, 'tick': self.tick, 'kind': kind, 'text': text, 'actors': actors, **extra}
        self.next_event += 1
        self.events.append(e)
        if len(self.events) > EVENT_LIMIT:
            del self.events[:-EVENT_LIMIT]
        if self.event_sink is not None:
            self.event_sink(e)
        for aid in actors:
            if aid in self.agents:
                from .memory import remember
                remember(self.agents[aid], self.tick, text, kind,
                         3 if kind in ('damage', 'conflict_start', 'conflict_end', 'dialogue') else 1)
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
        cid = f'c{self.next_conflict}'
        self.next_conflict += 1
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

    def construct(self, agent, kind, x=None, y=None):
        if kind not in BUILDINGS or agent.incapacitated:
            return False
        s = self.settlements[agent.home]
        nearby_store = combat.distance(agent, s) <= 2
        if not nearby_store and kind not in ('road', 'bridge'):
            return False
        materials = s.inventory if nearby_store else agent.inventory
        bid = f'{s.id}_{kind}'
        if bid in self.buildings:
            if kind not in ('house', 'storage', 'road', 'bridge'):
                return False
            bid = f'{bid}_{sum(b.home == s.id and b.kind == kind for b in self.buildings.values())}'
        if x is None or y is None:
            candidates = [(s.x+dx, s.y+dy) for dx, dy in ((1,1), (-1,1), (1,-1), (-1,-1), (2,0), (0,2), (-2,0), (0,-2))]
            occupied = {(b.x, b.y) for b in self.buildings.values()}
            position = next((p for p in candidates if self.passable(*p) and p not in occupied), None)
            if position is None:
                return False
            x, y = position
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)):
            return False
        x, y = round(x), round(y)
        if not 0 <= x < self.width or not 0 <= y < self.height or hypot(agent.x-x, agent.y-y) > 4:
            return False
        if kind == 'bridge':
            if self.terrain[y][x] not in ('river', 'lake'):
                return False
        elif not self.passable(x, y):
            return False
        if any(b.x == x and b.y == y for b in self.buildings.values()):
            return False
        recipe = BUILDINGS[kind]
        if any(materials[k] < v for k, v in recipe.items() if k in materials):
            return False
        for k, v in recipe.items():
            if k in materials:
                materials[k] -= v
        self.buildings[bid] = Building(bid, kind, s.id, x, y)
        if not nearby_store:
            agent.property.append(bid)
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

    def trade(self, a, b, offered='wood', wanted='food', amount=2, accepted=False):
        if (a.id == b.id or a.incapacitated or b.incapacitated or combat.distance(a, b) > 2
                or not math.isfinite(amount) or amount <= 0 or offered == wanted or offered not in a.inventory or wanted not in b.inventory):
            return False
        if a.inventory[offered] < amount or b.inventory[wanted] < amount:
            return False
        if not accepted:
            # Recipient independently values a scarce incoming good and protects survival stock.
            reserve = (3 if b.hunger > 45 else 1) if wanted == 'food' else ((3 if b.thirst > 45 else 1) if wanted == 'water' else 0)
            if b.inventory[wanted]-amount < reserve:
                return False
            value_in = 1/(1+b.inventory[offered])
            value_out = 1/(1+b.inventory[wanted])
            if value_in < value_out*.5:
                return False
        self.transfer(a.inventory, b.inventory, offered, amount)
        self.transfer(b.inventory, a.inventory, wanted, amount)
        self.stats['traded'] += amount * 2
        at_market = any(building.kind == 'market' and building.complete and combat.distance(a, building) <= 3 and combat.distance(b, building) <= 3 for building in self.buildings.values())
        self.relate(a, b, .05 if at_market else .03)
        self.relate(b, a, .05 if at_market else .03)
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
        sharing = self.governance.get(s.id, {}).get('sharing', True)
        if combat.distance(a, s) <= 2 and s.inventory[kind] >= 1 and (sharing or a.id in s.council or getattr(a, need) > 75):
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
        if a.incapacitated:
            a.activity, a.reason = 'rest', 'Incapacitated; recovering with available supplies'
            for kind, need in (('food', 'hunger'), ('water', 'thirst')):
                if getattr(a, need) > 55:
                    self._consume(a, kind, need)
            combat.recover(a, True)
            return
        for kind, need in (('water', 'thirst'), ('food', 'hunger')):
            if getattr(a, need) > 45:
                a.reason = f'{need.title()} has highest urgency'
                if self._consume(a, kind, need):
                    return
                if a.stamina < 5:
                    a.activity = 'rest'
                    combat.recover(a, True)
                    return
                # Settlement stocks are real shared property and preferred when nearby.
                if s.inventory[kind] >= 1 and combat.distance(a, s) < 6:
                    self.move(a, s.x, s.y)
                    return
                nearby = min((r for r in self.resources.values() if r.kind == kind and r.quantity > 0), key=lambda r: combat.distance(a, r), default=None)
                if nearby:
                    if not self.gather(a, nearby):
                        self.move(a, nearby.x, nearby.y)
                    return
        if a.hp < a.max_hp*.55 or a.stamina < 25 or a.fatigue > 75:
            shelters = [b for b in self.buildings.values() if b.home == a.home and b.complete and BUILDINGS[b.kind].get('shelter')]
            shelter = min(shelters, key=lambda b: combat.distance(a, b), default=None)
            if a.fatigue > 75 and shelter and combat.distance(a, shelter) > 2 and a.stamina > 5 and a.hp > 20:
                a.reason = 'Seeking shelter to sleep safely'
                self.move(a, shelter.x, shelter.y)
                return
            a.activity, a.reason = 'sleep' if a.fatigue > 60 and shelter and combat.distance(a, shelter) <= 2 else 'rest', 'Recovering health, stamina or fatigue'
            combat.recover(a, True)
            if a.activity == 'sleep':
                a.fatigue = max(0, a.fatigue-3)
                a.shelter = max(0, a.shelter-8)
            return
        if any(c.get('state') == 'active' and a.id in c.get('participants', []) and self.tick-c.get('updated', self.tick) <= 150 for c in self.conversations.values()):
            a.activity, a.reason = 'converse', 'Listening to a nearby conversation; survival still takes priority'
            a.social = max(0, a.social-.5)
            return
        from .planning import execute_plan
        if execute_plan(self, a):
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
        if getattr(a, 'social', 0) > 60:
            hall = next((b for b in self.buildings.values() if b.home == a.home and b.kind == 'hall' and b.complete), None)
            if hall:
                a.reason = 'Visiting the public hall to meet a social need'
                if combat.distance(a, hall) > 2:
                    self.move(a, hall.x, hall.y)
                    return
                companions = [b for b in self.agents.values() if b.id != a.id and not b.incapacitated and combat.distance(a, b) <= 3]
                if companions:
                    a.social = max(0, a.social-10)
                    for companion in companions:
                        companion.social = max(0, getattr(companion, 'social', 0)-3)
                        self.relate(a, companion, .005)
                    a.activity = 'socialize'
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
                requested = self.governance[s.id].get('projects', [])
                for kind in [*requested, 'farm', 'workshop', 'market', 'watchtower']:
                    if self.construct(a, kind):
                        if kind in requested:
                            requested.remove(kind)
                        break
            return
        if self.tick % 200 == 0 and combat.distance(a, s) <= 2 and a.occupation not in ('guard', 'builder'):
            for other in self.settlements.values():
                if other.id == a.home:
                    continue
                offered = max(('food', 'wood', 'metal', 'stone'), key=lambda k: s.inventory[k]-other.inventory[k])
                wanted = max(('food', 'wood', 'metal', 'stone'), key=lambda k: other.inventory[k]-s.inventory[k])
                if offered != wanted and s.inventory[offered]-other.inventory[offered] > 30 and other.inventory[wanted]-s.inventory[wanted] > 30:
                    if self.request_shipment(a, other.id, offered, wanted, 4):
                        a.reason, a.activity = 'Taking a voluntary trade opportunity from relative scarcity', 'transport'
                        return
        if self.tick % 17 == 0 and a.personality['sociability'] > .2:
            others = [b for b in self.agents.values() if b.id != a.id and combat.distance(a, b) < 3 and not b.incapacitated]
            if others:
                b = self.rng.choice(others)
                self.relate(a, b, .02)
                self.relate(b, a, .02)
                a.activity, a.reason = 'talk', 'Building familiarity with a nearby inhabitant (rule-based interaction)'
                a.social = max(0, getattr(a, 'social', 0)-15)
                b.social = max(0, getattr(b, 'social', 0)-10)
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
        if self.weather == 'drought':
            factor *= .55
        elif self.weather == 'rain':
            factor *= 1.2
        for r in self.resources.values():
            growth = self.resource_growth.get(r.id)
            growth_factor = 1
            if growth is not None:
                growth['age'] = (growth['age']+1) % (240 if r.kind == 'food' else 10000)
                if r.kind == 'food':
                    age = growth['age']
                    growth['stage'] = 'seedling' if age < 40 else ('growing' if age < 90 else ('mature' if age < 210 else 'dormant'))
                    growth_factor = .2 if age < 90 else (1 if age < 210 else 0)
                else:
                    growth['stage'] = 'seedling' if r.quantity < r.capacity*.1 else ('growing' if r.quantity < r.capacity*.7 else 'mature')
            amount = max(0, min(r.capacity-r.quantity, r.regeneration*factor*growth_factor))
            r.quantity += amount
            self.stats['produced'] += amount
        if self.tick % 10 == 0:
            for b in self.buildings.values():
                if not b.complete:
                    continue
                s = self.settlements[b.home]
                if b.kind in ('road', 'bridge'):
                    self.terrain[round(b.y)][round(b.x)] = 'road'
                if b.kind == 'farm':
                    from .technology import modifier
                    amount = min(5*factor*max(.1, b.condition/100)*modifier(self, s.id, 'farm_yield'), max(0, self.capacity(s)-sum(s.inventory.values())))
                    s.inventory['food'] += amount
                    self.stats['produced'] += amount
                if b.kind == 'well':
                    source = min((r for r in self.resources.values() if r.kind == 'water' and combat.distance(b, r) <= 10), key=lambda r: combat.distance(b, r), default=None)
                    if source:
                        amount = min(source.quantity, 3, max(0, self.capacity(s)-sum(s.inventory.values())))
                        source.quantity -= amount
                        s.inventory['water'] += amount
                        self.stats['gathered'] += amount
                if b.kind == 'workshop' and s.inventory['wood'] >= 2 and s.inventory['metal'] >= 1 and s.inventory['tools'] < 30 and sum(s.inventory.values()) < self.capacity(s):
                    s.inventory['wood'] -= 2
                    s.inventory['metal'] -= 1
                    s.inventory['tools'] += 1
                    self.event('craft', f'{s.name} crafted a tool.', [])
        for animal in list(self.wildlife.values()):
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

    def _institutions(self):
        # Council decisions are votes with material effects. No policy changes without
        # a proposal and a majority, and hostile defense never creates a conflict.
        for proposal in self.proposals.values():
            if proposal['state'] != 'open':
                continue
            s = self.settlements[proposal['settlement']]
            for aid in s.council:
                if self.cognition_config.get('enabled') and self.tick-proposal['tick'] < 10:
                    continue
                if aid in proposal['votes']:
                    continue
                voter = self.agents[aid]
                if voter.incapacitated:
                    continue
                policy = proposal['policy']
                if policy == 'group_project':
                    agree = voter.personality['sociability'] > .2 and s.stability > 30
                else:
                    agree = voter.personality['aggression'] < .7 if policy in ('share_surplus', 'open_trade') else (s.inventory['food'] < 40 if policy == 'rationing' else voter.personality['courage'] > .4)
                self.vote(voter, proposal['id'], agree)
            if len(proposal['votes']) >= len(s.council) or self.tick-proposal['tick'] >= 30:
                passed = sum(proposal['votes'].values()) > len(s.council)/2
                proposal['state'] = 'passed' if passed else 'rejected'
                if passed and proposal['policy'] == 'group_project':
                    projects = self.governance[s.id].setdefault('projects', [])
                    if proposal['kind'] not in projects:
                        projects.append(proposal['kind'])
                elif passed:
                    s.policy = proposal['policy']
                    self.governance[s.id]['sharing'] = s.policy in ('share_surplus', 'open_trade')
                    self.governance[s.id]['defense'] = 'guarded' if s.policy == 'defense' else 'peaceful'
                    s.stability = min(100, s.stability+2)
                self.event('council_decision', f'{s.name} council {proposal["state"]} {proposal["policy"]}.', list(proposal['votes']), proposal=proposal['id'])
        for sid, government in self.governance.items():
            if government['defense'] == 'guarded':
                disputes = [c for c in self.conflicts.values() if c.state == 'active' and sid in (self.agents[c.a].home, self.agents[c.b].home)]
                for guard in self.agents.values():
                    if guard.home == sid and guard.occupation == 'guard' and disputes:
                        guard.target = min(disputes, key=lambda c: combat.distance(guard, self.agents[c.a])).id
        for shipment in self.shipments.values():
            if shipment['state'] != 'in_transit':
                continue
            courier = self.agents.get(shipment['courier'])
            destination = self.settlements[shipment['destination']]
            origin = self.settlements[shipment['origin']]
            if courier is None or courier.incapacitated:
                shipment['state'] = 'waiting'
                continue
            if combat.distance(courier, destination) <= 2:
                offered, wanted, quantity = shipment['offered'], shipment['wanted'], shipment['amount']
                cargo = shipment['cargo']
                if destination.inventory[wanted] >= quantity and cargo[offered] >= quantity:
                    self.transfer(cargo, destination.inventory, offered, quantity)
                    self.transfer(destination.inventory, cargo, wanted, quantity)
                    shipment['state'] = 'returning'
                    self.stats['traded'] += quantity*2
                    self.event('settlement_trade', f'{courier.name} exchanged {quantity:g} {offered} for {wanted} at {destination.name}.', [courier.id])
                else:
                    shipment['state'] = 'returning'
                    shipment['failed'] = True
                    self.event('shipment_failed', 'A trade could not complete; the courier returns the original cargo.', [courier.id])
        # Reinstate interrupted couriers after recovery; goods never exist outside inventory.
        for shipment in self.shipments.values():
            courier = self.agents.get(shipment['courier'])
            if courier is not None and shipment['state'] == 'waiting' and not courier.incapacitated:
                shipment['state'] = 'in_transit'
            if courier is not None and shipment['state'] == 'returning':
                origin = self.settlements[shipment['origin']]
                if combat.distance(courier, origin) <= 2:
                    for kind, amount in list(shipment['cargo'].items()):
                        if amount > 0:
                            self.transfer(shipment['cargo'], origin.inventory, kind, amount)
                    shipment['state'] = 'cancelled' if shipment.get('failed') else 'delivered'
                    self.event('shipment_delivered', f'{courier.name} delivered traded goods to {origin.name}.', [courier.id])
        if self.tick % 100 == 0:
            for b in self.buildings.values():
                if b.complete:
                    b.condition = max(10, b.condition-.5)
            for c_id, c in list(self.conflicts.items()):
                if c.state != 'active' and c.ended is not None and self.tick-c.ended > 500:
                    del self.conflicts[c_id]
            self.proposals = {k: v for k, v in self.proposals.items() if v['state'] == 'open' or self.tick-v['tick'] < 500}
            self.shipments = {k: v for k, v in self.shipments.items() if v['state'] in ('in_transit', 'waiting', 'returning') or self.tick-v['tick'] < 500}
        if self.tick % 600 == 0:
            # Lightweight ecological population dynamics with a hard carrying capacity.
            healthy = [a for a in self.wildlife.values() if a.hp > 0 and a.stamina > 40]
            if len(healthy) >= 2 and len(self.wildlife) < 16 and sum(r.quantity for r in self.resources.values() if r.kind == 'food') > 30:
                parent = self.rng.choice(healthy)
                options = self.neighbors(parent.x, parent.y)
                if options:
                    x, y = self.rng.choice(options)
                    wid = f'wild_{self.tick}'
                    self.wildlife[wid] = Wildlife(wid, x, y, species=parent.species)
                    self.event('wildlife_birth', 'A new wild animal was observed.', [])

    def propose_policy(self, agent, policy, kind=None):
        policy = {'ration': 'rationing', 'guarded': 'defense'}.get(policy, policy)
        if kind is not None:
            if kind not in BUILDINGS:
                return None
            policy = 'group_project'
        if policy not in ('share_surplus', 'rationing', 'open_trade', 'defense', 'group_project') or agent.incapacitated or (policy == 'group_project' and kind is None):
            return None
        if any(p['state'] == 'open' and p['settlement'] == agent.home for p in self.proposals.values()):
            return None
        pid = f'proposal_{self.next_event}'
        self.proposals[pid] = {'id': pid, 'settlement': agent.home, 'proposer': agent.id, 'policy': policy, 'kind': kind, 'votes': {}, 'state': 'open', 'tick': self.tick}
        self.event('proposal', f'{agent.name} proposed {policy}.', [agent.id], proposal=pid)
        return pid

    def vote(self, agent, proposal_id, approve):
        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal['state'] != 'open' or agent.id not in self.settlements[proposal['settlement']].council or type(approve) is not bool:
            return False
        proposal['votes'][agent.id] = approve
        return True

    def request_shipment(self, agent, destination, offered='food', wanted='metal', amount=4):
        if destination not in self.settlements or destination == agent.home or not math.isfinite(amount) or amount <= 0 or amount > 20 or offered == wanted:
            return None
        origin = self.settlements[agent.home]
        target = self.settlements[destination]
        if combat.distance(agent, origin) > 2 or agent.incapacitated or self.active(agent.id):
            return None
        if any(s['courier'] == agent.id and s['state'] in ('in_transit', 'returning', 'waiting') for s in self.shipments.values()):
            return None
        if offered not in origin.inventory or wanted not in target.inventory or origin.inventory[offered] < amount or target.inventory[wanted] < amount:
            return None
        # Demand-sensitive decision: nobody gives away a scarcer good for a common one.
        if target.inventory[wanted] < target.inventory.get(offered, 0)*.4:
            return None
        cargo = {kind: 0 for kind in origin.inventory}
        if not self.transfer(origin.inventory, cargo, offered, amount):
            return None
        sid = f'shipment_{self.next_shipment}'
        self.next_shipment += 1
        self.shipments[sid] = {'id': sid, 'courier': agent.id, 'origin': origin.id, 'destination': destination, 'offered': offered, 'wanted': wanted, 'amount': amount, 'cargo': cargo, 'owner': origin.id, 'state': 'in_transit', 'tick': self.tick}
        self.event('shipment_started', f'{agent.name} carries {amount:g} {offered} to {target.name}.', [agent.id])
        return sid

    def craft(self, agent, item):
        recipe = RECIPES.get(item)
        workshop = next((b for b in self.buildings.values() if b.home == agent.home and b.kind == 'workshop' and b.complete and combat.distance(agent, b) <= 2), None)
        if recipe is None or workshop is None or agent.incapacitated or agent.stamina < 4:
            return False
        if any(agent.inventory.get(k, 0) < v for k, v in recipe['inputs'].items()):
            return False
        if recipe.get('equipment') and item in agent.equipment:
            return False
        for kind, amount in recipe['inputs'].items():
            agent.inventory[kind] -= amount
        if recipe.get('equipment'):
            agent.equipment.append(item)
        else:
            agent.inventory[item] += recipe['output']
        agent.skills['craft'] = min(5, agent.skills.get('craft', 0)+.05)
        agent.stamina -= 4
        self.event('craft', f'{agent.name} crafted {item}.', [agent.id])
        return True

    def teach(self, teacher, learner, topic):
        if teacher.id == learner.id or combat.distance(teacher, learner) > 3 or teacher.incapacitated or learner.incapacitated:
            return False
        if topic not in teacher.skills:
            known = next((k for k in teacher.knowledge if k.get('claim') == topic), None)
            if known is None or teacher.stamina < 3:
                return False
            from .memory import learn
            learn(learner, self.tick, topic, teacher.id, min(.8, known.get('confidence', .5)))
            teacher.stamina -= 3
            self.relate(learner, teacher, .02)
            self.event('teaching', f'{teacher.name} shared knowledge with {learner.name}.', [teacher.id, learner.id])
            return True
        current = learner.skills.get(topic, 0)
        if teacher.skills[topic] <= current or teacher.stamina < 3:
            return False
        learner.skills[topic] = min(teacher.skills[topic], current+.1)
        teacher.stamina -= 3
        self.relate(learner, teacher, .02)
        self.event('teaching', f'{teacher.name} taught {learner.name} a method of {topic}.', [teacher.id, learner.id])
        return True

    def step(self, count=1):
        if type(count) is not int or not 0 <= count <= 100000:
            raise ValueError('Tick count must be an integer in 0..100000')
        for _ in range(count):
            self.tick += 1
            self._ecology()
            combat.update(self)
            self._institutions()
            for a in self.agents.values():
                a.hunger = min(100, a.hunger + .22)
                a.thirst = min(100, a.thirst + .3)
                a.fatigue = min(100, a.fatigue + (.16 if self.daylight else .25))
                sheltered = any(b.complete and b.condition > 0 and BUILDINGS[b.kind].get('shelter') and combat.distance(a, b) <= 2 for b in self.buildings.values())
                a.shelter = max(0, min(100, getattr(a, 'shelter', 0)+(-.6 if sheltered else .08)))
                nearby_conflict = any(c.state == 'active' and combat.distance(a, self.agents[c.a]) < 5 for c in self.conflicts.values())
                a.safety = max(0, min(100, getattr(a, 'safety', 0)+(2 if nearby_conflict else -.3)))
                a.social = min(100, getattr(a, 'social', 0)+.08)
                if a.hunger >= 95 or a.thirst >= 95:
                    a.hp = max(0, a.hp - .4)
                    a.incapacitated = a.hp <= 0
                if not self.active(a.id):
                    if a.player:
                        combat.recover(a, a.activity in ('rest', 'sleep') or a.incapacitated)
                    else:
                        shipment = next((s for s in self.shipments.values() if s['courier'] == a.id and s['state'] in ('in_transit', 'returning')), None)
                        if shipment and a.hunger < 45 and a.thirst < 45 and a.stamina >= 25 and a.fatigue < 75:
                            destination = self.settlements[shipment['destination'] if shipment['state'] == 'in_transit' else shipment['origin']]
                            a.reason = 'Transporting real goods under a settlement trade agreement'
                            self.move(a, destination.x, destination.y)
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
                  'terrain': self.terrain, 'stats': self.stats, 'next_event': self.next_event, 'hour': self.hour, 'weather': self.weather, 'daylight': self.daylight,
                  'conversations': self.conversations, 'agreements': self.agreements, 'cognition_config': self.cognition_config, 'governance': self.governance, 'proposals': self.proposals, 'shipments': self.shipments, 'resource_growth': self.resource_growth, 'next_conflict': self.next_conflict, 'next_shipment': self.next_shipment, 'paths': {k: [list(v[0]), [list(p) for p in v[1]]] for k, v in self._paths.items()}}
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
        for name in ('conversations', 'agreements', 'proposals', 'shipments', 'resource_growth', 'cognition_config'):
            setattr(w, name, data.get(name, {}))
        w.governance = data.get('governance', {sid: {'leader': s.council[0] if s.council else None, 'tax': .1, 'sharing': True, 'defense': 'peaceful', 'technology': ['gathering', 'construction'], 'last_election': 0} for sid, s in w.settlements.items()})
        w.next_conflict = data.get('next_conflict', 1+max((int(k[1:]) for k in w.conflicts if k[1:].isdigit()), default=0))
        w.next_shipment = data.get('next_shipment', 1)
        w.event_sink = None
        w._paths = {k: (tuple(v[0]), [tuple(p) for p in v[1]]) for k, v in data.get('paths', {}).items()}
        w.rng = random.Random()
        w.rng.setstate(tuples(data['rng_state']))
        from .validation import validate_world
        return validate_world(w)
