"""Optional threats, private sightings, local alarms and voluntary human defense.

No nonhuman inference or generated speech. Positions, costs and non-graphic
combat outcomes are resolved by the existing authoritative simulation.
"""
import math
from . import combat
from .predators import move, sight

CHOICES = ('flee', 'shelter', 'request_help', 'defend', 'cooperate')
DEFAULTS = {'intensity': 1., 'max_zombies': 3, 'spawn_interval': 180,
            'night_only': True, 'grace_ticks': 360, 'spawn_regions': [],
            'wolf_aggression': .35}


def validate_settings(settings, width, height):
    if not isinstance(settings, dict) or set(settings) != set(DEFAULTS):
        raise ValueError('Unknown or missing threat setting')
    for key, low, high in [('intensity', 0, 2), ('max_zombies', 0, 8), ('spawn_interval', 60, 5000),
                           ('grace_ticks', 0, 10000), ('wolf_aggression', 0, 1)]:
        value = settings[key]
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Invalid threat setting: '+key)
        if key in ('max_zombies', 'spawn_interval', 'grace_ticks') and int(value) != value:
            raise ValueError('Threat counts and intervals must be integers')
    if type(settings['night_only']) is not bool:
        raise ValueError('night_only must be boolean')
    regions = settings['spawn_regions']
    if not isinstance(regions, list) or len(regions) > 8:
        raise ValueError('At most eight spawn rectangles are supported')
    for bounds in regions:
        if (not isinstance(bounds, list) or len(bounds) != 4
                or any(type(v) is not int for v in bounds)
                or not 0 <= bounds[0] <= bounds[2] < width
                or not 0 <= bounds[1] <= bounds[3] < height):
            raise ValueError('Spawn regions require integer bounds inside the map')


def initialize(world):
    settings = world.climate.setdefault('threat_settings', {})
    if not isinstance(settings, dict): raise ValueError('Invalid threat settings')
    for key, value in DEFAULTS.items():
        settings.setdefault(key, list(value) if isinstance(value, list) else value)
    for threat in world.threats.values():
        for key, value in {'max_hp': 35., 'target': None, 'last_seen': 0,
                           'last_attack': -100, 'last_move': -100}.items():
            threat.setdefault(key, value)
        if threat.get('hp') == 0: threat.setdefault('ended', threat.get('created', world.tick))


def reconcile(world):
    """Observer disabling/cap changes take effect even while the clock is paused."""
    settings = world.climate['threat_settings']
    disabled = not world.climate['threats_enabled'] or settings['intensity'] == 0
    cap = 0 if disabled else min(settings['max_zombies'], math.ceil(settings['max_zombies']*settings['intensity']))
    ordered = sorted(world.threats, key=lambda k: (world.threats[k]['created'], k))
    removed = set(ordered[int(cap):])
    if disabled:
        removed.update(key for actor in world.agents.values() for key, o in actor.observations.items() if o.get('species') == 'zombie' and o.get('kind') in ('threat','threat_report'))
    if not removed: return
    for key in removed:
        world.threats.pop(key, None)
        world._paths.pop('nonhuman:'+key, None)
    for actor in world.agents.values():
        for key in removed: actor.observations.pop(key, None)
        if actor.threat_state.get('target') in removed:
            for key in ('target','choice','response_tick'): actor.threat_state.pop(key, None)
        if actor.threat_intent.get('target') in removed: actor.threat_intent = {}
    for home in world.settlements.values():
        for key in removed: home.threat_alert.get('reports', {}).pop(key, None)
        home.threat_alert['active'] = bool(home.threat_alert.get('reports')) and home.threat_alert.get('until',0)>world.tick
    world.event('threats_disabled' if disabled else 'threats_rebalanced', 'Observer control removed optional zombies and cleared their live warnings; history is preserved.', [], removed=sorted(removed))


def view(world, target):
    if target in world.threats:
        return world.threats[target]
    animal = world.wildlife.get(target)
    if animal and animal.species == 'wolf':
        return {'id': animal.id, 'x': animal.x, 'y': animal.y, 'hp': animal.hp,
                'species': 'wolf', 'activity': animal.activity, 'stamina': animal.stamina,
                'target': animal.behavior.get('target')}
    return None


def dangerous(threat):
    return threat['hp'] > 0 and (threat['species'] == 'zombie' or threat['activity'] == 'territorial')


def separation(actor, threat):
    return math.hypot(actor.x-threat['x'], actor.y-threat['y'])


def visible(world, actor, threat):
    tower = any(b.home == actor.home and b.kind == 'watchtower' and b.complete
                and b.condition > 0 and combat.distance(actor, b) <= 3 for b in world.buildings.values())
    radius = (6 if world.daylight else 4) + (3 if tower else 0)
    return threat['hp'] > 0 and separation(actor, threat) <= radius and sight(world, actor.x, actor.y, threat['x'], threat['y'])


def safe_spawn(world, x, y):
    return (world.passable(x, y)
            and all(math.hypot(s.x-x, s.y-y) >= 9 for s in world.settlements.values())
            and all(math.hypot(b.x-x, b.y-y) >= 4 for b in world.buildings.values())
            and all(math.hypot(a.x-x, a.y-y) >= 7 for a in world.agents.values())
            and all(math.hypot(a.x-x, a.y-y) >= 2 for a in world.wildlife.values())
            and all(math.hypot(t['x']-x, t['y']-y) >= 4 for t in world.threats.values()))


def _spawn(world):
    config = world.climate['threat_settings']
    if world.tick < config['grace_ticks'] or (config['night_only'] and world.daylight): return
    cap = min(config['max_zombies'], math.ceil(config['max_zombies']*config['intensity']))
    interval = max(60, round(config['spawn_interval']/max(.25, config['intensity'])))
    if world.tick % interval or len(world.threats) >= cap: return
    regions = config['spawn_regions'] or [[1, 1, world.width-2, 3], [1, world.height-4, world.width-2, world.height-2]]
    candidates = [(x, y) for x0, y0, x1, y1 in regions
                  for x in range(int(x0), int(x1)+1) for y in range(int(y0), int(y1)+1)]
    world.rng.shuffle(candidates)
    for x, y in candidates:
        if not safe_spawn(world, x, y): continue
        tid = f'threat{world.next_event}'
        world.threats[tid] = {'id': tid, 'x': x, 'y': y, 'hp': 35., 'max_hp': 35.,
                             'stamina': 70., 'species': 'zombie', 'activity': 'wander',
                             'created': world.tick, 'target': None, 'last_seen': 0,
                             'last_attack': -100, 'last_move': -100}
        world.event('threat_spawned', 'An optional wanderer appeared outside inhabited areas.', [], threat=tid)
        break


def repel(world, actor, target):
    threat = view(world, target)
    if not threat or threat['hp'] <= 0 or actor.incapacitated or actor.stamina < 8:
        return {'ok': False, 'message': 'Repel needs a living threat and stamina'}
    if separation(actor, threat) > 2 or not sight(world, actor.x, actor.y, threat['x'], threat['y']):
        return {'ok': False, 'message': 'Threat is out of defensive reach or behind a barrier'}
    if world.tick-actor.threat_state.get('last_attack', -100) < 4:
        return {'ok': False, 'message': 'Defensive action is recovering; wait four ticks'}
    actor.threat_state['last_attack'] = world.tick
    actor.stamina -= 8
    actor.fatigue = min(100, actor.fatigue+1)
    actor.activity = 'defend'
    amount = round((10+actor.skills.get('combat', 1)+combat.attributes(actor, 'attack'))*(.6+.4*actor.stamina/100), 2)
    hp = max(0, threat['hp']-amount)
    if target in world.threats:
        world.threats[target]['hp'] = hp
        if hp == 0: world.threats[target].update(activity='dispersed', ended=world.tick, target=None)
    else:
        wolf = world.wildlife[target]
        wolf.hp, wolf.threat = hp, actor.id
        if hp == 0: wolf.activity = 'incapacitated'
    for item in actor.equipment:
        actor.equipment_condition[item] = max(0, actor.equipment_condition.get(item, 100)-.2)
    world.event('threat_repelled', f'{actor.name} defended against a {threat["species"]} for {amount:g} HP (non-graphic).', [actor.id], threat=target, amount=amount)
    if hp == 0:
        world.event('threat_dispersed', f'{actor.name} ended the encounter without graphic effects.', [actor.id], threat=target)
        for other in world.agents.values():
            if combat.distance(actor, other) <= 5 and sight(world,other.x,other.y,threat['x'],threat['y']):
                if target in other.observations: other.observations[target].update(hp=0, activity='dispersed', observed_tick=world.tick)
                if other.id != actor.id: world.relate(other, actor, .03)
    return {'ok': True, 'message': 'Defensive outcome resolved by the simulation'}


def _impact(world, threat, target, state, power):
    if (target.incapacitated or separation(target, threat) > 1.3 or threat['stamina'] < 8
            or world.tick-state.get('last_attack', -100) < 8
            or not sight(world, target.x, target.y, threat['x'], threat['y'])): return
    tower = any(b.kind == 'watchtower' and b.complete and b.condition > 0
                and b.home == target.home and combat.distance(target, b) <= 4 for b in world.buildings.values())
    shelter = any(b.kind in ('house', 'hall', 'barn') and b.complete and b.condition > 0
                  and combat.distance(target, b) <= 1.5 for b in world.buildings.values())
    protection = target.defense+combat.attributes(target, 'defense')+(4 if target.defending else 0)
    amount = round(max(1, power-protection*.5-(3 if tower else 0)-(2 if shelter else 0)), 2)
    target.hp = max(0, target.hp-amount)
    target.incapacitated = target.hp <= 0
    target.safety = min(100, target.safety+10)
    state['last_attack'] = world.tick
    state['stamina'] = max(0, threat['stamina']-8)
    world.event('threat_contact', f'{target.name} received a non-graphic {threat["species"]} impact ({amount:g} HP).', [target.id], threat=threat['id'], amount=amount)
    if target.incapacitated:
        world.event('incapacitated', f'{target.name} needs shelter, supplies and recovery.', [target.id])


def warn(world, actor, target):
    observation = actor.observations.get(target, {})
    if observation.get('kind') not in ('threat', 'threat_report') or world.tick-observation.get('observed_tick', -1000) > 100:
        return {'ok': False, 'message': 'Warn requires a recent personal sighting or sourced report'}
    if world.tick-actor.threat_state.get('last_warning', -100) < 60:
        return {'ok': True, 'message': 'Your recent warning is still active'}
    from .memory import learn
    actor.threat_state['last_warning'] = world.tick
    confidence = min(.65, observation.get('confidence',1)*.8)
    listeners = [a for a in world.agents.values() if a.id != actor.id and not a.incapacitated and combat.distance(actor, a) <= 8]
    for listener in listeners:
        # A direct observer retains their better evidence.
        existing = listener.observations.get(target, {})
        if existing.get('kind') != 'threat' or world.tick-existing.get('observed_tick', 0) > 4:
            listener.observations[target] = {**observation, 'kind': 'threat_report', 'source': actor.id,
                                             'confidence': confidence, 'received_tick': world.tick}
        learn(listener, world.tick, f'{actor.name} signaled {observation.get("species", "a threat")} {target} near ({observation["x"]:.0f}, {observation["y"]:.0f}).', actor.id, confidence)
    home = world.settlements[actor.home]
    if combat.distance(actor, home) <= 9:
        old = home.threat_alert
        fresh = target not in old.get('reports', {}) or world.tick-old.get('updated', 0) >= 100
        old.setdefault('reports', {})[target] = {k: observation[k] for k in ('x', 'y', 'observed_tick', 'species') if k in observation}
        old.update(until=world.tick+100, updated=world.tick, witness=actor.id)
        if fresh:
            world.event('settlement_warning', f'{home.name}: {actor.name} raised a local threat warning.', [actor.id]+[a.id for a in listeners], settlement=home.id, threat=target)
    world.event('threat_warning', f'{actor.name} signaled nearby inhabitants to watch for a threat.', [actor.id]+[a.id for a in listeners], threat=target)
    return {'ok': True, 'message': 'Local warning heard only within eight tiles'}


def report(world, actor, partner, target):
    """Transfer one sourced sighting through a real, nearby conversation action."""
    observation = actor.observations.get(target, {})
    if not partner or partner.id == actor.id or partner.incapacitated or combat.distance(actor, partner) > 3:
        return {'ok': False, 'message': 'Threat reports need a conscious nearby partner'}
    if observation.get('kind') not in ('threat', 'threat_report') or world.tick-observation.get('observed_tick', -1000) > 100:
        return {'ok': False, 'message': 'No recent private sighting to report'}
    from .memory import learn
    confidence = min(.6, observation.get('confidence',1)*.8)
    existing = partner.observations.get(target, {})
    if existing.get('kind') != 'threat' or existing.get('observed_tick', 0) < observation['observed_tick']:
        partner.observations[target] = {**observation, 'kind': 'threat_report', 'source': actor.id,
                                        'confidence': confidence, 'received_tick': world.tick}
    learn(partner, world.tick, f'{actor.name} reported {observation["species"]} {target} near ({observation["x"]:.0f}, {observation["y"]:.0f}), seen at tick {observation["observed_tick"]}.', actor.id, confidence)
    world.event('threat_report', f'{actor.name} shared a sourced sighting with {partner.name}.', [actor.id, partner.id], threat=target)
    return {'ok': True, 'message': 'One sourced report transferred; no private memories copied'}


def observe(world):
    candidates = list(world.threats.values())+[view(world, a.id) for a in world.wildlife.values() if a.species == 'wolf' and a.activity in ('territorial', 'warning')]
    for actor in world.agents.values():
        if actor.incapacitated: continue
        for threat in candidates:
            if not visible(world, actor, threat): continue
            old = actor.observations.get(threat['id'], {})
            actor.observations[threat['id']] = {'id': threat['id'], 'kind': 'threat', 'species': threat['species'],
                'x': threat['x'], 'y': threat['y'], 'activity': threat['activity'], 'hp': threat['hp'],
                'observed_tick': world.tick, 'source': actor.id, 'confidence': 1.}
            if old.get('kind') != 'threat' or world.tick-old.get('observed_tick', -1000) > 100:
                from .memory import learn
                learn(actor, world.tick, f'Observed {threat["species"]} {threat["id"]} near ({threat["x"]:.0f}, {threat["y"]:.0f}).', actor.id, 1, True)
                actor.next_reason_tick = world.tick
                actor.cognition_revision += 1
                world.event('threat_observed', f'{actor.name} observed a nearby {threat["species"]}.', [actor.id], threat=threat['id'])
                if not actor.player and dangerous(threat): warn(world, actor, threat['id'])
            elif not actor.player and dangerous(threat) and world.tick-actor.threat_state.get('last_warning', -100) >= 60:
                warn(world, actor, threat['id'])
        actor.observations = dict(list(actor.observations.items())[-80:])
    for home in world.settlements.values():
        alert = home.threat_alert
        alert['reports'] = {k: v for k, v in alert.get('reports', {}).items() if world.tick-v['observed_tick'] <= 100}
        active = bool(alert['reports']) and alert.get('until', 0) > world.tick
        if not active and alert.get('active'):
            world.event('settlement_safe', f'{home.name}: no new contact confirmed; the warning expired.', [], settlement=home.id)
        alert['active'] = active


def set_response(world, actor, target, choice):
    report = actor.observations.get(target, {})
    if choice not in CHOICES or report.get('kind') not in ('threat', 'threat_report') or world.tick-report.get('observed_tick', -1000) > 100:
        return {'ok': False, 'message': 'Choose flee/shelter/request_help/defend/cooperate for a recent observed or reported threat'}
    actor.threat_intent = {'target': target, 'choice': choice, 'expires': world.tick+100}
    return {'ok': True, 'message': 'Personal intention recorded; immediate health and stamina govern safety'}


def respond(world, actor):
    if actor.player or actor.incapacitated or world.active(actor.id): return False
    candidates = []
    for key, observation in actor.observations.items():
        if observation.get('kind') not in ('threat', 'threat_report') or world.tick-observation.get('observed_tick', -1000) > 100: continue
        actual = view(world, key)
        if actual and visible(world, actor, actual):
            if dangerous(actual): candidates.append(actual)
        elif actor.occupation == 'guard':
            known = {**observation, 'hp': observation.get('hp', 35), 'activity': observation.get('activity', 'search')}
            if dangerous(known) and 1 < separation(actor, known) <= 12:
                candidates.append(known)
    if not candidates:
        actor.threat_state.pop('target', None)
        return False
    threat = min(candidates, key=lambda t: separation(actor, t))
    gap = separation(actor, threat)
    if threat['activity'] == 'dormant' and gap > 2: return False
    # Intent actions must remain executable while a routine plan is paused.
    if actor.plan_status == 'active' and actor.plan_index < len(actor.plan) and actor.plan[actor.plan_index]['action'] in ('threat_response', 'warn'):
        from .planning import execute_plan
        execute_plan(world, actor)
    intent = actor.threat_intent
    choice = intent.get('choice') if intent.get('target') == threat['id'] and intent.get('expires', 0) >= world.tick else None
    if actor.hp < actor.max_hp*.35 or actor.stamina < 18:
        choice = 'shelter' if combat.distance(actor, world.settlements[actor.home]) < 7 else 'flee'
    if choice is None:
        allies = [a for a in world.agents.values() if a.id != actor.id and not a.incapacitated and a.defending and combat.distance(actor, a) < 4]
        if actor.occupation == 'guard': choice = 'defend'
        elif allies and actor.personality['courage'] > .65: choice = 'cooperate'
        elif actor.personality['courage'] > .8 and actor.personality['aggression'] > .55: choice = 'defend'
        elif actor.personality['sociability'] > .65: choice = 'request_help'
        else: choice = 'shelter' if combat.distance(actor, world.settlements[actor.home]) < 7 else 'flee'
    if actor.threat_state.get('choice') != choice or actor.threat_state.get('target') != threat['id']:
        world.event('threat_response', f'{actor.name} chose {choice.replace("_", " ")} in response to a {threat["species"]}.', [actor.id], threat=threat['id'], choice=choice)
    actor.threat_state.update(choice=choice, target=threat['id'], response_tick=world.tick)
    for kind, need in (('water', 'thirst'), ('food', 'hunger')):
        if getattr(actor, need) > 65 and world._consume(actor, kind, need): return True
    actor.reason = f'{choice.replace("_", " ").capitalize()}: local threat, health, stamina and personal priorities'
    if actor.plan_status == 'active' and actor.plan_index < len(actor.plan):
        step = actor.plan[actor.plan_index]
        if '_started' in step: step['_started'] += 1  # Pause elapsed work; preserve the plan.
    if choice in ('defend', 'cooperate'):
        actor.defending = True
        if gap <= 2:
            repel(world, actor, threat['id'])
        else:
            report = actor.observations[threat['id']]
            tx, ty = (threat['x'], threat['y']) if visible(world, actor, threat) else (report['x'], report['y'])
            world.move(actor, tx, ty)
        actor.activity = choice
        return True
    if choice == 'request_help': warn(world, actor, threat['id'])
    shelters = [b for b in world.buildings.values() if b.home == actor.home and b.complete and b.condition > 0
                and b.kind in ('house', 'hall', 'barn') and math.hypot(b.x-threat['x'], b.y-threat['y']) > gap]
    shelter = min(shelters, key=lambda b: combat.distance(actor, b), default=None)
    if choice in ('shelter', 'request_help') and shelter and gap > 1.5:
        if combat.distance(actor, shelter) > 1:
            world.move(actor, shelter.x, shelter.y, retreating=True)
            actor.activity = 'seek_shelter'
        else:
            actor.defending = True
            actor.activity = 'shelter'
            combat.recover(actor, True)
    else:
        options = world.neighbors(actor.x, actor.y)
        if options:
            tx, ty = max(options, key=lambda p: math.hypot(p[0]-threat['x'], p[1]-threat['y']))
            world.move(actor, tx, ty, retreating=True)
        actor.activity = 'flee'
    return True


def maintain(world, actor):
    """Idle builders may invest real supplies after a witnessed warning."""
    home = world.settlements[actor.home]
    if actor.occupation != 'builder' or not home.threat_alert.get('active') or combat.distance(actor, home) > 7: return False
    from .actions import execute
    structures = [b for b in world.buildings.values() if b.home == actor.home and b.kind in ('wall', 'gate', 'watchtower')]
    damaged = next((b for b in structures if b.complete and b.condition < 85), None)
    if damaged:
        if combat.distance(actor, damaged) > 2: return world.move(actor, damaged.x, damaged.y)
        if actor.inventory['wood'] >= 1:
            return execute(world, {'action': 'repair', 'building': damaged.id}, actor.id, True)['ok']
        if combat.distance(actor, home) <= 2:
            return execute(world, {'action': 'retrieve', 'kind': 'wood', 'amount': 1}, actor.id, True)['ok']
        return world.move(actor, home.x, home.y)
    pending = next((b for b in structures if not b.complete), None)
    if pending:
        if combat.distance(actor, pending) > 2: return world.move(actor, pending.x, pending.y)
        return execute(world, {'action': 'work', 'building': pending.id}, actor.id, True)['ok']
    if not structures and world.tick-home.threat_alert.get('last_project', -1000) >= 240:
        if combat.distance(actor, home) > 3: return world.move(actor, home.x, home.y)
        if world.construct(actor, 'watchtower'):
            home.threat_alert['last_project'] = world.tick
            return True
    return False


def update(world):
    initialize(world)
    reconcile(world)
    enabled = world.climate['threats_enabled'] and world.climate['threat_settings']['intensity'] > 0
    expired = [k for k, t in world.threats.items() if t['hp'] <= 0 and world.tick-t.get('ended', world.tick) >= 60]
    for key in expired:
        world.threats.pop(key)
        world._paths.pop('nonhuman:'+key, None)
    if enabled: _spawn(world)
    if world.tick % 4 == 0:
        for threat in world.threats.values():
            if threat['hp'] <= 0: continue
            if world.tick-threat['created'] > 1440:
                threat.update(hp=0, activity='dispersed', ended=world.tick, target=None)
                world.event('threat_departed', 'A wanderer left the region.', [], threat=threat['id'])
                continue
            threat['stamina'] = min(70, threat['stamina']+2)
            if world.daylight and world.climate['threat_settings']['night_only']:
                threat.update(activity='dormant', target=None)
                continue
            seen = [a for a in world.agents.values() if not a.incapacitated and separation(a, threat) <= 6
                    and sight(world, threat['x'], threat['y'], a.x, a.y)]
            target = min(seen, key=lambda a: separation(a, threat), default=None)
            if target: threat.update(target=target.id, last_seen=world.tick, last_location=[target.x, target.y])
            if target and separation(target, threat) <= 1.3:
                threat['activity'] = 'contact'
                _impact(world, threat, target, threat, 5)
            elif threat['stamina'] < 10:
                threat['activity'] = 'rest'
            elif threat.get('target') and world.tick-threat['last_seen'] <= 32:
                tx, ty = threat.get('last_location', [threat['x'], threat['y']])
                threat['x'], threat['y'], threat['stamina'], _ = move(world, threat['id'], threat['x'], threat['y'], threat['stamina'], tx, ty, .65)
                threat['activity'] = 'pursue' if target else 'search'
            else:
                if threat.get('target'): world.event('threat_escape', 'A wanderer lost contact; pursuit ended.', [], threat=threat['id'])
                threat.update(target=None, activity='wander')
                options = world.neighbors(threat['x'], threat['y'])
                if options:
                    tx, ty = world.rng.choice(options)
                    threat['x'], threat['y'], threat['stamina'], _ = move(world, threat['id'], threat['x'], threat['y'], threat['stamina'], tx, ty, .45)
        for animal in world.wildlife.values():
            if animal.species != 'wolf' or animal.hp <= 0 or animal.activity != 'territorial': continue
            target = world.agents.get(animal.behavior.get('target'))
            if target:
                state = {**animal.behavior, 'stamina': animal.stamina}
                _impact(world, view(world, animal.id), target, state, 6)
                animal.behavior['last_attack'] = state.get('last_attack', -100)
                animal.stamina = state['stamina']
    observe(world)
