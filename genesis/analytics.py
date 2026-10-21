"""Measured events and explicit proposal/acceptance/completion provenance.

Audit records are not agent memories. They are bounded in interactive worlds and
streamed to local files by experiments; natural-language rationales are not causes.
"""
from collections import Counter
import hashlib
import json


def initialize(world):
    if not hasattr(world,'research_stats'):world.research_stats={'events':{},'agents':{},'actions':{},'next_action':1}
    if not hasattr(world,'action_history'):world.action_history=[]
    world.audit_sink=None
    world._action_origin=None


def increment(target,key,amount=1):target[key]=target.get(key,0)+amount


def emit(world,record):
    record={'tick':world.tick,**record}
    if world.controls.get('audit',False):
        world.action_history.append(record);world.action_history[:]=world.action_history[-256:]
    sink=getattr(world,'audit_sink',None)
    if sink:sink(record)


def event(world,event):
    increment(world.research_stats['events'],event['kind'])
    for actor in event['actors']:
        stats=world.research_stats['agents'].setdefault(actor,{})
        increment(stats,event['kind'])


def proposal(world,actor,data,status,adopted=False):
    steps=data.get('plan',[]) if isinstance(data,dict) else []
    stats=world.research_stats['agents'].setdefault(actor,{})
    if status=='proposed':increment(stats,'llm_proposed_actions',len(steps) if isinstance(steps,list) else 0)
    if status=='rejected':increment(stats,'invalid_proposals')
    if adopted:increment(stats,'plans_adopted')
    record={'kind':'model_proposal','source':'llm','actor':actor,'stage':status,'adopted':adopted,
            'steps':steps if isinstance(steps,list) else [],'rationale_is_causal_evidence':False}
    emit(world,record)


def execute(world,command,actor,planned,origin,function):
    origin=origin or ('player' if world.agents.get(actor) and world.agents[actor].player else 'deterministic_fallback')
    previous=world._action_origin;world._action_origin=origin
    identity=f'action{world.research_stats["next_action"]}';world.research_stats['next_action']+=1
    try:result=function(world,command,actor,planned)
    finally:world._action_origin=previous
    stats=world.research_stats['agents'].setdefault(actor,{})
    accepted=bool(result.get('ok'));completed=accepted and not result.get('pending',False)
    increment(stats,'accepted_actions' if accepted else 'failed_actions')
    if completed:increment(stats,'completed_actions')
    increment(world.research_stats['actions'],origin)
    safe={k:v for k,v in command.items() if k not in ('message','claim')}
    record={'id':identity,'kind':'action','actor':actor,'source':origin,'command':safe,'accepted':accepted,'completed':completed,
            'message':result.get('message',''),'pending':bool(result.get('pending',False))}
    if 'job' in result:
        record['job']=result['job']
        job=world.production_jobs.get(result['job'])
        if job and 'audit' not in job:job['audit']={'id':identity,'source':origin,'actor':actor}
    emit(world,record)
    return result


def completion(world,job):
    audit=job.get('audit')
    if not audit:return
    increment(world.research_stats['agents'].setdefault(audit['actor'],{}),'delayed_completions')
    emit(world,{'kind':'completion','source':audit['source'],'actor':audit['actor'],'accepted_action':audit['id'],'job':job['id'],'completed':True})


def gini(values):
    values=sorted(max(0,float(v)) for v in values);n=len(values);total=sum(values)
    return sum((2*i-n-1)*v for i,v in enumerate(values,1))/(n*total) if n and total else 0.


def sample(world,cognition=None):
    from .families import adult
    humans=[a for a in world.agents.values() if not a.player]
    stock=Counter()
    for owner in [*world.agents.values(),*world.settlements.values()]:stock.update(owner.inventory)
    for household in world.households.values():stock.update(household['inventory'])
    for estate in world.estates.values():stock.update(estate['inventory'])
    for shipment in world.shipments.values():
        if shipment['state'] in ('in_transit','waiting','returning'):stock.update(shipment['cargo'])
    for job in world.production_jobs.values():stock.update(job.get('escrow',{}))
    counters=world.research_stats['events']
    result={'tick':world.tick,'population':len(humans),'adults':sum(adult(a) for a in humans),'dependents':sum(not adult(a) for a in humans),
            'households':sum(bool(h['members']) for h in world.households.values()),'births':counters.get('birth',0),'deaths':counters.get('natural_death',0),
            'settlements':len(world.settlements),'buildings':sum(b.complete for b in world.buildings.values()),'projects':sum(not b.complete for b in world.buildings.values()),
            'conversations':counters.get('dialogue',0),'offline_social_events':counters.get('social',0),'trade_volume':world.stats.get('traded',0),
            'agreements_fulfilled':counters.get('agreement_fulfilled',0),'food_stock':round(stock['food'],6),'water_stock':round(stock['water'],6),
            'wood_stock':round(stock['wood'],6),'personal_food_gini':round(gini(a.inventory['food'] for a in humans),6),
            'wildlife':sum(a.hp>0 for a in world.wildlife.values()),'zombies':sum(a['hp']>0 for a in world.threats.values()),
            'navigation_expanded':world.navigation['expanded'],'plan_completions':counters.get('plan_completed',0),'plan_failures':counters.get('plan_failed',0)}
    if cognition:
        metrics=cognition.status()['metrics']
        for k in ('completed','failed','stale','latency_ms','throughput_per_minute','input_tokens','output_tokens','usage_available'):
            result['inference_'+k]=metrics.get(k,None)
    return result


def fingerprint(world):
    payload=json.dumps(world.snapshot(True),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()
