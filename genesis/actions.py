"""Authoritative, actor-independent action boundary for players and model plans."""
import math
from . import combat
from .memory import learn


def execute(world, command, actor_id='player', planned=False):
    a = world.agents.get(actor_id)
    def fail(reason):
        return {'ok': False, 'message': reason}
    def done(pending=False):
        return {'ok': True, 'pending': pending, 'message': f'{action}: '+('in progress' if pending else 'completed')}
    if not a:
        return fail('Unknown actor')
    action = command.get('action')
    if a.incapacitated and action not in ('rest', 'eat', 'drink', 'sleep'):
        return fail('Incapacitated; eat, drink and rest to recover.')
    if world.active(a.id) and action not in ('negotiate', 'retreat', 'defend', 'fight', 'avoid', 'conflict_response', 'rest'):
        return fail('Resolve or disengage from the current conflict first.')
    target = world.agents.get(command.get('target'))
    try:
        if action == 'move':
            entity = next((collection.get(command.get('target')) for collection in
                           (world.agents, world.resources, world.buildings, world.settlements) if command.get('target') in collection), None)
            if entity and planned and entity.id != a.home and entity.id not in a.observations and entity.id not in a.property and combat.distance(a, entity) > 9:
                return fail('Destination is not in current perception or remembered geography')
            if entity:
                x, y = entity.x, entity.y
            elif 'x' in command and 'y' in command:
                x, y = float(command['x']), float(command['y'])
            else:
                dx, dy = int(command.get('dx', 0)), int(command.get('dy', 0))
                if abs(dx)+abs(dy) != 1:
                    return fail('Move requires a cardinal step, destination coordinates, or a known target')
                x, y = round(a.x)+dx, round(a.y)+dy
            if not math.isfinite(x) or not math.isfinite(y) or not world.passable(x, y):
                return fail('Destination is outside the world or impassable')
            if math.hypot(a.x-x, a.y-y) <= .3:
                return done()
            if not world.move(a, x, y):
                return fail('No traversable path or insufficient stamina')
            return done(planned and math.hypot(a.x-x, a.y-y) > .3)
        if action in ('rest', 'sleep'):
            if action == 'sleep' and not any(b.complete and b.condition > 0 and b.kind in ('house', 'hall') and combat.distance(a, b) <= 2 for b in world.buildings.values()):
                return fail('Sleep requires nearby completed shelter; rest is possible outdoors')
            a.activity = action
            if planned:
                combat.recover(a, True)
                return done(a.fatigue > 15 or a.stamina < 90 or a.hp < a.max_hp)
            return done()
        if action in ('eat', 'drink'):
            if world._consume(a, 'food' if action == 'eat' else 'water', 'hunger' if action == 'eat' else 'thirst'):
                return done()
            return fail('No food/water in inventory or reachable home store')
        if action == 'observe':
            from .memory import perceive
            perceive(world, a)
            a.activity = 'observe'
            return done()
        if action == 'gather':
            r = world.resources.get(command.get('resource'))
            if command.get('resource') and r is None:
                return fail('Unknown resource deposit')
            if r is None:
                r = min((r for r in world.resources.values() if combat.distance(a, r) <= 1.6 and r.quantity > 0), key=lambda r: combat.distance(a, r), default=None)
            if not r:
                return fail('No resource deposit in reach')
            if world.gather(a, r):
                return done()
            return fail('Deposit depleted, out of reach, or too exhausted to gather')
        if action == 'build':
            if world.construct(a, command.get('kind', 'farm'), command.get('x'), command.get('y')):
                return done()
            from .world import BUILDINGS
            required = {k: v for k, v in BUILDINGS.get(command.get('kind', 'farm'), {}).items() if k in a.inventory}
            return fail(f'Construction failed: costs {required}; check available materials, site, ownership and duplicate building type')
        if action == 'work':
            s = world.settlements[a.home]
            if a.stamina < 3:
                return fail('Construction work requires stamina')
            b = world.buildings.get(command.get('building'))
            if command.get('building') and b is None:
                return fail('Unknown construction project')
            if b is None:
                b = min((b for b in world.buildings.values() if b.home == a.home and not b.complete), key=lambda b: combat.distance(a, b), default=None)
            if not b or b.home != a.home:
                return fail('No authorized construction project')
            if combat.distance(a, b) > 2:
                return fail('Work requires proximity to the actual construction site')
            if b.complete:
                return done()
            from .world import BUILDINGS
            from .technology import modifier
            previous_progress = b.progress
            b.progress += (1 + max(0, a.skills['build']-1)*.1)*modifier(world, a.home, 'construction')
            for commitment in a.commitments:
                if commitment.get('building') == b.id and commitment['state'] == 'active':
                    commitment['contributed'] = commitment.get('contributed', 0)+b.progress-previous_progress
            a.skills['build'] = min(5, a.skills['build']+.005)
            a.stamina -= 3
            a.activity = 'build'
            if b.progress >= BUILDINGS[b.kind]['duration']:
                b.complete = True
                if b.kind in ('road', 'bridge'):
                    world.terrain[round(b.y)][round(b.x)] = 'road'
                world.stats['built'] += 1
                world.event('built', f'{s.name} completed a {b.kind}.', [a.id])
            return done(planned and not b.complete)
        if action in ('store', 'retrieve'):
            s = world.settlements[a.home]
            if combat.distance(a, s) > 2:
                return fail('Visit your home store first')
            kind, amount = command.get('kind', 'wood'), float(command.get('amount', 2))
            if not math.isfinite(amount) or amount <= 0:
                return fail('Amount must be finite and positive')
            source, destination = (a.inventory, s.inventory) if action == 'store' else (s.inventory, a.inventory)
            if action == 'store' and sum(s.inventory.values())+amount > world.capacity(s):
                return fail('Store capacity exceeded')
            if action == 'retrieve' and not world.governance.get(s.id, {}).get('sharing', True) and a.id not in s.council:
                emergency = kind in ('food', 'water') and getattr(a, 'hunger' if kind == 'food' else 'thirst') > 75 and amount <= 1
                if not emergency:
                    return fail('Council policy restricts shared withdrawals; emergency aid permits one unit')
            if action == 'retrieve' and s.policy == 'rationing' and kind in ('food', 'water') and amount > 3:
                return fail('Council rationing limits withdrawals to three units')
            if world.transfer(source, destination, kind, amount):
                world.event(action, f'{a.name} {action}: {amount:g} {kind}.', [a.id])
                return done()
            return fail('Insufficient owned resource or unsupported item')
        if action == 'repair':
            b = world.buildings.get(command.get('building'))
            if b and b.home == a.home and combat.distance(a, b) <= 2 and a.inventory['wood'] >= 1 and b.condition < 100:
                a.inventory['wood'] -= 1
                b.condition = min(100, b.condition+10)
                return done()
            return fail('Repair requires own damaged building, wood and proximity')
        if action == 'trade':
            if target and world.trade(a, target, command.get('offered', 'wood'), command.get('wanted', 'food'), float(command.get('amount', 2))):
                return done()
            return fail('Exchange declined: check distance, stock, demand and participants')
        if action in ('offer', 'accept', 'reject'):
            from .social import agreement_action
            return agreement_action(world, a, command)
        if action == 'commit_work':
            from .social import commit_work
            return commit_work(world, a, target, command.get('building'))
        if action == 'talk':
            if not target or target.id == a.id or combat.distance(a, target) > 3:
                return fail('Conversation partner must be within three tiles')
            callback = getattr(world, 'dialogue_sink', None)
            if callback and command.get('message'):
                callback(a.id, target.id, str(command['message'])[:1200], 'llm' if planned else 'player')
                return done()
            return fail('LLM dialogue is disabled or no message was supplied')
        if action in ('share', 'claim'):
            if not target or target.id == a.id or combat.distance(a, target) > 3:
                return fail('Recipient must be nearby')
            claim = str(command.get('claim', command.get('message', '')))[:500]
            if not claim:
                return fail('Empty claim')
            if action == 'share' and not any(x.get('claim') == claim for x in a.knowledge):
                return fail('Cannot share information you do not know')
            trust = target.relationships.get(a.id, {}).get('trust', 0)
            learn(target, world.tick, claim, a.id, .4+trust*.3)
            world.event('claim', f'{a.name} shared an unverified claim with {target.name}: {claim}', [a.id, target.id])
            return done()
        if action == 'equip':
            if command.get('item') in a.equipment:
                a.activity = 'equip'
                return done()
            return fail('Equipment is not owned')
        if action in ('craft', 'teach', 'propose', 'vote', 'shipment'):
            method = {'craft': 'craft', 'teach': 'teach', 'propose': 'propose_policy', 'vote': 'vote', 'shipment': 'request_shipment'}[action]
            callback = getattr(world, method, None)
            if not callback:
                return fail('World capability unavailable')
            if action == 'craft':
                ok = callback(a, command.get('item', 'tools'))
            elif action == 'teach':
                ok = target and callback(a, target, command.get('topic', 'gather'))
            elif action == 'propose':
                ok = callback(a, command.get('policy', 'share_surplus'), command.get('kind'))
            elif action == 'vote':
                if type(command.get('approve', True)) is not bool:
                    return fail('Vote approve must be a boolean')
                ok = callback(a, command.get('proposal'), command.get('approve', True))
            else:
                ok = callback(a, command.get('destination'), command.get('offered', 'wood'), command.get('wanted', 'metal'), float(command.get('amount', 2)))
            return done() if ok else fail(f'{action} refused: unmet capability, ownership, proximity, or resource preconditions')
        if action == 'research':
            from .technology import research
            return done() if research(world, a, command.get('technology')) else fail('Research requires a supported method, skill, workshop, stamina and personal materials')
        if action == 'help':
            kind, amount = command.get('kind', 'food'), float(command.get('amount', 1))
            if target and target.id != a.id and combat.distance(a, target) <= 2 and 0 < amount <= 3 and kind in ('food', 'water') and world.transfer(a.inventory, target.inventory, kind, amount):
                world.relate(target, a, .03)
                world.event('help', f'{a.name} supplied {amount:g} {kind} to {target.name}.', [a.id, target.id])
                return done()
            return fail('Help requires a nearby recipient and owned food or water (up to three units)')
        if action == 'specialize':
            occupation = command.get('occupation')
            if occupation not in ('gatherer', 'builder', 'guard', 'farmer', 'miner', 'trader', 'craftsperson'):
                return fail('Unknown occupation')
            a.occupation = occupation
            world.event('specialize', f'{a.name} chose to work as {occupation}.', [a.id])
            return done()
        if action in ('negotiate', 'retreat', 'avoid', 'defend', 'fight', 'conflict_response'):
            if not target or not any(c.state == 'active' and {c.a, c.b} == {a.id, target.id} for c in world.conflicts.values()):
                # Peaceful contact can improve familiarity but cannot resolve somebody else's dispute.
                if action == 'negotiate' and target and combat.distance(a, target) <= 4 and not world.active(a.id):
                    world.relate(target, a, .01)
                    return done()
                return fail('Target must be your actual conflict opponent')
            choice = command.get('choice', action)
            if choice not in ('negotiate', 'retreat', 'avoid', 'defend', 'fight'):
                return fail('Unknown conflict strategy')
            a.combat_choice = choice
            a.combat_intent = {'choice': choice, 'expires': world.tick+40}
            if choice == 'negotiate' and combat.choose_response(target, a) in ('negotiate', 'avoid', 'retreat'):
                c = next(c for c in world.conflicts.values() if c.state == 'active' and {c.a, c.b} == {a.id, target.id})
                world.relate(a, target, .1)
                world.relate(target, a, .1)
                combat.finish(world, c, 'negotiated peace')
            return done()
        if action == 'challenge' and target:
            a.combat_choice = 'negotiate'
            if world.start_conflict(a.id, target.id, 'player challenge' if a.player else 'unresolved dispute'):
                return done()
            return fail('Cannot initiate this conflict')
    except (TypeError, ValueError, OverflowError) as exc:
        return fail(f'Invalid {action} arguments: {exc}')
    return fail(f'Unsupported action: {action}')
