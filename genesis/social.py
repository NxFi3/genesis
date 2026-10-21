"""Voluntary agreements and private, explicitly sourced information transfer."""
from .combat import distance
from .memory import learn
import math


def agreement_action(world, actor, command):
    action = command['action']
    def fail(message):
        return {'ok': False, 'message': message}
    if action == 'offer':
        recipient = world.agents.get(command.get('target'))
        offered, wanted = command.get('offered', 'wood'), command.get('wanted', 'food')
        amount = float(command.get('amount', 2))
        if not recipient or recipient.id == actor.id or distance(actor, recipient) > 3:
            return fail('Offer requires a nearby different recipient')
        if offered == wanted or offered not in actor.inventory or wanted not in recipient.inventory or not math.isfinite(amount) or amount <= 0 or actor.inventory[offered] < amount:
            return fail('Offer has invalid or unowned goods')
        pending = sum(x['state'] == 'proposed' and x['proposer'] == actor.id for x in world.agreements.values())
        if pending >= 3:
            return fail('Resolve existing offers first')
        aid = f'ag{world.next_event}'
        world.agreements[aid] = {'id': aid, 'proposer': actor.id, 'recipient': recipient.id,
                                'offered': offered, 'wanted': wanted, 'amount': amount,
                                'created': world.tick, 'expires': world.tick+100, 'state': 'proposed'}
        actor.commitments.append({'agreement': aid, 'state': 'proposed', 'tick': world.tick})
        actor.commitments[:] = actor.commitments[-30:]
        world.event('offer', f'{actor.name} offered {amount:g} {offered} for {wanted} to {recipient.name}.', [actor.id, recipient.id], agreement=aid)
        return {'ok': True, 'message': 'Offer proposed, not yet exchanged', 'agreement': aid}
    agreement = world.agreements.get(command.get('agreement'))
    if not agreement or agreement['recipient'] != actor.id or agreement['state'] != 'proposed':
        return fail('Only the intended recipient may accept/reject a pending offer')
    if world.tick >= agreement['expires']:
        agreement['state'] = 'expired'
        return fail('Offer expired')
    proposer = world.agents[agreement['proposer']]
    if action == 'reject':
        agreement['state'] = 'rejected'
        world.event('agreement_rejected', f'{actor.name} declined {proposer.name}\'s offer.', [actor.id, proposer.id])
        return {'ok': True, 'message': 'Offer rejected'}
    if distance(actor, proposer) > 2:
        return fail('Both participants must meet to exchange goods')
    # Explicit acceptance is still subject to mechanical ownership and stock checks.
    if not world.trade(proposer, actor, agreement['offered'], agreement['wanted'], agreement['amount']):
        return fail('Exchange cannot execute: stock or demand changed')
    agreement['state'] = 'fulfilled'
    for person in (actor, proposer):
        person.commitments.append({'agreement': agreement['id'], 'state': 'fulfilled', 'tick': world.tick})
        person.commitments[:] = person.commitments[-30:]
    world.event('agreement_fulfilled', f'{actor.name} accepted and fulfilled {proposer.name}\'s offer.', [actor.id, proposer.id])
    return {'ok': True, 'message': 'Accepted; goods exchanged'}


def hear(world, listener, speaker, text):
    """Listener gains only the utterance, not the speaker's entire private state."""
    trust = listener.relationships.get(speaker.id, {}).get('trust', 0)
    learn(listener, world.tick, text, speaker.id, .35+trust*.3)
    listener.social = max(0, listener.social-12)
    # Familiarity is observable; agreement/trust is not automatic obedience.
    r = listener.relationships.setdefault(speaker.id, {'trust': 0, 'familiarity': 0, 'cooperation': 0, 'rivalry': 0, 'reputation': 0})
    r['familiarity'] = min(1, r['familiarity']+.02)


def upkeep(world):
    for agreement in world.agreements.values():
        if agreement['state'] == 'proposed' and world.tick >= agreement['expires']:
            agreement['state'] = 'expired'
    if len(world.agreements) > 100:
        for key in list(world.agreements):
            if len(world.agreements) <= 100:
                break
            if world.agreements[key]['state'] != 'proposed':
                del world.agreements[key]
    for agent in world.agents.values():
        agent.knowledge[:] = agent.knowledge[-80:]
        agent.semantic_memory[:] = agent.semantic_memory[-60:]
        agent.beliefs[:] = agent.beliefs[-40:]
        agent.goals[:] = agent.goals[-12:]
        agent.long_term_goals[:] = agent.long_term_goals[-12:]
        agent.commitments[:] = agent.commitments[-30:]
