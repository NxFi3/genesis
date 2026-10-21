"""Optional bounded fantasy encounters. Disabled worlds never spawn threats."""
import math
from .combat import distance


def repel(world,actor,target):
    threat=world.threats.get(target)
    if not threat or threat['hp']<=0 or actor.incapacitated or actor.stamina<8:
        return {'ok':False,'message':'Repel needs a living threat and stamina'}
    if math.hypot(actor.x-threat['x'],actor.y-threat['y'])>2:
        return {'ok':False,'message':'Threat is out of defensive reach'}
    actor.stamina-=8;actor.activity='defend'
    threat['hp']=max(0,threat['hp']-(10+actor.skills.get('combat',1)))
    if threat['hp']==0:
        threat['activity']='dispersed';threat['ended']=world.tick
        world.event('threat_dispersed',f'{actor.name} dispersed a fantasy threat without graphic effects.',[actor.id],threat=target)
    return {'ok':True,'message':'Defensive outcome resolved by the simulation'}


def update(world):
    if not world.climate['threats_enabled']:
        if world.threats:
            world.threats.clear()
            world.event('threats_disabled','Optional fantasy threats removed by world control.',[])
        return
    world.threats={k:v for k,v in world.threats.items() if v['hp']>0 or world.tick-v.get('ended',world.tick)<60}
    if world.tick%180==0 and len(world.threats)<3:
        options=[(2,3),(world.width-3,world.height-3),(3,world.height-3),(world.width-3,3)]
        for x,y in options:
            if world.passable(x,y) and not any(math.hypot(a.x-x,a.y-y)<7 for a in world.agents.values()) and not any(math.hypot(t['x']-x,t['y']-y)<4 for t in world.threats.values()):
                tid=f'threat{world.next_event}'
                world.threats[tid]={'id':tid,'x':x,'y':y,'hp':35.,'stamina':70.,'species':'zombie','activity':'wander','created':world.tick}
                world.event('threat_spawned','An optional fantasy wanderer appeared in the wilderness.',[],threat=tid)
                break
    if world.tick%4: return
    for threat in world.threats.values():
        if threat['hp']<=0: continue
        nearby=[a for a in world.agents.values() if not a.incapacitated and math.hypot(a.x-threat['x'],a.y-threat['y'])<=5]
        guards=[a for a in nearby if a.occupation=='guard' and not a.player]
        if guards:
            guard=min(guards,key=lambda a:math.hypot(a.x-threat['x'],a.y-threat['y']))
            if math.hypot(guard.x-threat['x'],guard.y-threat['y'])<=2: repel(world,guard,threat['id'])
        for a in nearby:
            # Local observation is private and becomes cognition input, never global knowledge.
            a.observations[threat['id']]={'id':threat['id'],'kind':'fantasy_threat','x':threat['x'],'y':threat['y'],'tick':world.tick}
            if world.tick%20==0: world.event('threat_observed',f'{a.name} observed a nearby fictional threat.',[a.id])
            if not a.player and a.occupation!='guard':
                choices=world.neighbors(a.x,a.y)
                if choices:
                    x,y=max(choices,key=lambda p:math.hypot(p[0]-threat['x'],p[1]-threat['y']))
                    world.move(a,x,y,retreating=True);a.activity='retreat'
        if threat['hp']<=0:continue
        target=min(nearby,key=lambda a:math.hypot(a.x-threat['x'],a.y-threat['y']),default=None)
        if not target: threat['activity']='wander';continue
        distance_to=math.hypot(target.x-threat['x'],target.y-threat['y'])
        if distance_to<=1.3 and threat['stamina']>=8:
            threat['stamina']-=8
            target.hp=max(0,target.hp-max(1,4-target.defense*.5));target.incapacitated=target.hp<=0
            world.event('threat_contact',f'{target.name} received a non-graphic impact from a fantasy threat.',[target.id],threat=threat['id'])
        else:
            choices=world.neighbors(threat['x'],threat['y'])
            if choices:
                x,y=min(choices,key=lambda p:math.hypot(p[0]-target.x,p[1]-target.y))
                threat['x'],threat['y']=x,y;threat['activity']='approach'
        threat['stamina']=min(70,threat['stamina']+2)
