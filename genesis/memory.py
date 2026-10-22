"""Private, bounded, provenance-aware cognition contexts."""
import json
import re
import math
from .combat import distance
from .environment import conditions


def remember(agent, tick, text, source, importance=1, confidence=1):
    if not agent.memory_enabled:return
    agent.memories.append({'tick': tick, 'content': str(text)[:1200], 'source': source,
                           'importance': importance, 'confidence': min(1, max(0, confidence))})
    if len(agent.memories) > 120:
        removed = agent.memories.pop(next((i for i, m in enumerate(agent.memories) if m.get('importance', 1) < 3), 0))
        agent.reflection = (agent.reflection + ' ' + removed['content'])[-2000:]


def learn(agent, tick, claim, source, confidence=.5, observed=False):
    """A report is a belief, not a fact. Only this recipient acquires it."""
    if not agent.memory_enabled:return
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
    nearby_projects = []
    for project in world.architecture_projects.values():
        if project['state'] != 'active' or project['home'] != agent.home:
            continue
        if min(math.hypot(agent.x-b['x'], agent.y-b['y']) for b in project['parts']) <= 10:
            nearby_projects.append({'id': project['id'], 'kind': 'modular_project',
                                    'name': project['title'], 'purpose': project['purpose'],
                                    'progress': project['progress'], 'total': len(project['parts']),
                                    'origin': [project['parts'][0]['x'],project['parts'][0]['y']]})
    nearby_projects = nearby_projects[:6]
    x0, y0 = max(0, int(round(agent.x))-3), max(0, int(round(agent.y))-3)
    local_ground = []
    legend = {'plains': '.', 'forest': 'f', 'mountain': 'm', 'farmland': 'a', 'road': '=',
              'river': '~', 'lake': '~'}
    for yy in range(y0, min(world.height, y0+7)):
        local_ground.append(''.join(legend.get(world.terrain[yy][xx], '?') if world.passable(xx, yy) else '#'
                                    for xx in range(x0,min(world.width,x0+7))))
    return {'location': [round(agent.x, 2), round(agent.y, 2)], 'tick': world.tick,
            'nearby_architecture':nearby_projects,
            'local_ground':{'x':x0,'y':y0,'rows':local_ground,'legend':'. plains, f forest, m mountain, a farm, = road, ~ water, # blocked'},
            'climate': conditions(world,agent.x,agent.y), 'season': world.season, 'day_phase': 'day' if world.daylight else 'night', 'weather': world.weather,
            'nearby_agents': [{'id': a.id, 'name': a.name, 'home': a.home, 'activity': a.activity,
                               'x': round(a.x, 2), 'y': round(a.y, 2)} for a in nearby],
            'threat_reports': [dict(o) for o in agent.observations.values() if o.get('kind') in ('threat', 'threat_report') and world.tick-o.get('observed_tick', -1000) <= 100][-6:],
            'resources': [x for key, x in agent.observations.items() if key in world.resources],
            'known_places': [x for key, x in agent.observations.items() if key in world.settlements],
            'buildings': [{'id': b.id, 'kind': b.kind, 'complete': b.complete, 'progress': b.progress, 'home': b.home, 'x': b.x, 'y': b.y} for b in buildings]}


def context(world, agent, query='', limit=12000, partner_id=None):
    perception = perceive(world, agent)
    home = world.settlements[agent.home]
    words = set(re.findall(r'\w+', query.lower()))
    def rank(entry):
        claim = entry.get('claim', entry.get('content', ''))
        return (len(words & set(re.findall(r'\w+', claim.lower()))) + (2 if partner_id and entry.get('source') == partner_id else 0), entry.get('tick', 0))
    relevant = sorted(agent.knowledge, key=rank, reverse=True)[:10]
    nearby_ids = {a['id'] for a in perception['nearby_agents']}
    relations = sorted(agent.relationships.items(), key=lambda pair: (pair[0] == partner_id, pair[0] in nearby_ids, pair[1].get('familiarity', 0)), reverse=True)[:8]
    state = {'identity': {'id': agent.id, 'name': agent.name, 'personality': agent.personality,
                          'occupation': agent.occupation, 'skills': agent.skills},
             'family':{'age':agent.age,'stage':agent.life_stage,'household':agent.household,'partner':agent.partner,'parents':agent.parents,'children':agent.children,'intention':agent.family_intent},
             'needs': {k: getattr(agent, k) for k in ('hp', 'stamina', 'hunger', 'thirst', 'fatigue', 'warmth', 'shelter', 'safety', 'social')},
             'inventory': agent.inventory, 'carry_capacity':agent.carry_capacity, 'production_job':world.production_jobs.get(agent.production_job), 'equipment': agent.equipment, 'perception': perception,
             'knowledge': relevant, 'relationships': dict(relations),
             'semantic_memory': sorted(agent.semantic_memory, key=rank, reverse=True)[:3],
             'projects': [b for b in perception['buildings'] if not b['complete']] + perception['nearby_architecture'],
             'goals': agent.goals[-5:], 'long_term_goals': agent.long_term_goals[-4:],
             'commitments': agent.commitments[-8:], 'plan': [{k: v for k, v in step.items() if not k.startswith('_')} for step in agent.plan[agent.plan_index:agent.plan_index+8]],
             'plan_status': agent.plan_status, 'plan_goal': agent.plan_goal, 'plan_feedback': agent.plan_feedback,
             'threat_intent': agent.threat_intent,
             'conflicts': [{'opponent': c.b if c.a == agent.id else c.a, 'cause': c.cause} for c in world.conflicts.values() if c.state == 'active' and agent.id in (c.a, c.b)], 'failure': agent.plan_error, 'reflection': agent.reflection[-1200:],
             'memories': world.memories_for(agent.id, query, 8),
             'settlement': {'id': home.id, 'name': home.name, 'policy': home.policy}}
    # Stores are visible only when physically visiting the settlement store.
    if distance(agent, home) <= 3:
        state['settlement']['stores'] = dict(home.inventory)
        state['settlement']['projects'] = world.governance.get(home.id, {}).get('projects', [])
        state['settlement']['public_methods'] = world.governance.get(home.id, {}).get('technology', [])
    state['own_shipments'] = [s for s in world.shipments.values() if s['courier'] == agent.id and s['state'] in ('in_transit', 'returning', 'waiting')][-2:]
    # Trim whole records, never truncate into invalid JSON.
    for key in ('memories', 'knowledge', 'semantic_memory', 'projects', 'relationships', 'perception'):
        if len(json.dumps(state)) <= limit:
            break
        if key == 'perception':
            state[key]['resources'] = state[key]['resources'][-4:]
        elif key == 'relationships':
            state[key] = {k: v for k, v in list(state[key].items())[:4]}
        else:
            state[key] = state[key][:2]
    if len(json.dumps(state)) > limit:
        state = {'identity': state['identity'], 'needs': state['needs'], 'inventory': state['inventory'],
                 'location': perception['location'], 'failure': agent.plan_error[:200],
                 'family':state['family'],
                 'perception':{'tick':world.tick,'climate':perception['climate'],'nearby_agents':perception['nearby_agents'][:2],
                               'threat_reports':perception.get('threat_reports',[])[:2]}}
    return state
