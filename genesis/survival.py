"""Abstract mining, hunting, crops, fuel, warmth and food; all effects use real stock."""
import math
from .combat import distance
from .registry import RESOURCES, MINERALS, room, mass
from .environment import conditions, region_at

CROPS={'wheat':{'duration':100,'yield':6},'vegetables':{'duration':75,'yield':8}}


def action(world,actor,command):
    name=command['action']
    fail=lambda text:{'ok':False,'message':text}
    done=lambda text,pending=False:{'ok':True,'message':text,'pending':pending}
    if name in ('mine','fish'):
        resource=world.resources.get(command.get('resource'))
        valid=resource and (resource.kind in MINERALS if name=='mine' else resource.kind=='fish')
        if not valid or distance(actor,resource)>2: return fail('Visit a valid nearby mineral deposit or fish stock')
        if actor.stamina<3 or resource.quantity<1 or room(actor,resource.kind)<1: return fail('Extraction needs stock, stamina and carrying room')
        job=actor.extraction
        if job.get('target')!=resource.id or job.get('action')!=name: actor.extraction={'target':resource.id,'action':name,'progress':0,'tick':-1}; job=actor.extraction
        job['auto']=bool(command.get('_continuous',False))
        if job['tick']!=world.tick:
            job['tick']=world.tick
            bonus=.5 if name=='mine' and any(b.kind=='mine' and b.home==actor.home and b.complete and b.condition>0 and distance(b,resource)<=3 for b in world.buildings.values()) else 0
            job['progress']+=1+bonus; actor.stamina-=2
        actor.activity=name
        if job['progress']<(4 if name=='mine' else 3): return done('Extraction in progress',True)
        resource.quantity-=1; actor.inventory[resource.kind]+=1; job['progress']=0;job['auto']=False
        skill='mining' if name=='mine' else 'fishing'
        actor.skills[skill]=min(5,actor.skills.get(skill,1)+.02)
        world.stats['gathered']+=1
        world.event(name,f'{actor.name} obtained one {resource.kind}.',[actor.id],resource=resource.id)
        return done('One real unit extracted')
    if name=='hunt':
        animal=world.wildlife.get(command.get('target'))
        if not animal or animal.hp<=0 or animal.harvested or distance(actor,animal)>2: return fail('Hunting requires living wildlife within two tiles')
        yields={'raw_meat':3,'hides':1}
        if animal.species=='sheep': yields['wool']=2
        if actor.stamina<5 or mass(actor.inventory)+mass(yields)>actor.carry_capacity: return fail('Hunting requires stamina and carrying room')
        animal.threat=actor.id; animal.hp=max(0,animal.hp-12); actor.stamina-=5; actor.activity='hunt'
        if animal.hp<=0:
            animal.harvested=True; animal.activity='incapacitated'
            for kind,amount in yields.items(): actor.inventory[kind]+=amount
            world.event('hunt_completed',f'{actor.name} obtained food and materials from a non-graphic hunt.',[actor.id],wildlife=animal.id)
        return done('Hunt resolved by the engine',animal.hp>0)
    if name=='collect_water':
        resource=world.resources.get(command.get('resource'))
        if not resource or resource.kind!='water' or distance(actor,resource)>2: return fail('Reach an environmental river, lake or well reserve')
        amount=min(2.,resource.quantity,room(actor,'water'))
        if amount<=0 or actor.stamina<1: return fail('No extractable water, stamina or carrying room')
        resource.quantity-=amount; actor.inventory['water']+=amount; actor.stamina-=1
        world.stats['gathered']+=amount
        world.event('water_collected',f'{actor.name} collected {amount:g} drinking water.',[actor.id],source=resource.id)
        return done('Environmental water collected into owned inventory')
    if name in ('plant','harvest','irrigate'):
        b=world.buildings.get(command.get('building'))
        if not b or not b.complete or b.kind!='farm' or b.home!=actor.home or distance(actor,b)>2: return fail('Visit a completed home farm')
        soil=world.climate['regions'][conditions(world,b.x,b.y)['region']]
        if name=='irrigate':
            amount=float(command.get('amount',2))
            if not math.isfinite(amount) or not 0<amount<=3 or actor.inventory['water']<amount: return fail('Irrigation consumes up to three owned water units')
            actor.inventory['water']-=amount; soil['moisture']=min(1,soil['moisture']+amount*.10)
            world.event('irrigated',f'{actor.name} used {amount:g} water to irrigate a farm.',[actor.id])
            return done('Owned water consumed; soil moisture increased')
        crop=world.crops.get(b.id)
        if name=='plant':
            kind=command.get('crop','wheat')
            if kind not in CROPS or actor.inventory['seeds']<1 or actor.inventory['water']<1 or crop and crop['stage']!='harvested': return fail('Planting needs a supported crop, seed, water and an empty plot')
            actor.inventory['seeds']-=1; actor.inventory['water']-=1
            world.crops[b.id]={'building':b.id,'kind':kind,'growth':0.,'stage':'seedling','planted':world.tick,'yield':0.}
            world.event('crop_planted',f'{actor.name} planted {kind}.',[actor.id])
            return done('Seed and water consumed; crop planted')
        if not crop or crop['stage']!='mature': return fail('Crop is not mature')
        amount=min(crop['yield'],room(actor,crop['kind']))
        if amount<crop['yield'] or mass(actor.inventory)+mass({crop['kind']:amount,'seeds':1})>actor.carry_capacity: return fail('Make carrying room for the harvest')
        actor.inventory[crop['kind']]+=amount
        # Seed reproduction is defined crop output, not a trade/resource transfer.
        actor.inventory['seeds']+=1
        crop['stage']='harvested'; world.stats['produced']+=amount; soil['harvested']+=amount
        soil['fertility']=max(.25,soil['fertility']-.01)
        world.event('harvest',f'{actor.name} harvested {amount:g} {crop["kind"]}.',[actor.id])
        return done('Harvest transferred to owned inventory')
    if name in ('fuel','extinguish'):
        b=world.buildings.get(command.get('building'))
        if not b or b.kind not in ('campfire','hearth') or not b.complete or b.home!=actor.home or distance(actor,b)>2: return fail('Visit a completed home campfire or hearth')
        fire=world.fires.setdefault(b.id,{'fuel_ticks':0.,'lit':False})
        if name=='extinguish': fire['fuel_ticks']=0; fire['lit']=False
        else:
            kind=command.get('kind','wood'); amount=float(command.get('amount',1))
            if kind not in ('wood','charcoal','coal') or not math.isfinite(amount) or not 0<amount<=5 or actor.inventory[kind]<amount or fire['fuel_ticks']+amount*(60 if kind!='wood' else 40)>400: return fail('Fuel needs owned wood/charcoal/coal and space below the fire cap')
            actor.inventory[kind]-=amount; fire['fuel_ticks']+=amount*(60 if kind!='wood' else 40); fire['lit']=True
        world.event(name,f'{actor.name} {name} at {b.kind}.',[actor.id],building=b.id)
        return done('Fire state updated with a real fuel cost')
    if name=='repair_equipment':
        item=command.get('item')
        if item not in actor.equipment or actor.inventory['tools']<1: return fail('Repair needs owned equipment and one tool')
        if not any(b.complete and b.kind in ('blacksmith','workshop') and b.home==actor.home and distance(actor,b)<=2 for b in world.buildings.values()): return fail('Visit a workshop or blacksmith')
        actor.inventory['tools']-=1; actor.equipment_condition[item]=100
        return done('Tool consumed; equipment repaired')
    if name=='gate':
        b=world.buildings.get(command.get('building'))
        opened=command.get('open')
        if not b or b.kind!='gate' or b.home!=actor.home or not b.complete or distance(actor,b)>2 or type(opened) is not bool: return fail('Operate a nearby completed home gate using a boolean open state')
        if not opened and any(distance(a,b)<.75 for a in world.agents.values()): return fail('Cannot close a gate on an occupant')
        world.gates[b.id]=opened; world._paths.clear(); world._blocked_tick=-1
        world.event('gate_changed',f'{actor.name} {"opened" if opened else "closed"} a gate.',[actor.id])
        return done('Gate pathfinding state changed')
    return fail('Unsupported survival action')


def update(world):
    for bid,fire in world.fires.items():
        b=world.buildings.get(bid)
        if not b: continue
        env=conditions(world,b.x,b.y)
        fire['fuel_ticks']=max(0,fire['fuel_ticks']-(1+env['precipitation']*(.6 if b.kind=='campfire' else 0)))
        fire['lit']=fire['fuel_ticks']>0
    for bid,crop in world.crops.items():
        if crop['stage'] in ('mature','harvested'): continue
        b=world.buildings.get(bid)
        if not b or not b.complete: continue
        env=conditions(world,b.x,b.y); soil=world.climate['regions'][env['region']]
        temperature=max(0,1-abs(env['temperature']-18)/23)
        crop['growth']+=temperature*soil['moisture']*soil['fertility']*(1-env['drought']*.5)
        crop['stage']='growing' if crop['growth']>CROPS[crop['kind']]['duration']*.25 else 'seedling'
        if crop['growth']>=CROPS[crop['kind']]['duration']:
            crop['stage']='mature'; crop['yield']=round(CROPS[crop['kind']]['yield']*max(.3,soil['fertility']),2)
    if world.tick%20==0:
        for owner in [*world.agents.values(),*world.settlements.values()]:
            barn=owner.id in world.settlements and any(b.complete and b.home==getattr(owner,'home',owner.id) and b.kind in ('barn','warehouse') for b in world.buildings.values())
            for kind,definition in RESOURCES.items():
                amount=owner.inventory.get(kind,0); rate=definition['spoilage']
                if amount>0 and rate:
                    lost=min(amount,amount*rate*20*(.3 if barn else 1))
                    owner.inventory[kind]=max(0,amount-lost)
                    world.stats['spoiled']=world.stats.get('spoiled',0)+lost
    for actor in world.agents.values():
        env=conditions(world,actor.x,actor.y)
        sheltered=any(b.complete and b.kind in ('house','hall','barn') and distance(actor,b)<=2 for b in world.buildings.values())
        heated=any(f['lit'] and bid in world.buildings and distance(actor,world.buildings[bid])<=3 for bid,f in world.fires.items())
        coat=any(item in actor.equipment for item in ('padded_coat','wool_coat','leather_coat'))
        cold=max(0,8-env['temperature'])*.035*world.climate['difficulty']
        actor.warmth=max(0,min(100,actor.warmth+cold*(.3 if coat else 1)*(.35 if sheltered else 1)-(.8 if sheltered else 0)-(1.4 if heated else 0)-(.2 if env['temperature']>8 else 0)))
        if actor.warmth>90 and world.tick%10==0:
            actor.hp=max(0,actor.hp-.2); actor.incapacitated=actor.hp<=0


def emergency(world,actor):
    if actor.warmth<55: return False
    sites=[b for b in world.buildings.values() if b.home==actor.home and b.complete and b.kind in ('house','hall','campfire','hearth')]
    if not sites: return False
    b=min(sites,key=lambda b:distance(actor,b))
    if distance(actor,b)>2:
        world.move(actor,b.x,b.y)
    elif b.kind in ('campfire','hearth') and not world.fires.get(b.id,{}).get('lit') and actor.inventory['wood']>=1:
        action(world,actor,{'action':'fuel','building':b.id})
    else:
        actor.activity='rest'; actor.reason='Seeking warmth and shelter from the local cold'
        from .combat import recover
        recover(actor,True)
    return True


def autonomous(world,actor):
    if actor.occupation=='farmer':
        plots=[b for b in world.buildings.values() if b.home==actor.home and b.kind=='farm' and b.complete]
        if plots:
            store=world.settlements[actor.home]
            sharing=world.governance[actor.home].get('sharing',True) or actor.id in store.council
            if actor.inventory['seeds']<1 and store.inventory['seeds']>=1 and sharing and distance(actor,store)<=2:
                world.transfer(store.inventory,actor.inventory,'seeds',1)
            b=min(plots,key=lambda b:distance(actor,b))
            crop=world.crops.get(b.id)
            if distance(actor,b)>2 and crop and crop['stage']=='mature': world.move(actor,b.x,b.y); return True
            if distance(actor,b)<=2:
                if crop and crop['stage']=='mature': return action(world,actor,{'action':'harvest','building':b.id})['ok']
                if (not crop or crop['stage']=='harvested') and actor.inventory['seeds']>=1 and actor.inventory['water']>=2:
                    return action(world,actor,{'action':'plant','building':b.id})['ok']
                if world.climate['regions'][b.home]['moisture']<.3 and actor.inventory['water']>=3:
                    return action(world,actor,{'action':'irrigate','building':b.id,'amount':2})['ok']
    if actor.occupation=='miner':
        deposits=[r for r in world.resources.values() if r.kind in ('iron_ore','coal','copper_ore') and r.quantity>=1 and room(actor,r.kind)>=1]
        if deposits and sum(actor.inventory[k] for k in MINERALS)<8:
            resource=min(deposits,key=lambda r:distance(actor,r))
            if distance(actor,resource)>2: world.move(actor,resource.x,resource.y); return True
            return action(world,actor,{'action':'mine','resource':resource.id})['ok']
    return False
