"""Non-graphic conflict rules. No networking, rendering, or LLM dependency."""
from math import hypot

EQUIPMENT = {
    'staff': {'attack': 4, 'defense': 1, 'weight': 1},
    'shield': {'attack': 0, 'defense': 5, 'weight': 2},
    'padded_coat': {'attack': 0, 'defense': 3, 'weight': 1},
    'boots': {'attack': 0, 'defense': 0, 'weight': 0, 'speed': .15},
}
STRIKE_COST = 12
STRIKE_RANGE = 1.5


def distance(a, b):
    return hypot(a.x - b.x, a.y - b.y)


def attributes(agent, key):
    return sum(EQUIPMENT.get(item, {}).get(key, 0) for item in agent.equipment)


def damage(attacker, defender):
    """Stamina weakens attacks; equipment and a defensive stance absorb damage."""
    power = (7 + attributes(attacker, 'attack') + attacker.skills['combat'])
    power *= .5 + .5 * min(100, max(0, attacker.stamina)) / 100
    protection = defender.defense + attributes(defender, 'defense')
    if defender.defending:
        protection += 4
    return round(max(1, power - protection * .6), 2)


def strike(world, attacker, defender):
    if (attacker.incapacitated or defender.incapacitated or
            attacker.stamina < STRIKE_COST or distance(attacker, defender) > STRIKE_RANGE):
        return False
    amount = damage(attacker, defender)
    # A completed watchtower protects defenders in its immediate settlement area.
    tower = world.buildings.get(f'{defender.home}_watchtower')
    if tower and tower.complete and distance(defender, tower) <= 4:
        amount = max(1, amount - 3)
    attacker.stamina -= STRIKE_COST
    attacker.fatigue = min(100, attacker.fatigue + 2)
    defender.hp = max(0, defender.hp - amount)
    defender.incapacitated = defender.hp <= 0
    world.event('damage', f'{attacker.name} struck {defender.name} for {amount:g} HP.',
                [attacker.id, defender.id], amount=amount)
    world.relate(defender, attacker, -.04)
    if defender.incapacitated:
        world.event('incapacitated', f'{defender.name} is incapacitated and needs rest.', [defender.id])
    return True


def recover(agent, resting=False):
    """No instant revival: safe rest and met needs gradually restore health."""
    agent.stamina = min(100, agent.stamina + (7 if resting else 2))
    if resting:
        agent.fatigue = max(0, agent.fatigue - 5)
    if resting and agent.hunger < 75 and agent.thirst < 75:
        agent.hp = min(agent.max_hp, agent.hp + 1.5)
    if agent.incapacitated and agent.hp >= agent.max_hp * .2:
        agent.incapacitated = False


def choose_response(agent, opponent):
    """Utility choices respond to health, stamina, trust, temperament and strength."""
    if agent.hp < agent.max_hp * .35 or agent.stamina < 18:
        return 'retreat'
    if agent.player:
        return agent.combat_choice
    trust = agent.relationships.get(opponent.id, {}).get('trust', 0)
    if trust >= .15 or agent.personality['aggression'] < .35:
        return 'negotiate'
    if agent.personality['courage'] < .3:
        return 'avoid'
    if agent.personality['aggression'] < .65:
        return 'defend'
    return 'fight'


def retreat(world, agent, opponent):
    """Walk away on passable terrain, choosing the tile with greatest separation."""
    options = world.neighbors(agent.x, agent.y)
    if not options:
        agent.defending = True
        return False
    x, y = max(options, key=lambda p: hypot(p[0] - opponent.x, p[1] - opponent.y))
    return world.move(agent, x, y, retreating=True)


def finish(world, conflict, outcome):
    conflict.state = 'resolved'
    conflict.ended = world.tick
    conflict.outcome = outcome
    for aid in (conflict.a, conflict.b):
        world.agents[aid].defending = False
    world.event('conflict_end', f'Conflict resolved: {outcome}.', [conflict.a, conflict.b], conflict=conflict.id)


def update(world):
    for c in list(world.conflicts.values()):
        if c.state != 'active':
            continue
        a, b = world.agents[c.a], world.agents[c.b]
        if a.incapacitated or b.incapacitated:
            finish(world, c, 'incapacitation')
            continue
        if world.tick - c.started >= 80:
            finish(world, c, 'exhaustion truce')
            continue
        if distance(a, b) > 8:
            finish(world, c, 'separation')
            continue
        choices = {p.id: choose_response(p, q) for p, q in ((a, b), (b, a))}
        # A meaningful trust threshold prevents one forced conversation ending every dispute.
        if all(v in ('negotiate', 'defend') for v in choices.values()) and 'negotiate' in choices.values():
            world.relate(a, b, .12)
            world.relate(b, a, .12)
            for sid in {a.home, b.home}:
                world.settlements[sid].stability = min(100, world.settlements[sid].stability + 2)
            finish(world, c, 'negotiated peace')
            continue
        for actor, other in ((a, b), (b, a)):
            if actor.incapacitated or other.incapacitated:
                break
            response = choices[actor.id]
            actor.activity = response
            actor.reason = f'{response.title()} chosen from health, stamina, trust and temperament'
            actor.defending = response in ('defend', 'negotiate')
            if response in ('retreat', 'avoid'):
                retreat(world, actor, other)
            elif distance(actor, other) > STRIKE_RANGE:
                if response == 'fight':
                    world.move(actor, other.x, other.y)
            elif response in ('fight', 'defend'):
                strike(world, actor, other)
        if a.incapacitated or b.incapacitated:
            finish(world, c, 'incapacitation')
        elif all(v in ('avoid', 'retreat', 'negotiate') for v in choices.values()):
            finish(world, c, 'mutual disengagement')
    active_homes = set()
    for c in world.conflicts.values():
        if c.state == 'active':
            active_homes.update((world.agents[c.a].home, world.agents[c.b].home))
    for settlement in world.settlements.values():
        settlement.conflict = 'alert' if settlement.id in active_homes else 'peace'
        for other in world.settlements.values():
            if other.id != settlement.id:
                cross = any(c.state == 'active' and {world.agents[c.a].home, world.agents[c.b].home} == {settlement.id, other.id} for c in world.conflicts.values())
                settlement.diplomacy[other.id] = 'dispute' if cross else 'peace'
