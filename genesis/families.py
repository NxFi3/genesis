"""Mutual adult unions, physically owned household stores and bounded generations."""
import math
from dataclasses import asdict
from .combat import distance, recover, finish
from .registry import inventory, expand
from .memory import learn, remember
from . import genetics

DEFAULTS={'enabled':True,'ticks_per_year':10000,'population_cap':100,'max_age':80,'offline_fallback':False,'birth_interval_years':2}
ACTIONS={'propose_union','accept_union','decline_union','leave_union','create_household','household_transfer','family_plan','inherit'}


def stage(age):
    return 'infant' if age<2 else 'child' if age<12 else 'adolescent' if age<18 else 'adult' if age<65 else 'elder'


def adult(agent):
    return agent.age>=18 and agent.life_stage in ('adult','elder')


def initialize(world):
    for key,value in [('demography',dict(DEFAULTS)),('households',{}),('family_archive',{}),('family_offers',{}),('estates',{})]:
        if not hasattr(world,key):setattr(world,key,value)
    if not hasattr(world,'next_person'):world.next_person=1
    for agent in world.agents.values():
        if agent.birth_tick is None:agent.birth_tick=world.tick-int(agent.age*world.demography['ticks_per_year'])
        agent.life_stage=stage(agent.age)
        if not agent.appearance:agent.appearance=genetics.profile(world.seed,agent.id)
        if agent.household is None:
            hid='hh_'+agent.id
            agent.household=hid;agent.residence=f'{agent.home}_house'
            world.households[hid]={'id':hid,'members':[agent.id],'owners':[agent.id],'home':agent.home,'residence':agent.residence,'inventory':inventory(),'created':world.tick,'births':0}
    for household in world.households.values():
        household['inventory']=expand(household['inventory'])
        household.setdefault('owners',list(household['members']))


def record(world,identity):
    a=world.agents.get(identity)
    return asdict(a) if a else world.family_archive.get(identity)


def ancestors(world,identity,seen=None):
    seen=set() if seen is None else seen
    if identity in seen:return seen
    seen.add(identity);person=record(world,identity)
    if person:
        for parent in person.get('parents',[]):ancestors(world,parent,seen)
    return seen


def related(world,a,b):
    return bool(ancestors(world,a.id)&ancestors(world,b.id))


def tree(world,identity):
    person=record(world,identity)
    if not person:return None
    def short(key):
        r=record(world,key)
        return {k:r.get(k) for k in ('id','name','age','life_stage','parents','children','partner','appearance','birth_tick','death_tick')} if r else None
    peers={**world.family_archive,**{k:asdict(a) for k,a in world.agents.items()}}
    return {'person':short(identity),'parents':[short(p) for p in person['parents']],
            'children':[short(p) for p in person['children']],
            'siblings':[short(k) for k,r in peers.items() if k!=identity and set(person['parents'])&set(r.get('parents',[]))],
            'partner':short(person['partner']) if person.get('partner') else None,
            'history':person.get('family_history',[])[-24:]}


def event(world,kind,text,people,**extra):
    world.event(kind,text,[p.id for p in people],**extra)
    for p in people:
        p.family_history.append({'tick':world.tick,'kind':kind,'text':text})
        p.family_history[:]=p.family_history[-24:]


def action(world,actor,command):
    name=command['action'];target=world.agents.get(command.get('target'))
    def fail(text):return {'ok':False,'message':text}
    def done(text):return {'ok':True,'message':text}
    if not adult(actor):return fail('Household decisions require adulthood')
    if name in ('propose_union','accept_union','decline_union'):
        if not target or target.id==actor.id or not adult(target) or target.incapacitated or distance(actor,target)>3:return fail('A union requires two conscious adults within speaking distance')
        if related(world,actor,target):return fail('Close or ancestral kin cannot form a partnership')
        if actor.partner or target.partner:return fail('End an existing partnership before proposing another')
        key=':'.join(sorted([actor.id,target.id]));offer=world.family_offers.get(key)
        if name=='propose_union':
            if offer and offer['state']=='proposed' and world.tick<=offer['expires']:return fail('A proposal is already awaiting a response')
            if actor.relationships.get(target.id,{}).get('familiarity',0)<.1:return fail('Develop familiarity through actual interaction before a partnership proposal')
            world.family_offers[key]={'proposer':actor.id,'recipient':target.id,'state':'proposed','expires':world.tick+300}
            event(world,'union_proposed',f'{actor.name} proposed a voluntary household union to {target.name}.',[actor,target])
            return done('Proposal recorded; recipient consent is required')
        if not offer or offer['state']!='proposed' or offer['recipient']!=actor.id or offer['proposer']!=target.id or world.tick>offer['expires']:return fail('No current proposal addressed to you')
        if name=='decline_union':
            offer['state']='declined';event(world,'union_declined',f'{actor.name} declined a household union.',[actor,target]);return done('Declined without changing property')
        household=world.households[target.household]
        residence=world.buildings.get(household['residence'])
        if actor.home!=target.home or not residence or not residence.complete or residence.condition<=0 or distance(actor,residence)>3 or distance(target,residence)>3:return fail('Meet at a completed shared residence in the same settlement first')
        world.households[actor.household]['members'].remove(actor.id)
        household['members'].append(actor.id)
        if actor.id not in household['owners']:household['owners'].append(actor.id)
        actor.household=target.household;actor.residence=target.residence
        actor.partner=target.id;target.partner=actor.id;offer['state']='accepted'
        event(world,'union_formed',f'{actor.name} and {target.name} mutually formed a household; personal inventories remain separate.',[actor,target])
        return done('Mutual union formed; no resources combined')
    if name in ('leave_union','create_household'):
        previous=world.households[actor.household]
        if name=='create_household' and actor.partner:return fail('End your partnership before establishing a separate household')
        partner=world.agents.get(actor.partner)
        if partner:partner.partner=None
        actor.partner=None;actor.family_intent={}
        previous['members'].remove(actor.id)
        hid=f'hh_{actor.id}_{world.tick}_{len(world.households)}'
        world.households[hid]={'id':hid,'members':[actor.id],'owners':[actor.id],'home':actor.home,'residence':actor.residence,'inventory':inventory(),'created':world.tick,'births':0}
        actor.household=hid
        event(world,'household_created',f'{actor.name} established a separate household without moving shared stores.',[actor]+([partner] if partner else []))
        return done('Separate household established; shared goods remain jointly owned')
    if name=='household_transfer':
        h=world.households.get(command.get('household',actor.household))
        if not h or actor.id not in h.get('owners',h['members']):return fail('No ownership rights to this household store')
        residence=world.buildings.get(h['residence'])
        kind=command.get('kind');amount=command.get('amount',1);direction=command.get('direction','deposit')
        if not residence or distance(actor,residence)>2 or direction not in ('deposit','withdraw'):return fail('Visit the household residence to deposit or withdraw')
        if kind not in actor.inventory or type(amount) not in (int,float) or not math.isfinite(amount) or amount<=0:return fail('Invalid resource or quantity')
        source,destination=(actor.inventory,h['inventory']) if direction=='deposit' else (h['inventory'],actor.inventory)
        if direction=='deposit' and sum(destination.values())+amount>240:return fail('Household store is full')
        if not world.transfer(source,destination,kind,amount):return fail('Transfer exceeds owned stock or carrying capacity')
        event(world,'household_transfer',f'{actor.name} {direction}ed {amount:g} {kind} at the household store.',[actor],resource=kind,amount=amount)
        return done('Owned resources transferred')
    if name=='family_plan':
        if not target or actor.partner!=target.id or target.partner!=actor.id or actor.household!=target.household or command.get('choice') not in ('raise_child','not_now'):return fail('Family planning requires a mutual adult household partnership')
        actor.family_intent={'with':target.id,'choice':command['choice'],'tick':world.tick}
        event(world,'family_intention',f'{actor.name} chose {command["choice"].replace("_"," ")} as a personal family intention.',[actor])
        return done('Personal intention recorded; birth requires both adults, shelter and supplies')
    if name=='inherit':
        estate=world.estates.get(command.get('estate'))
        if not estate or actor.id not in estate['heirs'] or math.hypot(actor.x-estate['x'],actor.y-estate['y'])>2:return fail('Reach an estate for which you are an heir')
        kind=command.get('kind');amount=command.get('amount',1)
        if kind not in actor.inventory or type(amount) not in (int,float) or not math.isfinite(amount) or amount<=0 or not world.transfer(estate['inventory'],actor.inventory,kind,amount):return fail('Invalid or unavailable inheritance quantity')
        event(world,'inheritance',f'{actor.name} physically collected {amount:g} {kind} from an estate.',[actor]);return done('Estate resources collected')
    return fail('Unsupported household action')


def ready(world,h):
    adults=[world.agents[k] for k in h['members'] if k in world.agents and adult(world.agents[k]) and not world.agents[k].incapacitated]
    b=world.buildings.get(h['residence'])
    children=[a for a in world.agents.values() if not adult(a) and a.residence==h['residence']]
    return (len(adults)>=2 and b and b.complete and b.condition>0 and len(children)<6
            and sum(not a.player for a in world.agents.values())<world.demography['population_cap']
            and len(world.family_archive)<10000 and all(h['inventory'][k]>=8 for k in ('food','water'))
            and world.settlements[h['home']].stability>=50
            and all(distance(a,b)<=3 and a.hunger<65 and a.thirst<65 and a.hp>55 for a in adults[:2]))


def birth(world,h,parents):
    from .models import Agent
    b=world.buildings[h['residence']];identity=f'person{world.next_person}';world.next_person+=1
    baby=Agent(identity,f'Child {identity}',b.x,b.y,h['home'],age=0,birth_tick=world.tick,life_stage='infant',household=h['id'],residence=b.id,parents=[p.id for p in parents],inventory=inventory(),occupation='dependent',skills={'gather':.1,'build':.1,'combat':.1})
    baby.appearance=genetics.profile(world.seed,identity,[p.appearance for p in parents])
    baby.personality={'aggression':world.rng.uniform(.05,.85),'courage':world.rng.random(),'sociability':world.rng.random()}
    for kind in ('food','water'):h['inventory'][kind]-=2
    h['members'].append(identity);h['births']+=1;h['last_birth']=world.tick;h.pop('birth_due',None)
    for p in parents:
        p.children.append(identity);p.fatigue=min(100,p.fatigue+10);p.family_intent={}
        world.relate(baby,p,.2);world.relate(p,baby,.2)
    world.agents[identity]=baby
    event(world,'birth',f'{baby.name} joined the household and needs caregivers.',parents+[baby])
    return baby


def die(world,actor):
    from .production import cancel
    if actor.production_job:cancel(world,actor)
    event(world,'natural_death',f'{actor.name} died naturally; family history and property remain.',[actor])
    heirs=list(dict.fromkeys(actor.children+([actor.partner] if actor.partner else [])+world.households[actor.household]['members']))
    world.estates[actor.id]={'id':actor.id,'x':actor.x,'y':actor.y,'heirs':[k for k in heirs if k!=actor.id],'inventory':dict(actor.inventory),'equipment':list(actor.equipment)}
    record={k:getattr(actor,k) for k in ('id','name','age','life_stage','birth_tick','parents','children','partner','appearance','family_history')}
    record.update(death_tick=world.tick,knowledge=actor.knowledge[-12:]);world.family_archive[actor.id]=record
    for c in world.conflicts.values():
        if c.state=='active' and actor.id in (c.a,c.b):finish(world,c,'participant died naturally')
    partner=world.agents.get(actor.partner)
    if partner:partner.partner=None;partner.family_intent={}
    world.households[actor.household]['members'].remove(actor.id)
    for s in world.settlements.values():
        s.council=[k for k in s.council if k!=actor.id]
        if not s.council:s.council=[a.id for a in world.agents.values() if a.id!=actor.id and a.home==s.id and adult(a)][:2]
        if world.governance[s.id].get('leader')==actor.id:world.governance[s.id]['leader']=next(iter(s.council),None)
    world._paths.pop(actor.id,None);del world.agents[actor.id]


def update(world):
    if not world.demography['enabled']:return
    years=world.demography['ticks_per_year']
    for actor in list(world.agents.values()):
        if actor.player:continue
        previous=actor.life_stage;actor.age=round((world.tick-actor.birth_tick)/years,6);actor.life_stage=stage(actor.age)
        if previous!=actor.life_stage:
            if adult(actor):actor.occupation='gatherer';actor.next_reason_tick=world.tick;actor.cognition_revision+=1
            event(world,'life_stage',f'{actor.name} entered the {actor.life_stage} life stage.',[actor])
        if actor.age>=world.demography['max_age']:die(world,actor)
    for h in list(world.households.values()):
        parents=[world.agents[k] for k in h['members'] if k in world.agents and adult(world.agents[k]) and world.agents[k].partner in h['members']]
        if len(parents)!=2:continue
        mutual=all(p.family_intent.get('choice')=='raise_child' and p.family_intent.get('with') in [a.id for a in parents if a!=p] for p in parents)
        interval=years*world.demography['birth_interval_years']
        if mutual and ready(world,h) and world.tick-h.get('last_birth',-interval)>=interval:
            if 'birth_due' not in h:
                h['birth_due']=world.tick+max(1,int(years*.75))
                event(world,'family_expected','A household began an abstract, non-explicit family project.',parents)
            elif world.tick>=h['birth_due']:birth(world,h,parents)
        elif not mutual:h.pop('birth_due',None)
    if world.tick%120==0 and world.demography['offline_fallback'] and not world.cognition_config.get('enabled'):
        fallback(world)
    for key,offer in list(world.family_offers.items()):
        if offer['state']=='proposed' and world.tick>offer['expires']:offer['state']='expired'
        if offer['state']!='proposed' and world.tick-offer['expires']>300:del world.family_offers[key]


def fallback(world):
    """Explicit deterministic baseline: interaction history, mutual eligibility, no random pairing."""
    for a in sorted(world.agents.values(),key=lambda a:a.id):
        if a.player or not adult(a) or a.incapacitated or a.personality['sociability']<.55 or a.age>55:continue
        if a.partner:
            action(world,a,{'action':'family_plan','target':a.partner,'choice':'raise_child'})
            continue
        for b in sorted(world.agents.values(),key=lambda a:a.id):
            if b.id<=a.id or b.player or not adult(b) or b.partner or b.incapacitated or b.personality['sociability']<.55 or b.age>55 or distance(a,b)>3 or related(world,a,b):continue
            if any(p.relationships.get(q.id,{}).get('trust',0)<.35 or p.relationships.get(q.id,{}).get('familiarity',0)<.2 for p,q in ((a,b),(b,a))):continue
            answer=action(world,a,{'action':'propose_union','target':b.id})
            if answer['ok']:action(world,b,{'action':'accept_union','target':a.id})
            break


def autonomous(world,actor):
    h=world.households[actor.household]
    if not any(k in world.agents and not adult(world.agents[k]) for k in h['members']) and not actor.family_intent:return False
    b=world.buildings.get(h['residence'])
    dependents=[world.agents[k] for k in h['members'] if k in world.agents and not adult(world.agents[k])]
    if b and dependents and distance(actor,b)>2 and any(c.hunger>60 or c.thirst>60 for c in dependents):
        actor.reason='Returning to dependent children who need care'
        return world.move(actor,b.x,b.y)
    if not b or distance(actor,b)>2:return False
    for kind in ('food','water'):
        if h['inventory'][kind]>=10:continue
        available=max(0,actor.inventory[kind]-2)
        if available:
            return action(world,actor,{'action':'household_transfer','kind':kind,'amount':min(4,available),'direction':'deposit'})['ok']
        store=world.settlements[actor.home]
        if distance(actor,store)<=2 and store.inventory[kind]>8 and world.governance[actor.home].get('sharing',True):
            from .actions import execute
            return execute(world,{'action':'retrieve','kind':kind,'amount':2},actor.id,True)['ok']
    return False


def dependent(world,child):
    h=world.households[child.household];b=world.buildings.get(h['residence'])
    caregivers=[world.agents[k] for k in h['members'] if k in world.agents and adult(world.agents[k]) and not world.agents[k].incapacitated and distance(world.agents[k],child)<=3 and world.agents[k].threat_state.get('response_tick')!=world.tick]
    child.activity='rest' if child.life_stage=='infant' else 'learn'
    child.reason='Dependent: caregivers, food, water, shelter and education'
    if not caregivers or not b or distance(child,b)>3:return
    carer=caregivers[world.tick%len(caregivers)]
    for kind,need in (('food','hunger'),('water','thirst')):
        if getattr(child,need)>45 and h['inventory'][kind]>=1:
            h['inventory'][kind]-=1;setattr(child,need,max(0,getattr(child,need)-50));carer.fatigue=min(100,carer.fatigue+.5)
            world.event('childcare',f'{carer.name} provided one {kind} to {child.name}.',[carer.id,child.id],resource=kind,amount=1)
    if child.hunger<75 and child.thirst<75:recover(child,True)
    interval=max(10,world.demography['ticks_per_year']//4)
    if child.age>=2 and world.tick%interval==0:
        skill=max(carer.skills,key=carer.skills.get);child.skills[skill]=min(carer.skills[skill],child.skills.get(skill,0)+.1)
        if carer.knowledge:
            report=carer.knowledge[world.tick%len(carer.knowledge)]
            learn(child,world.tick,report['claim'],carer.id,report.get('confidence',.5)*.8)
        world.event('education',f'{child.name} learned {skill} from {carer.name}.',[carer.id,child.id],skill=skill)


def validate_world(world):
    config=world.demography
    if set(config)!=set(DEFAULTS) or any(type(config[k]) is not bool for k in ('enabled','offline_fallback')):raise ValueError('Invalid demographic configuration')
    for key,lo,hi in [('ticks_per_year',10,1000000),('population_cap',1,400),('max_age',18,150),('birth_interval_years',1,20)]:
        if type(config[key]) is not int or not lo<=config[key]<=hi:raise ValueError('Invalid demographic limit '+key)
    from .registry import RESOURCES
    all_people={**world.family_archive,**{k:asdict(v) for k,v in world.agents.items()}}
    colors={}
    def visit(key):
        if colors.get(key)==1:raise ValueError('Genealogy contains an ancestry cycle')
        if colors.get(key)==2:return
        if key not in all_people:raise ValueError('Genealogy references an unknown parent')
        colors[key]=1;p=all_people[key]
        if len(p.get('parents',[])) not in (0,2) or len(set(p.get('parents',[])))!=len(p.get('parents',[])):raise ValueError('Invalid parentage')
        genetics.validate(p['appearance'])
        for parent in p['parents']:
            visit(parent)
            if key not in all_people[parent]['children']:raise ValueError('Nonreciprocal parentage')
        colors[key]=2
    for key in all_people:visit(key)
    for key,a in world.agents.items():
        if not isinstance(a.age,(int,float)) or not math.isfinite(a.age) or a.age<0 or a.life_stage!=stage(a.age) or type(a.birth_tick) is not int:raise ValueError('Invalid human lifecycle')
        h=world.households.get(a.household)
        if not h or key not in h['members'] or a.home!=h['home']:raise ValueError('Invalid household membership')
        if a.partner:
            partner=world.agents.get(a.partner)
            if not partner or partner.partner!=key or not adult(a) or not adult(partner) or a.household!=partner.household or related(world,a,partner):raise ValueError('Invalid mutual adult partnership')
    for h in world.households.values():
        if h['home'] not in world.settlements or len(h['members'])!=len(set(h['members'])) or any(k not in world.agents or world.agents[k].household!=h['id'] for k in h['members']):raise ValueError('Invalid household ownership')
        if any(k not in RESOURCES or type(v) not in (int,float) or not math.isfinite(v) or v<0 for k,v in h['inventory'].items()):raise ValueError('Invalid household inventory')
    for estate in world.estates.values():
        if any(k not in RESOURCES or type(v) not in (int,float) or not math.isfinite(v) or v<0 for k,v in estate['inventory'].items()):raise ValueError('Invalid estate inventory')
