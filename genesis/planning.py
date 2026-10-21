"""Structured plans contain only bounded, engine-supported actions."""
from . import combat

# These are capabilities, not predefined goals or life scripts. Goals are free text.
SCHEMAS = {
    'move': {'target': 'visible/remembered entity id OR x and y coordinates', 'x': 'number optional', 'y': 'number optional'},
    'observe': {}, 'rest': {}, 'sleep': {}, 'eat': {}, 'drink': {},
    'gather': {'resource': 'resource id in perception'},
    'store': {'kind': 'resource name', 'amount': 'positive number'},
    'retrieve': {'kind': 'resource name', 'amount': 'positive number'},
    'build': {'kind': 'house/farm/workshop/storage/market/watchtower/road/bridge/well/hall', 'x': 'optional site x', 'y': 'optional site y'},
    'work': {'building': 'optional building id'},
    'repair': {'building': 'building id'},
    'craft': {'item': 'supported equipment or tools recipe'},
    'equip': {'item': 'owned equipment'},
    'trade': {'target': 'agent id', 'offered': 'resource', 'wanted': 'resource', 'amount': 'positive number'},
    'offer': {'target': 'agent id', 'offered': 'resource', 'wanted': 'resource', 'amount': 'positive number'},
    'accept': {'agreement': 'agreement id'}, 'reject': {'agreement': 'agreement id'},
    'talk': {'target': 'nearby agent id', 'message': 'natural-language speech'},
    'share': {'target': 'nearby agent id', 'claim': 'a claim already in your knowledge'},
    'teach': {'target': 'nearby agent id', 'topic': 'known skill or knowledge'},
    'research': {'technology': 'crop_rotation/efficient_joinery (skill level 2, workshop and personal materials)'},
    'help': {'target': 'nearby agent id', 'kind': 'food/water', 'amount': 'positive number up to three'},
    'specialize': {'occupation': 'gatherer/builder/guard/farmer/miner/trader/craftsperson'},
    'propose': {'policy': 'share_surplus/rationing/open_trade/defense', 'kind': 'optional building project type'},
    'vote': {'proposal': 'proposal id', 'approve': 'boolean'},
    'shipment': {'destination': 'settlement id', 'offered': 'resource', 'wanted': 'resource', 'amount': 'positive number'},
    'conflict_response': {'target': 'opponent id', 'choice': 'negotiate/avoid/retreat/defend/fight'},
}


def validate_plan(data):
    if not isinstance(data, dict):
        raise ValueError('Model output must be a JSON object')
    goal = data.get('goal', '')
    plan = data.get('plan', [])
    if not isinstance(goal, str) or len(goal) > 500 or not isinstance(plan, list) or len(plan) > 16:
        raise ValueError('Expected goal text and at most 16 executable steps')
    steps = []
    for item in plan:
        if not isinstance(item, dict) or item.get('action') not in SCHEMAS:
            raise ValueError('Unknown or malformed plan action')
        action = item['action']
        if set(item) - {'action', *SCHEMAS[action]}:
            raise ValueError(f'Unsupported fields for {action}')
        for value in item.values():
            if isinstance(value, (dict, list)) or (isinstance(value, str) and len(value) > 1200):
                raise ValueError('Action fields must be bounded scalars')
            if isinstance(value, float):
                import math
                if not math.isfinite(value):
                    raise ValueError('Non-finite action value')
        steps.append(dict(item))
    speech = data.get('speech', '')
    if not isinstance(speech, str) or len(speech) > 2000:
        raise ValueError('Speech must be bounded text')
    return {'goal': goal, 'plan': steps, 'speech': speech,
            'reflection': str(data.get('reflection', ''))[:1000],
            'end_conversation': bool(data.get('end_conversation', False))}


def execute_plan(world, agent):
    if agent.plan_status != 'active' or agent.plan_index >= len(agent.plan):
        return False
    if agent.incapacitated or world.active(agent.id):
        return False
    from .actions import execute
    step = agent.plan[agent.plan_index]
    # Deterministic engine stamps elapsed time; model cannot set these fields.
    started = step.setdefault('_started', world.tick)
    if world.tick-started > 300:
        result = {'ok': False, 'message': 'Action timed out after 300 ticks'}
    else:
        result = execute(world, {k: v for k, v in step.items() if not k.startswith('_')}, actor_id=agent.id, planned=True)
    agent.reason = f'Plan: {agent.goals[-1].get("description", "chosen goal") if agent.goals else "chosen goal"}; step {agent.plan_index+1}'
    if not result['ok']:
        agent.plan_status = 'failed'
        agent.plan_error = result['message']
        agent.next_reason_tick = world.tick
        agent.cognition_revision += 1
        world.event('plan_failed', f'{agent.name}: {result["message"]}', [agent.id])
    elif not result.get('pending'):
        agent.plan_index += 1
        agent.plan_error = ''
        if agent.plan_index >= len(agent.plan):
            agent.plan_status = 'completed'
            agent.next_reason_tick = world.tick+5
            world.event('plan_completed', f'{agent.name} completed a plan.', [agent.id])
    return True
