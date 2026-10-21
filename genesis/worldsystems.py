"""Additive world-system initialization and backwards-compatible save defaults."""
import math
from .registry import expand, MINERALS
from .environment import initial
from .models import Resource, Building, Wildlife

BUILDING_TYPES={
    'barn':{'wood':18,'stone':6,'duration':18,'capacity':200,'shelter':4},
    'warehouse':{'planks':12,'bricks':8,'duration':24,'capacity':1000},
    'mine':{'wood':12,'stone':8,'duration':18},
    'furnace':{'stone':16,'clay':8,'duration':20},
    'blacksmith':{'planks':10,'stone':14,'duration':22},
    'carpenter':{'wood':16,'stone':6,'duration':16},
    'rain_collector':{'wood':8,'clay':4,'duration':12,'capacity':40},
    'campfire':{'wood':3,'stone':2,'duration':3},
    'hearth':{'wood':6,'stone':8,'duration':8},
    'wall':{'stone':8,'duration':8,'defense':2},
    'gate':{'wood':8,'stone':4,'duration':8,'defense':1},
}


def initialize(world,new=False):
    for name,default in [('climate',initial()),('crops',{}),('fires',{}),('production_jobs',{}),('gates',{}),('threats',{})]:
        if not hasattr(world,name): setattr(world,name,default)
    from .threats import initialize as initialize_threats
    initialize_threats(world)
    for a in world.agents.values(): a.inventory=expand(a.inventory)
    for s in world.settlements.values(): s.inventory=expand(s.inventory)
    for shipment in world.shipments.values(): shipment['cargo']=expand(shipment['cargo'])
    if not hasattr(world,'elevation'):
        world.elevation=[]
        for y in range(world.height):
            row=[]
            for x in range(world.width):
                t=world.terrain[y][x]
                h=.13+.10*math.sin(x*.28)*math.cos(y*.34)
                if t=='mountain': h+=max(0,x-world.width*.72)*.14
                row.append(round(-.1 if t in ('river','lake') else h,3))
            world.elevation.append(row)
    if not new: return
    for sid,s in world.settlements.items():
        # Explicit founding stock is generated once, never reapplied on load.
        s.inventory.update(seeds=12,plant_fiber=6,clay=12,coal=6,iron_ore=6)
        for i,(kind,dx,dy) in enumerate([('hearth',-2,-1),('furnace',2,-2),('carpenter',-2,2),('blacksmith',2,2)]):
            bid=f'{sid}_{kind}'
            world.buildings[bid]=Building(bid,kind,sid,s.x+dx,s.y+dy,100,True)
        for index,kind in enumerate(sorted(MINERALS)):
            if kind=='stone': continue
            x=min(world.width-2,int(s.x)+3+index%3)
            y=min(world.height-2,int(s.y)-4-index//3)
            quantity=100 if sid=='b' and kind in ('iron_ore','coal','gold_ore') else 35
            rid=f'{sid}_{kind}_vein'
            world.resources[rid]=Resource(rid,kind,x,y,quantity,quantity,source='mineral_vein')
        for kind,dx,dy,quantity,regen in [('seeds',-2,-3,40,.05),('plant_fiber',-4,2,60,.1),('fruit',-3,-2,80,.15),('vegetables',-4,-1,60,.12)]:
            rid=f'{sid}_{kind}_patch'
            world.resources[rid]=Resource(rid,kind,s.x+dx,s.y+dy,quantity,quantity,regen,source='vegetation')
        for i,occupation in [(2,'farmer'),(3,'miner'),(4,'craftsperson'),(5,'trader')]:
            if f'{sid}{i}' in world.agents:
                a=world.agents[f'{sid}{i}']; a.occupation=occupation
                if occupation=='farmer': a.inventory['seeds']=2
    for r in world.resources.values():
        if r.kind=='water': r.source='environmental_reserve'
    for i,(x,y) in enumerate([(world.width//2,8),(4,world.height-5)]):
        rid=f'fish_stock_{i}'
        world.resources[rid]=Resource(rid,'fish',x,y,50,50,.025,source='fish_habitat')
    for index,species in enumerate(('wolf','sheep')):
        x,y=world.width-5,5+index*2
        if world.passable(x,y): world.wildlife[f'v3_{species}']=Wildlife(f'v3_{species}',x,y,species=species)
