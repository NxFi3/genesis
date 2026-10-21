"""Voluntary agreements and private, explicitly sourced information transfer."""
from .combat import distance
from .memory import learn, remember
import math


def sync_commitment(world, agreement):
    """One current record per party; a proposal is not a fulfilled promise."""
    for aid in (agreement['proposer'], agreement['recipient']):
        person = world.agents.get(aid)
        if person is None:
            continue
        person.commitments[:] = [c for c in person.commitments if c.get('agreement') != agreement['id']]
        person.commitments.append({'agreement': agreement['id'], 'state': agreement['state'], 'tick': world.tick,
                                   'partner': agreement['recipient'] if aid == agreement['proposer'] else agreement['proposer'],
                                   'description': f"Exchange {agreement['amount']:g} {agreement['offered']} for {agreement['wanted']}",
                                   'expires': agreement['expires']})
        person.commitments[:] = person.commitments[-30:]


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
        sync_commitment(world, world.agreements[aid])
        world.event('offer', f'{actor.name} offered {amount:g} {offered} for {wanted} to {recipient.name}.', [actor.id, recipient.id], agreement=aid)
        return {'ok': True, 'message': 'Offer proposed, not yet exchanged', 'agreement': aid}
    agreement = world.agreements.get(command.get('agreement'))
    if not agreement or agreement['recipient'] != actor.id or agreement['state'] != 'proposed':
        return fail('Only the intended recipient may accept/reject a pending offer')
    if world.tick >= agreement['expires']:
        agreement['state'] = 'expired'
        sync_commitment(world, agreement)
        return fail('Offer expired')
    proposer = world.agents.get(agreement['proposer'])
    if proposer is None:
        return fail('Offer proposer is no longer available')
    if action == 'reject':
        agreement['state'] = 'rejected'
        sync_commitment(world, agreement)
        world.event('agreement_rejected', f'{actor.name} declined {proposer.name}\'s offer.', [actor.id, proposer.id])
        return {'ok': True, 'message': 'Offer rejected'}
    if distance(actor, proposer) > 2:
        return fail('Both participants must meet to exchange goods')
    # Explicit acceptance is still subject to mechanical ownership and stock checks.
    if not world.trade(proposer, actor, agreement['offered'], agreement['wanted'], agreement['amount'], accepted=True):
        return fail('Exchange cannot execute: stock or demand changed')
    agreement['state'] = 'fulfilled'
    sync_commitment(world, agreement)
    for person, other in ((actor, proposer), (proposer, actor)):
        remember(person, world.tick, f'Completed exchange {agreement["id"]} with {other.name}; goods actually received.', 'engine_confirmation', 3)
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
            sync_commitment(world, agreement)
            world.event('offer_expired', f'Offer {agreement["id"]} expired without exchange.', [agreement['proposer'], agreement['recipient']])
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


def commit_work(world, actor, partner, building_id):
    building = world.buildings.get(building_id)
    if not partner or partner.id == actor.id or distance(actor, partner) > 3:
        return {'ok': False, 'message': 'A work commitment requires a nearby partner'}
    if not building or building.complete or building.home != actor.home or distance(actor, building) > 9:
        return {'ok': False, 'message': 'Commit to an unfinished visible home project'}
    if any(c.get('building') == building_id and c['state'] == 'active' for c in actor.commitments):
        return {'ok': False, 'message': 'You already committed to this project'}
    if sum(c.get('building') is not None and c['state'] == 'active' for c in actor.commitments) >= 2:
        return {'ok': False, 'message': 'Complete your existing work commitments first'}
    actor.commitments.append({'building': building.id, 'partner': partner.id, 'state': 'active',
                              'description': 'Contribute work to '+building.kind, 'tick': world.tick,
                              'expires': world.tick+300, 'contributed': 0})
    world.event('work_committed', f'{actor.name} agreed with {partner.name} to help build the {building.kind}.', [actor.id, partner.id])
    return {'ok': True, 'message': 'Work commitment recorded; unfinished plans and urgent needs take priority'}


def work_commitments(world, actor):
    """Idle agents honor self-chosen commitments through the usual engine actions."""
    from .actions import execute
    for commitment in actor.commitments:
        if not commitment.get('building') or commitment['state'] != 'active':
            continue
        building = world.buildings.get(commitment['building'])
        finished = building and building.complete
        if not building or finished or world.tick >= commitment['expires']:
            contributed = commitment.get('contributed', 0) > 0
            commitment['state'] = 'fulfilled' if contributed else 'superseded' if finished else 'expired'
            partner = world.agents.get(commitment['partner'])
            if partner and contributed:
                world.relate(partner, actor, .05)
                world.relate(actor, partner, .02)
            world.event('work_commitment_closed', f'{actor.name}: {commitment["description"]} — {commitment["state"]}.', [actor.id, commitment['partner']])
            continue
        if distance(actor, building) > 2:
            result = execute(world, {'action': 'move', 'target': building.id}, actor.id, planned=True)
        else:
            result = execute(world, {'action': 'work', 'building': building.id}, actor.id, planned=True)
        actor.reason = 'Honoring work commitment: '+commitment['description']
        if not result['ok']:
            actor.plan_feedback = result['message']
            # Let ordinary survival/recovery proceed; do not erase the commitment.
            return False
        return True
    return False
