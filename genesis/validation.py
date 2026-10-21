"""Semantic save validation before malformed state can enter the engine."""
import math


def validate_world(world):
    from .world import BUILDINGS, PASSABLE
    from .registry import RESOURCES, PRODUCTION
    from .environment import WEATHER, SEASONS
    def finite(value, minimum=0, maximum=float('inf')):
        return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum
    def require(condition, message):
        if not condition:
            raise ValueError('Invalid saved world: '+message)
    def inventory(items):
        require(isinstance(items, dict) and all(k in RESOURCES and finite(v) for k, v in items.items()), 'invalid inventory quantities')
    def position(entity):
        require(finite(entity.x, 0, world.width-1) and finite(entity.y, 0, world.height-1), 'entity position outside world')
    require(type(world.width) is int and type(world.height) is int and world.width > 0 and world.height > 0, 'invalid dimensions')
    require(type(world.tick) is int and world.tick >= 0, 'invalid simulation time')
    require(len(world.terrain) == world.height and all(len(row) == world.width for row in world.terrain), 'invalid terrain dimensions')
    require(all(cell in {*PASSABLE, 'river', 'lake'} for row in world.terrain for cell in row), 'unknown terrain')
    for aid, agent in world.agents.items():
        require(agent.id == aid and agent.home in world.settlements, 'invalid agent ownership')
        position(agent)
        require(world.passable(agent.x, agent.y), 'agent on impassable terrain')
        require(finite(agent.max_hp, .01) and finite(agent.hp, 0, agent.max_hp), 'invalid health')
        require(all(finite(getattr(agent, name), 0, 100) for name in ('stamina', 'hunger', 'thirst', 'fatigue', 'shelter', 'safety', 'social','warmth')), 'invalid need or stamina')
        require(finite(agent.speed, .01) and finite(agent.defense), 'invalid physical attributes')
        require(agent.incapacitated == (agent.hp < agent.max_hp*.2) if agent.incapacitated else agent.hp > 0, 'invalid incapacitation state')
        inventory(agent.inventory)
        require(finite(agent.carry_capacity,1,10000),'invalid carrying capacity')
        require(all(k in agent.equipment and finite(v,0,100) for k,v in agent.equipment_condition.items()),'invalid equipment condition')
    for sid, settlement in world.settlements.items():
        require(sid == settlement.id, 'invalid settlement identity')
        position(settlement)
        inventory(settlement.inventory)
    for resource in world.resources.values():
        position(resource)
        require(resource.kind in RESOURCES,'unknown deposit resource')
        require(finite(resource.capacity) and finite(resource.quantity, 0, resource.capacity), 'invalid resource quantity')
    for building in world.buildings.values():
        position(building)
        require(building.home in world.settlements and building.kind in BUILDINGS and finite(building.progress) and finite(building.condition, 0, 100), 'invalid building')
    for shipment in world.shipments.values():
        inventory(shipment['cargo'])
    require(len(world.elevation)==world.height and all(len(row)==world.width and all(finite(v,-2,20) for v in row) for row in world.elevation),'invalid elevation')
    require(world.climate.get('season_override') in (None,*SEASONS),'invalid season override')
    require(finite(world.climate.get('difficulty'),.25,2) and type(world.climate.get('threats_enabled')) is bool,'invalid world controls')
    require(finite(world.climate.get('clock_offset'),-24,24),'invalid clock offset')
    for scope,env in world.climate['overrides'].items():
        require(scope in ('world','a','b','region') and env.get('weather') in WEATHER and finite(env.get('expires')),'invalid weather override')
        for key,lo,hi in [('temperature',-40,50),('precipitation',0,1),('wind',0,1),('snow',0,1),('drought',0,1)]:
            if key in env: require(finite(env[key],lo,hi),'invalid weather parameter')
        if scope=='region':
            bounds=env.get('bounds')
            require(isinstance(bounds,list) and len(bounds)==4 and all(finite(v) for v in bounds) and 0<=bounds[0]<=bounds[2]<world.width and 0<=bounds[1]<=bounds[3]<world.height,'invalid weather region bounds')
    require(type(world.climate.get('simulation_paused',False)) is bool and finite(world.climate.get('simulation_speed',2),.25,20),'invalid saved simulation controls')
    for soil in world.climate['regions'].values():
        require(all(finite(soil.get(k),0,1) for k in ('moisture','fertility','flood')),'invalid regional soil')
    for bid,crop in world.crops.items():
        require(bid in world.buildings and crop.get('kind') in ('wheat','vegetables') and finite(crop.get('growth')) and finite(crop.get('yield')) and crop.get('stage') in ('seedling','growing','mature','harvested'),'invalid crop')
    for bid,fire in world.fires.items():
        require(bid in world.buildings and finite(fire.get('fuel_ticks'),0,400) and type(fire.get('lit')) is bool,'invalid fire')
    for job in world.production_jobs.values():
        require(job.get('actor') in world.agents and job.get('building') in world.buildings and job.get('recipe') in PRODUCTION and finite(job.get('progress')) and job.get('duration')==PRODUCTION[job['recipe']]['duration'] and job.get('state') in ('working','completed','cancelled'),'invalid production job')
        inventory(job.get('escrow',{}))
        require(job['escrow']==PRODUCTION[job['recipe']]['inputs'] if job['state']=='working' else not job['escrow'],'invalid reserved production inputs')
    for bid,opened in world.gates.items(): require(bid in world.buildings and world.buildings[bid].kind=='gate' and type(opened) is bool,'invalid gate state')
    for animal in world.wildlife.values():
        position(animal)
        require(finite(animal.hp,0,100) and finite(animal.hunger,0,100) and animal.species in ('deer','boar','wolf','sheep') and type(animal.harvested) is bool,'invalid wildlife')
    require(len(world.threats)<=3,'threat population exceeds cap')
    for threat in world.threats.values():
        require(finite(threat.get('x'),0,world.width-1) and finite(threat.get('y'),0,world.height-1) and finite(threat.get('hp'),0,100) and finite(threat.get('stamina'),0,100),'invalid fantasy threat')
    return world
