"""Timed production with owned input escrow and resumable authoritative progress."""
from .registry import PRODUCTION, RESOURCES, mass, room
from .combat import distance


def start(world, actor, recipe_id, building_id=None):
    recipe=PRODUCTION.get(recipe_id)
    if recipe is None: return {'ok':False,'message':'Unknown production recipe'}
    current=world.production_jobs.get(actor.production_job)
    if current and current['state']=='working':
        if current['recipe']!=recipe_id: return {'ok':False,'message':'Finish or cancel the current production job first'}
        return {'ok':True,'pending':True,'message':'Production is in progress','job':current['id']}
    if current and current['state']=='completed' and current['recipe']==recipe_id:
        actor.production_job=None
        return {'ok':True,'pending':False,'message':'Production completed','job':current['id']}
    facilities=[b for b in world.buildings.values() if b.complete and b.condition>0 and b.home==actor.home and b.kind in recipe['facilities'] and distance(actor,b)<=2 and (not building_id or b.id==building_id)]
    if not facilities: return {'ok':False,'message':'Visit a completed compatible home production facility'}
    facility=min(facilities,key=lambda b:distance(actor,b))
    if facility.kind in ('campfire','hearth') and world.fires.get(facility.id,{}).get('fuel_ticks',0)<=0:
        return {'ok':False,'message':'Cooking needs a fueled fire'}
    if actor.incapacitated or actor.stamina<5: return {'ok':False,'message':'Production requires a conscious rested worker'}
    if any(actor.inventory.get(k,0)<v for k,v in recipe['inputs'].items()): return {'ok':False,'message':'Production inputs are not owned or insufficient'}
    output_mass=mass(recipe['outputs'])
    if mass(actor.inventory)-mass(recipe['inputs'])+output_mass>actor.carry_capacity: return {'ok':False,'message':'Production output exceeds carrying capacity'}
    if recipe.get('equipment') in actor.equipment: return {'ok':False,'message':'This equipment is already owned'}
    jid=f'job{world.next_event}'
    # Explicit escrow persists and can be refunded once; no output exists yet.
    for kind,amount in recipe['inputs'].items(): actor.inventory[kind]-=amount
    world.production_jobs[jid]={'id':jid,'actor':actor.id,'building':facility.id,'recipe':recipe_id,'escrow':dict(recipe['inputs']),
                                'progress':0.,'duration':recipe['duration'],'state':'working','created':world.tick}
    actor.production_job=jid
    world.event('production_started',f'{actor.name} started {recipe_id}.',[actor.id],job=jid)
    return {'ok':True,'pending':True,'message':'Inputs reserved; timed production started','job':jid}


def cancel(world,actor):
    job=world.production_jobs.get(actor.production_job)
    if not job or job['state']!='working': return {'ok':False,'message':'No active production job'}
    if mass(actor.inventory)+mass(job['escrow'])>actor.carry_capacity: return {'ok':False,'message':'Make carrying room before reclaiming reserved inputs'}
    for kind,amount in job['escrow'].items(): actor.inventory[kind]+=amount
    job['escrow']={}; job['state']='cancelled'; actor.production_job=None
    world.event('production_cancelled',f'{actor.name} reclaimed reserved production inputs.',[actor.id])
    return {'ok':True,'message':'Production cancelled and inputs returned once'}


def update(world):
    for job in world.production_jobs.values():
        if job['state']!='working': continue
        actor=world.agents.get(job['actor']); b=world.buildings.get(job['building'])
        if actor is None or b is None: continue
        recipe=PRODUCTION[job['recipe']]
        talking=any(c['state']=='active' and actor.id in c['participants'] for c in world.conversations.values())
        if actor.incapacitated or world.active(actor.id) or actor.threat_state.get('response_tick')==world.tick or talking or actor.hunger>75 or actor.thirst>75 or actor.stamina<5 or actor.fatigue>80 or distance(actor,b)>2: continue
        if b.kind in ('campfire','hearth') and world.fires.get(b.id,{}).get('fuel_ticks',0)<=0: continue
        actor.activity='produce'; actor.reason='Working on '+job['recipe']
        actor.stamina=max(0,actor.stamina-1)
        job['progress']=min(job['duration'],job['progress']+1+max(0,actor.skills.get('craft',1)-1)*.05)
        if job['progress']<job['duration']: continue
        if mass(actor.inventory)+mass(recipe['outputs'])>actor.carry_capacity:
            actor.plan_feedback='Production is ready but needs carrying room; deposit goods or cancel.'
            actor.next_reason_tick=world.tick
            continue
        for kind,amount in recipe['outputs'].items(): actor.inventory[kind]+=amount
        if recipe.get('equipment') and recipe['equipment'] not in actor.equipment: actor.equipment.append(recipe['equipment'])
        actor.skills['craft']=min(5,actor.skills.get('craft',1)+.05)
        job['escrow']={}; job['state']='completed'; job['completed']=world.tick
        world.event('production_completed',f'{actor.name} completed {job["recipe"]}.',[actor.id],job=job['id'])
    if world.tick%100==0:
        world.production_jobs={k:v for k,v in world.production_jobs.items() if v['state']=='working' or world.tick-v.get('completed',v['created'])<500}


def autonomous(world,actor):
    """Fallback specialization uses the same transactions; model plans take priority."""
    job=world.production_jobs.get(actor.production_job)
    if job and job['state']=='working':
        if job['progress']>=job['duration'] and mass(actor.inventory)+mass(PRODUCTION[job['recipe']]['outputs'])>actor.carry_capacity:
            store=world.settlements[actor.home]
            if distance(actor,store)>2: world.move(actor,store.x,store.y)
            else:
                for kind,amount in list(actor.inventory.items()):
                    if kind not in ('food','water') and amount>0 and sum(store.inventory.values())+amount<=world.capacity(store): world.transfer(actor.inventory,store.inventory,kind,amount)
            return True
        facility=world.buildings.get(job['building'])
        if facility and distance(actor,facility)>2: world.move(actor,facility.x,facility.y)
        else: actor.activity='produce'; actor.reason='Continuing reserved production work'
        return True
    # Deliver output before accepting more inputs; otherwise workers can fill their
    # packs and lose room for drinking water during a shortage.
    if sum(v for k,v in actor.inventory.items() if k not in ('food','water'))>=10: return False
    if actor.occupation not in ('craftsperson','farmer') or world.tick%15: return False
    store=world.settlements[actor.home]
    if distance(actor,store)>2: return False
    for rid in ('bread','cook_meat','planks','smelt_iron','refined_tools'):
        recipe=PRODUCTION[rid]
        facilities=[b for b in world.buildings.values() if b.complete and b.home==actor.home and b.kind in recipe['facilities'] and distance(actor,b)<=2]
        if not facilities: continue
        fire=next((b for b in facilities if b.kind in ('hearth','campfire')),None)
        if fire and not world.fires.get(fire.id,{}).get('lit'):
            if actor.inventory['wood']<1 and store.inventory['wood']>=1 and world.governance[actor.home].get('sharing',True): world.transfer(store.inventory,actor.inventory,'wood',1)
            if actor.inventory['wood']>=1:
                from .survival import action
                if action(world,actor,{'action':'fuel','building':fire.id})['ok']: return True
            continue
        missing={k:max(0,v-actor.inventory[k]) for k,v in recipe['inputs'].items()}
        if any(store.inventory.get(k,0)<v for k,v in missing.items()): continue
        if mass(actor.inventory)+mass(missing)>actor.carry_capacity: continue
        if not world.governance[actor.home].get('sharing',True) and actor.id not in store.council: continue
        for k,v in missing.items():
            if v: world.transfer(store.inventory,actor.inventory,k,v)
        result=start(world,actor,rid)
        if result['ok']: return True
    return False
