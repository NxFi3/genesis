"""Private, bounded, provenance-aware cognition contexts."""
import json
from .combat import distance


def remember(agent, tick, text, source, importance=1, confidence=1):
    agent.memories.append({'tick': tick, 'content': str(text)[:1200], 'source': source,
                           'importance': importance, 'confidence': min(1, max(0, confidence))})
    if len(agent.memories) > 120:
        removed = agent.memories.pop(next((i for i, m in enumerate(agent.memories) if m.get('importance', 1) < 3), 0))
        agent.reflection = (agent.reflection + ' ' + removed['content'])[-2000:]


def learn(agent, tick, claim, source, confidence=.5, observed=False):
    """A report is a belief, not a fact. Only this recipient acquires it."""
    claim = str(claim).strip()[:500]
    if not claim:
        return
    entry = {'claim': claim, 'source': source, 'tick': tick, 'confidence': min(1, max(0, confidence)),
             'status': 'observed' if observed else 'unverified'}
    existing = next((x for x in agent.knowledge if x.get('claim') == claim and x.get('source') == source), None)
    if existing:
        existing.update(entry)
    else:
        agent.knowledge.append(entry)
    agent.knowledge[:] = agent.knowledge[-80:]
    agent.beliefs = [dict(x) for x in agent.knowledge[-40:]]


def perceive(world, agent):
    nearby = [a for a in world.agents.values() if a.id != agent.id and distance(agent, a) <= 7]
    resources = [r for r in world.resources.values() if distance(agent, r) <= 9]
    buildings = [b for b in world.buildings.values() if distance(agent, b) <= 9]
    for resource in resources:
        agent.observations[resource.id] = {'id': resource.id, 'kind': resource.kind, 'x': resource.x, 'y': resource.y,
                                         'quantity': round(resource.quantity, 2), 'observed_tick': world.tick}
    for settlement in world.settlements.values():
        if settlement.id == agent.home or distance(agent, settlement) <= 9:
            agent.observations[settlement.id] = {'id': settlement.id, 'kind': 'settlement', 'name': settlement.name, 'x': settlement.x, 'y': settlement.y, 'observed_tick': world.tick}
    # Geography may be remembered, resource quantities are explicitly old observations.
    agent.observations = dict(list(agent.observations.items())[-80:])
    return {'location': [round(agent.x, 2), round(agent.y, 2)], 'tick': world.tick,
            'season': world.season, 'day_phase': getattr(world, 'day_phase', 'day'),
            'nearby_agents': [{'id': a.id, 'name': a.name, 'home': a.home, 'activity': a.activity,
                               'x': round(a.x, 2), 'y': round(a.y, 2)} for a in nearby],
            'resources': [x for key, x in agent.observations.items() if key in world.resources],
            'known_places': [x for key, x in agent.observations.items() if key in world.settlements],
            'buildings': [{'id': b.id, 'kind': b.kind, 'complete': b.complete, 'x': b.x, 'y': b.y} for b in buildings]}


def context(world, agent, query='', limit=12000):
    perception = perceive(world, agent)
    home = world.settlements[agent.home]
    state = {'identity': {'id': agent.id, 'name': agent.name, 'personality': agent.personality,
                          'occupation': agent.occupation, 'skills': agent.skills},
             'needs': {k: getattr(agent, k) for k in ('hp', 'stamina', 'hunger', 'thirst', 'fatigue', 'shelter', 'safety', 'social')},
             'inventory': agent.inventory, 'equipment': agent.equipment, 'perception': perception,
             'knowledge': agent.knowledge[-12:], 'relationships': agent.relationships,
             'goals': agent.goals[-5:], 'long_term_goals': agent.long_term_goals[-4:],
             'commitments': agent.commitments[-8:], 'plan': agent.plan[agent.plan_index:agent.plan_index+8],
             'conflicts': [{'opponent': c.b if c.a == agent.id else c.a, 'cause': c.cause} for c in world.conflicts.values() if c.state == 'active' and agent.id in (c.a, c.b)], 'failure': agent.plan_error, 'reflection': agent.reflection[-1200:],
             'memories': world.memories_for(agent.id, query, 8),
             'settlement': {'id': home.id, 'name': home.name, 'policy': home.policy}}
    # Stores are visible only when physically visiting the settlement store.
    if distance(agent, home) <= 3:
        state['settlement']['stores'] = dict(home.inventory)
        state['settlement']['public_methods'] = world.governance.get(home.id, {}).get('technology', [])
    # Trim whole records, never truncate into invalid JSON.
    for key in ('memories', 'knowledge', 'relationships', 'perception'):
        if len(json.dumps(state)) <= limit:
            break
        if key == 'perception':
            state[key]['resources'] = state[key]['resources'][-4:]
        elif key == 'relationships':
            state[key] = {k: v for k, v in list(state[key].items())[:4]}
        else:
            state[key] = state[key][-2:]
    if len(json.dumps(state)) > limit:
        state = {'identity': state['identity'], 'needs': state['needs'], 'inventory': state['inventory'],
                 'location': perception['location'], 'failure': agent.plan_error[:200]}
    return state
