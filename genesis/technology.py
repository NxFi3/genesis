"""Finite, extensible practical methods. This is not unrestricted invention."""
from .combat import distance
from .memory import learn

TECHNOLOGIES = {
    'crop_rotation': {'skill': 'gather', 'level': 2, 'cost': {'food': 6, 'tools': 1}, 'effect': 'farm_yield', 'multiplier': 1.2},
    'efficient_joinery': {'skill': 'build', 'level': 2, 'cost': {'wood': 6, 'tools': 1}, 'effect': 'construction', 'multiplier': 1.2},
}


def research(world, agent, name):
    definition = TECHNOLOGIES.get(name)
    if not definition or agent.incapacitated or agent.stamina < 8:
        return False
    if agent.skills.get(definition['skill'], 0) < definition['level']:
        return False
    if not any(b.home == agent.home and b.complete and b.kind == 'workshop' and distance(agent, b) <= 2 for b in world.buildings.values()):
        return False
    methods = world.governance[agent.home].setdefault('technology', [])
    if name in methods or any(agent.inventory.get(k, 0) < v for k, v in definition['cost'].items()):
        return False
    for kind, amount in definition['cost'].items():
        agent.inventory[kind] -= amount
    agent.stamina -= 8
    methods.append(name)
    learn(agent, world.tick, f'Practical method: {name}', agent.id, 1, observed=True)
    agent.semantic_memory.append({'content': name, 'source': 'experiment', 'confidence': 1, 'tick': world.tick})
    world.event('innovation', f'{agent.name} demonstrated {name} in the community workshop.', [agent.id])
    return True


def modifier(world, home, effect):
    result = 1
    for name in world.governance.get(home, {}).get('technology', []):
        definition = TECHNOLOGIES.get(name, {})
        if definition.get('effect') == effect:
            result *= definition['multiplier']
    return result
