"""Lightweight predator ecology and authoritative nonhuman grid movement."""
from math import hypot
from types import SimpleNamespace


def occupied(world, x, y):
    cell = (round(x), round(y))
    return (any((round(a.x), round(a.y)) == cell for a in world.agents.values())
            or any(a.hp > 0 and (round(a.x), round(a.y)) == cell for a in world.wildlife.values())
            or any(a['hp'] > 0 and (round(a['x']), round(a['y'])) == cell for a in world.threats.values()))


def safe_habitat(world, x, y):
    return (world.passable(x,y) and not occupied(world,x,y)
            and all(hypot(s.x-x,s.y-y)>=7 for s in world.settlements.values())
            and all(hypot(a.x-x,a.y-y)>=4 for a in world.agents.values()))


def sight(world, x, y, tx, ty):
    steps = max(1, int(hypot(tx-x, ty-y)*4))
    return all(world.passable(round(x+(tx-x)*i/steps), round(y+(ty-y)*i/steps)) for i in range(1, steps+1))


def move(world, key, x, y, stamina, tx, ty, speed=.7):
    # Share the existing cached pathfinder, terrain, weather, walls and gates.
    body = SimpleNamespace(id='nonhuman:'+key, x=x, y=y, stamina=stamina,
                           speed=speed, equipment=[], equipment_condition={}, activity='move', incapacitated=False)
    moved = world.move(body, tx, ty)
    return body.x, body.y, body.stamina, moved


def wolf(world, animal):
    """Wolves prefer prey and avoid groups. Humans are not default prey."""
    if animal.hp <= 0 or world.tick % 4: return
    state = animal.behavior
    territory = state.setdefault('territory', [round(animal.x), round(animal.y)])
    animal.stamina = min(70, animal.stamina+3)
    humans = [a for a in world.agents.values() if not a.incapacitated and hypot(a.x-animal.x, a.y-animal.y) <= 6
              and sight(world, animal.x, animal.y, a.x, a.y)]
    close = min(humans, key=lambda a: hypot(a.x-animal.x, a.y-animal.y), default=None)
    gap = hypot(close.x-animal.x, close.y-animal.y) if close else 100
    aggression = world.climate['threat_settings']['wolf_aggression']
    provoked = next((a for a in humans if a.id == animal.threat), None)
    intruder = close and hypot(close.x-territory[0], close.y-territory[1]) < 2
    if close and gap < 5 and (len(humans) >= 2 or close.occupation == 'guard' or animal.hp < 16 or animal.stamina < 14):
        animal.activity = 'avoid'
        options = world.neighbors(animal.x, animal.y)
        if options:
            tx, ty = max(options, key=lambda p: hypot(p[0]-close.x, p[1]-close.y))
            animal.x, animal.y, animal.stamina, _ = move(world, animal.id, animal.x, animal.y, animal.stamina, tx, ty, .95)
        return
    if close and (provoked or (intruder and aggression >= .6 and gap < 3)):
        animal.activity = 'territorial'
        state['target'] = close.id
        if gap > 1.3:
            animal.x, animal.y, animal.stamina, _ = move(world, animal.id, animal.x, animal.y, animal.stamina, close.x, close.y, .8)
        return
    state.pop('target', None)
    if close and gap < 2.5:
        animal.activity = 'warning'
        return
    prey = [a for a in world.wildlife.values() if a.id != animal.id and a.hp > 0 and not a.harvested
            and a.species in ('deer', 'sheep') and hypot(a.x-territory[0], a.y-territory[1]) <= 8
            and hypot(a.x-animal.x, a.y-animal.y) <= 6 and sight(world, animal.x, animal.y, a.x, a.y)]
    target = min(prey, key=lambda a: hypot(a.x-animal.x, a.y-animal.y), default=None)
    if animal.hunger > 35 and target and animal.stamina >= 12:
        animal.activity = 'hunt'
        state['prey'] = target.id
        gap = hypot(target.x-animal.x, target.y-animal.y)
        if gap <= 1.4 and world.tick-state.get('last_attack', -100) >= 8:
            animal.stamina -= 8
            state['last_attack'] = world.tick
            target.hp = max(0, target.hp-10)
            target.activity = 'flee' if target.hp else 'incapacitated'
            if target.hp == 0:
                target.harvested = True  # Feeding consumes the carcass; no duplicate hunting yield.
                animal.hunger = max(0, animal.hunger-50)
                world.event('wildlife_hunt', 'A wolf fed on wild prey (non-graphic).', [], predator=animal.id, prey=target.id)
        elif gap > 1.4:
            animal.x, animal.y, animal.stamina, _ = move(world, animal.id, animal.x, animal.y, animal.stamina, target.x, target.y, .95)
        if target.hp > 0:
            options = world.neighbors(target.x, target.y)
            if options:
                tx, ty = max(options, key=lambda p: hypot(p[0]-animal.x, p[1]-animal.y))
                target.x, target.y, target.stamina, _ = move(world, target.id, target.x, target.y, target.stamina, tx, ty, .65)
        return
    state.pop('prey', None)
    animal.activity = 'patrol'
    options = [p for p in world.neighbors(animal.x, animal.y) if hypot(p[0]-territory[0], p[1]-territory[1]) <= 6]
    if options:
        preferred = [p for p in options if world.terrain[p[1]][p[0]] in ('forest', 'mountain')]
        tx, ty = world.rng.choice(preferred or options)
        animal.x, animal.y, animal.stamina, _ = move(world, animal.id, animal.x, animal.y, animal.stamina, tx, ty, .6)
