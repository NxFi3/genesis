"""Structured plans contain only bounded, engine-supported actions."""
from . import combat

# These are capabilities, not predefined goals or life scripts. Goals are free text.
SCHEMAS = {
    'move': {'target': 'visible/remembered entity id OR x and y coordinates', 'x': 'number optional', 'y': 'number optional'},
    'observe': {}, 'rest': {}, 'sleep': {}, 'eat': {}, 'drink': {},
    'gather': {'resource': 'resource id in perception'},
    'store': {'kind': 'resource name', 'amount': 'positive number'},
    'retrieve': {'kind': 'resource name', 'amount': 'positive number'},
    'build': {'kind': 'supported building id from building_costs, including furnace/blacksmith/mine/campfire/wall/gate', 'x': 'optional site x', 'y': 'optional site y'},
    'work': {'building': 'optional building id'},
    'repair': {'building': 'building id'},
    'craft': {'item': 'supported equipment or tools recipe'},
    'equip': {'item': 'owned equipment'},
    'trade': {'target': 'agent id', 'offered': 'resource', 'wanted': 'resource', 'amount': 'positive number'},
    'offer': {'target': 'agent id', 'offered': 'resource', 'wanted': 'resource', 'amount': 'positive number'},
    'commit_work': {'target': 'nearby conversation partner', 'building': 'visible unfinished home building'},
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
SCHEMAS.update({
    'propose_union': {'target':'familiar nearby unrelated adult id'},
    'accept_union': {'target':'adult proposer id; mutual consent at a shared residence'},
    'decline_union': {'target':'adult proposer id'},
    'leave_union': {}, 'create_household': {},
    'household_transfer': {'direction':'deposit/withdraw','kind':'resource','amount':'positive quantity','household':'optional owned household id'},
    'family_plan': {'target':'mutual adult partner id','choice':'raise_child/not_now'},
    'inherit': {'estate':'deceased person id','kind':'owned resource','amount':'positive quantity'},
    'threat_response': {'target': 'recent observed/reported threat id', 'choice': 'flee/shelter/request_help/defend/cooperate'},
    'warn': {'target': 'recent observed/reported threat id; local alarm, not dialogue'},
    'report_threat': {'target': 'nearby conversation partner id', 'threat': 'threat id in your recent private observations'},
    'repel': {'target':'nearby observed optional fantasy threat id'},
    'mine': {'resource':'visible finite mineral deposit id'},
    'fish': {'resource':'nearby fish habitat stock id'},
    'hunt': {'target':'nearby wildlife id; non-graphic deterministic hunting'},
    'collect_water': {'resource':'nearby environmental water reserve id'},
    'produce': {'recipe':'catalogue production recipe id', 'building':'optional nearby compatible home facility'},
    'cancel_production': {},
    'plant': {'building':'completed home farm id','crop':'wheat/vegetables'},
    'harvest': {'building':'mature home farm id'},
    'irrigate': {'building':'home farm id','amount':'owned water units, up to three'},
    'fuel': {'building':'completed home campfire/hearth','kind':'wood/coal/charcoal','amount':'positive owned units up to five'},
    'extinguish': {'building':'nearby home fire id'},
    'repair_equipment': {'item':'owned equipment id; consumes tool at workshop'},
    'gate': {'building':'nearby completed home gate','open':'boolean'},
})



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
    policy = data.get('plan_policy', 'keep')
    revision = data.get('revision_reason', '')
    if policy not in ('keep', 'append', 'replace') or not isinstance(revision, str) or len(revision) > 400:
        raise ValueError('Use keep/append/replace and a bounded revision_reason')
    if policy == 'replace' and len(revision.strip()) < 8:
        raise ValueError('Replacing a plan requires a meaningful revision_reason')
    conversation = data.get('conversation')
    if conversation is not None:
        if not isinstance(conversation, dict) or set(conversation)-{'target', 'topic', 'message'}:
            raise ValueError('Conversation requires target, topic and message only')
        for key, maximum in (('target', 80), ('topic', 100), ('message', 1200)):
            value = conversation.get(key, '')
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError('Conversation fields must be nonempty bounded text')
    dialogue_actions = data.get('dialogue_actions', [])
    if not isinstance(dialogue_actions, list) or len(dialogue_actions) > 2:
        raise ValueError('At most two dialogue actions may be proposed per turn')
    for action in dialogue_actions:
        if not isinstance(action, dict) or action.get('action') not in ('offer', 'accept', 'reject', 'help', 'teach', 'share', 'commit_work', 'conflict_response', 'report_threat','propose_union','accept_union','decline_union','family_plan'):
            raise ValueError('Unsupported dialogue action')
    if dialogue_actions:
        # Reuse exactly the same flat argument validation as ordinary plans.
        dialogue_actions = validate_plan({'plan': dialogue_actions})['plan']
    return {'goal': goal, 'plan': steps, 'speech': speech,
            'plan_policy': policy, 'revision_reason': revision.strip(),
            'conversation': conversation, 'dialogue_actions': dialogue_actions,
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
    agent.reason = f'Plan: {agent.plan_goal or (agent.goals[-1].get("description", "chosen goal") if agent.goals else "chosen goal")}; step {agent.plan_index+1}'
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


def adopt_plan(world, agent, proposal):
    """Conversation and periodic reflection preserve unfinished physical work by default."""
    proposed = proposal['plan']
    active = agent.plan_status == 'active' and agent.plan_index < len(agent.plan)
    policy = proposal['plan_policy']
    if not proposed:
        return False
    if active and policy == 'keep':
        agent.plan_feedback = 'Preserved unfinished plan; use append or replace with a concrete reason to change it.'
        return False
    if active and policy == 'append':
        if len(agent.plan)-agent.plan_index+len(proposed) > 16:
            agent.plan_feedback = 'Append refused: at most 16 unfinished steps are allowed.'
            return False
        # Keep the running step, including its engine-owned start time and progress.
        agent.plan = agent.plan[agent.plan_index:] + proposed
        agent.plan_index = 0
        agent.plan_feedback = 'Added steps after the current task.'
    else:
        if active:
            world.event('plan_revised', f'{agent.name} revised a plan: {proposal["revision_reason"]}', [agent.id])
        agent.plan, agent.plan_index, agent.plan_status = proposed, 0, 'active'
        agent.plan_goal = proposal['goal']
        agent.plan_feedback = 'Plan revised: '+proposal['revision_reason'] if active else 'New plan adopted.'
    agent.plan_error = ''
    return True
