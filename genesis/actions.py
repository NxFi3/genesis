"""Validated player actions; autonomous life uses the same resource primitives."""
from . import combat


def execute(world, command):
    a = world.agents['player']
    action = command.get('action')
    if a.incapacitated and action not in ('rest', 'eat', 'drink'):
        return {'ok': False, 'message': 'Incapacitated; eat, drink and rest to recover.'}
    if world.active(a.id) and action not in ('negotiate', 'retreat', 'defend', 'fight', 'rest'):
        return {'ok': False, 'message': 'Resolve or disengage from the current conflict first.'}
    target = world.agents.get(command.get('target'))
    ok = False
    if action == 'move':
        dx, dy = int(command.get('dx', 0)), int(command.get('dy', 0))
        if abs(dx) + abs(dy) == 1:
            ok = world.move(a, round(a.x)+dx, round(a.y)+dy)
    elif action == 'rest':
        a.activity = 'rest'
        ok = True
    elif action in ('eat', 'drink'):
        ok = world._consume(a, 'food' if action == 'eat' else 'water', 'hunger' if action == 'eat' else 'thirst')
    elif action == 'gather':
        nodes = [r for r in world.resources.values() if combat.distance(a, r) <= 1.6 and r.quantity > 0]
        if nodes:
            ok = world.gather(a, min(nodes, key=lambda r: combat.distance(a, r)))
    elif action == 'build':
        ok = world.construct(a, command.get('kind', 'farm'))
    elif action == 'trade' and target:
        ok = world.trade(a, target, command.get('offered', 'wood'), command.get('wanted', 'food'), float(command.get('amount', 2)))
    elif action == 'claim' and target and combat.distance(a, target) <= 3:
        claim = str(command.get('message', ''))[:500]
        if claim:
            trust = target.relationships.get(a.id, {}).get('trust', 0)
            target.knowledge.append({'claim': claim, 'source': a.id, 'tick': world.tick, 'confidence': max(.1, min(.9, .4 + trust*.4)), 'status': 'unverified'})
            world.event('claim', f'{a.name} shared an unverified claim with {target.name}: {claim}', [a.id, target.id])
            ok = True
    elif action == 'work':
        s = world.settlements[a.home]
        if combat.distance(a, s) <= 2 and a.stamina >= 3:
            pending = [b for b in world.buildings.values() if b.home == a.home and not b.complete]
            if pending:
                from .world import BUILDINGS
                b = pending[0]
                b.progress += 1
                a.stamina -= 3
                if b.progress >= BUILDINGS[b.kind]['duration']:
                    b.complete = True
                    world.stats['built'] += 1
                    world.event('built', f'{s.name} completed a {b.kind}.', [a.id])
                ok = True
    elif action in ('store', 'retrieve'):
        s = world.settlements[a.home]
        if combat.distance(a, s) <= 2:
            kind = command.get('kind', 'wood')
            amount = float(command.get('amount', 2))
            source, destination = (a.inventory, s.inventory) if action == 'store' else (s.inventory, a.inventory)
            if action != 'store' or sum(s.inventory.values()) + amount <= world.capacity(s):
                ok = world.transfer(source, destination, kind, amount)
    elif action == 'repair':
        building = world.buildings.get(command.get('building'))
        if building and combat.distance(a, building) <= 2 and a.inventory['wood'] >= 1 and building.condition < 100:
            a.inventory['wood'] -= 1
            building.condition = min(100, building.condition + 10)
            ok = True
    elif action == 'negotiate' and target and combat.distance(a, target) <= 4:
        a.combat_choice = 'negotiate'
        for c in world.conflicts.values():
            if c.state == 'active' and {c.a, c.b} == {a.id, target.id}:
                if combat.choose_response(target, a) in ('negotiate', 'avoid', 'retreat'):
                    world.relate(a, target, .1)
                    world.relate(target, a, .1)
                    combat.finish(world, c, 'player negotiated peace')
                    ok = True
        if not world.active(a.id):
            world.relate(target, a, .01)
            ok = True
    elif action in ('retreat', 'defend', 'fight') and target and world.active(a.id):
        a.activity = a.combat_choice = action
        ok = True
    elif action == 'challenge' and target:
        a.combat_choice = 'negotiate'
        ok = world.start_conflict(a.id, target.id, 'player challenge') is not None
    elif action == 'equip':
        item = command.get('item')
        # Equipment is held physically in the equipment inventory; no item generation.
        ok = item in a.equipment
    if ok and action not in ('rest', 'move', 'gather', 'eat', 'drink'):
        world.event('player_action', f'{a.name}: {action}.', [a.id])
    return {'ok': bool(ok), 'message': f'{action}: completed' if ok else f'{action}: preconditions not met'}
