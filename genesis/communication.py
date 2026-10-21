"""Grounded conversational opportunities, not scripted dialogue or forced encounters.

Only an agent's own memories, agreements and local observations enter these hints.
Models can decline them, and must author their own speech and explicit actions.
"""
from .combat import distance


def opportunities(world, agent, limit=3):
    if agent.incapacitated or world.active(agent.id):
        return []
    busy = {aid for c in world.conversations.values() if c['state'] == 'active' for aid in c['participants']}
    if agent.id in busy:
        return []
    home = world.settlements[agent.home]
    projects = [b for b in world.buildings.values() if not b.complete and distance(agent, b) <= 7]
    reports = [k for k in agent.knowledge if world.tick-k.get('tick', 0) <= 250]
    choices = []
    for other in world.agents.values():
        if other.id == agent.id or other.incapacitated or other.player or other.id in busy or distance(agent, other) > 3:
            continue
        if world.tick-agent.social_contacts.get(other.id, -1000) < 80:
            continue
        relationship = agent.relationships.get(other.id, {})
        topic, reason, score = '', '', 0
        offers = [a for a in world.agreements.values() if a['state'] == 'proposed' and {a['proposer'], a['recipient']} == {agent.id, other.id}]
        if offers:
            topic, reason, score = 'trade offer', f'Discuss pending offer {offers[-1]["id"]}; acceptance is voluntary.', 9
        elif relationship.get('rivalry', 0) > .2:
            topic, reason, score = 'disagreement', 'You remember unresolved rivalry; consider clarification, distance or a peaceful discussion.', 7
        elif agent.observations.get('climate',{}).get('drought',0)>.5 or agent.observations.get('climate',{}).get('temperature',20)<0:
            topic,reason,score='local weather','You observed difficult local weather; consider asking about water, shelter, fuel or cooperation.',6
        elif other.home != agent.home:
            topic, reason, score = 'cross-settlement contact', f'A visitor from {world.settlements[other.home].name} is within speaking distance; ask about needs without assuming their stocks.', 6
        elif projects:
            project = min(projects, key=lambda b: distance(agent, b))
            topic, reason, score = 'construction', f'You can see unfinished {project.kind} {project.id}; consider asking for help or discussing its materials.', 5
        elif distance(agent, home) <= 3 and any(home.inventory[kind] < 15 for kind in ('food', 'water', 'wood')):
            shortage = [kind for kind in ('food', 'water', 'wood') if home.inventory[kind] < 15]
            topic, reason, score = 'settlement needs', 'The home store you can inspect is short of '+', '.join(shortage)+'.', 5
        elif reports:
            report = max(reports, key=lambda k: k.get('tick', 0))
            topic, reason, score = 'news', f'You remember a report from {report["source"]}: {report["claim"][:200]}. Preserve its uncertainty when sharing.', 4
        elif agent.social > 40:
            topic, reason, score = 'company', 'You want company; ask about this neighbor\'s work or concerns.', 2
        if topic:
            # Personality/rivalry affects opportunities, but never generates a line of dialogue.
            score += agent.personality.get('sociability', .5) - distance(agent, other)*.1
            choices.append({'target': other.id, 'topic': topic, 'reason': reason, '_score': score})
    choices.sort(key=lambda c: (-c['_score'], c['target']))
    return [{k: v for k, v in choice.items() if k != '_score'} for choice in choices[:limit]]


def dialogue_context(world, agent, conversation):
    other_id = next(aid for aid in conversation['participants'] if aid != agent.id)
    other = world.agents.get(other_id)
    return {
        'id': conversation['id'], 'topic': conversation.get('topic', 'conversation'),
        'participants': conversation['participants'], 'turns': conversation['turns'][-6:],
        'partner': {'id': other_id, 'name': other.name if other else other_id,
                    'relationship': agent.relationships.get(other_id, {}),
                    'your_reports_from_them': [k for k in agent.knowledge if k.get('source') == other_id][-4:]},
        'outcomes': conversation.get('outcomes', [])[-4:],
        'instruction': 'Answer the latest question concretely. Distinguish witnessed facts from reports; ask a useful question only when needed. Do not repeat greetings or already settled points. You may disagree, refuse or end the conversation. Only confirmed outcomes below changed the world.'
    }
