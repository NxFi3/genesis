"""Deterministic regional climate and explicit, persistent God Mode interventions."""
import copy
import math

WEATHER = {
    'clear': (0, 0, .12), 'rain': (-2, .55, .25), 'heavy_rain': (-3, .9, .4),
    'snow': (-10, .45, .25), 'blizzard': (-18, .65, .9), 'thunderstorm': (-4, .85, .8),
    'fog': (-2, .15, .05), 'wind': (-3, 0, .7), 'heatwave': (13, 0, .2),
    'cold_snap': (-16, 0, .3), 'drought': (8, 0, .3),
}
SEASONS = ('spring','summer','autumn','winter')


def initial():
    return {'overrides': {}, 'regions': {sid: {'moisture': .65, 'fertility': .8, 'flood': 0., 'harvested': 0.} for sid in ('a','b')},
            'season_override': None, 'clock_offset': 0., 'difficulty': 1., 'threats_enabled': False}


def region_at(world, x, y):
    custom = world.climate['overrides'].get('region')
    if custom and custom['expires'] > world.tick:
        bounds = custom['bounds']
        if bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]: return 'region'
    return min(world.settlements.values(), key=lambda s: (s.x-x)**2+(s.y-y)**2).id


def conditions(world, x=None, y=None, region=None):
    region = region or (region_at(world, x, y) if x is not None else 'world')
    # Does not consume RNG; save/reload and offline runs are reproducible.
    choices = ('clear','rain','clear','wind','fog','drought','heavy_rain','thunderstorm','clear','heatwave','cold_snap','snow')
    weather = choices[(world.seed+world.tick//120)%len(choices)]
    if world.season == 'winter' and weather in ('rain','heavy_rain'): weather = 'snow'
    temperature = (15,24,11,0)[SEASONS.index(world.season)]
    delta, rain, wind = WEATHER[weather]
    result = {'weather':weather,'temperature':float(temperature+delta),'precipitation':rain,'wind':wind,
              'snow':rain if weather in ('snow','blizzard') else 0.,'drought':1. if weather=='drought' else 0.}
    for scope in ('world',region):
        override = world.climate['overrides'].get(scope)
        if override and override['expires'] > world.tick:
            if 'weather' in override:
                weather = override['weather']
                delta,rain,wind = WEATHER[weather]
                result.update(weather=weather,temperature=float(temperature+delta),precipitation=rain,wind=wind,
                              snow=rain if weather in ('snow','blizzard') else 0.,drought=1. if weather=='drought' else 0.)
            result.update({k:v for k,v in override.items() if k in result})
    result['region'] = region
    soil = world.climate['regions'].get(region,world.climate['regions'].get('a',{}))
    result['moisture'] = soil.get('moisture',.65)
    result['fertility'] = soil.get('fertility',.8)
    result['travel_factor'] = max(.35,1-result['precipitation']*.15-result['snow']*.25-result['wind']*.1-soil.get('flood',0)*.2)
    result['water_recharge'] = max(0,(.5+result['precipitation'])*(1-result['drought']))
    return result


def number(value, low, high, name):
    if type(value) not in (int,float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be a finite number in {low}..{high}')
    return float(value)


def intervene(world, command):
    """Validate the full intervention before changing any state. Not an NPC action."""
    operation = command.get('operation','weather')
    region = command.get('region','world')
    if region not in ('world','a','b','region'):
        raise ValueError('Region must be world, a, b or region')
    bounds = command.get('bounds')
    if region == 'region':
        if not isinstance(bounds,list) or len(bounds)!=4: raise ValueError('Selected region needs four bounds')
        bounds = [number(v,0,world.width-1 if i%2==0 else world.height-1,'bounds') for i,v in enumerate(bounds)]
        if bounds[0]>bounds[2] or bounds[1]>bounds[3]: raise ValueError('Invalid selected region bounds')
    candidate = copy.deepcopy(world.climate)
    if operation == 'weather':
        weather = command.get('weather','clear')
        if weather not in WEATHER: raise ValueError('Unknown weather')
        override = {'weather':weather,'expires':world.tick+int(number(command.get('duration',240),1,10000,'duration'))}
        for key, low, high in [('temperature',-40,50),('precipitation',0,1),('wind',0,1),('snow',0,1),('drought',0,1)]:
            if key in command: override[key] = number(command[key],low,high,key)
        if bounds: override['bounds'] = bounds
        candidate['overrides'][region] = override
        if region=='region': candidate['regions'].setdefault('region',{'moisture':.65,'fertility':.8,'flood':0.,'harvested':0.})
    elif operation == 'natural':
        if region == 'world': candidate['overrides'].clear(); candidate['season_override']=None; candidate['clock_offset']=0.
        else: candidate['overrides'].pop(region,None)
    elif operation == 'season':
        if command.get('season') not in SEASONS: raise ValueError('Unknown season')
        candidate['season_override'] = command['season']
    elif operation == 'time':
        hour = number(command.get('hour'),0,23.99,'hour')
        candidate['clock_offset'] = hour-world.tick%240/10
    elif operation == 'difficulty': candidate['difficulty']=number(command.get('value',1),.25,2,'difficulty')
    elif operation == 'threats':
        if type(command.get('enabled')) is not bool: raise ValueError('Threat enable must be boolean')
        candidate['threats_enabled']=command['enabled']
    elif operation == 'replenish':
        fraction=number(command.get('fraction',.25),0,1,'fraction')
        selected=[r for r in world.resources.values() if region=='world' or region_at(world,r.x,r.y)==region or region=='region' and bounds[0]<=r.x<=bounds[2] and bounds[1]<=r.y<=bounds[3]]
        for resource in selected: resource.quantity=min(resource.capacity,resource.quantity+resource.capacity*fraction)
    elif operation == 'spawn':
        species=command.get('species','deer')
        if species not in ('deer','boar','wolf','sheep'): raise ValueError('Unsupported species')
        if len(world.wildlife)>=24: raise ValueError('Wildlife population cap reached')
        x=number(command.get('x'),0,world.width-1,'x'); y=number(command.get('y'),0,world.height-1,'y')
        if not world.passable(x,y): raise ValueError('Wildlife needs passable land')
        from .models import Wildlife
        wid=f'w_god_{world.next_event}'
        world.wildlife[wid]=Wildlife(wid,x,y,species=species)
    else: raise ValueError('Unknown God Mode operation')
    world.climate=candidate
    world.event('god_intervention',f'God Mode: {operation} in {region}.',[],intervention={k:v for k,v in command.items() if k!='action'})
    # Humans learn changes only through subsequent local perception.
    return {'ok':True,'message':f'{operation.capitalize()} intervention applied and recorded'}


def update(world):
    for key, override in list(world.climate['overrides'].items()):
        if override['expires']<=world.tick:
            del world.climate['overrides'][key]
            world.event('weather_override_ended',f'Natural weather resumed in {key}.',[])
    for sid,soil in world.climate['regions'].items():
        env=conditions(world,region=sid)
        rain=env['precipitation']*(1-env['snow'])
        soil['moisture']=max(0,min(1,soil['moisture']+rain*.012-.0015-max(0,env['temperature']-20)*.00008-env['drought']*.006))
        soil['flood']=max(0,min(1,soil['flood']+(rain-.7)*.02))
        if world.tick%30==0 and env['weather']=='thunderstorm':
            for b in world.buildings.values():
                if b.home==sid and b.complete: b.condition=max(10,b.condition-.5)
    if world.tick%20==0:
        for a in world.agents.values():
            env=conditions(world,a.x,a.y)
            previous=a.observations.get('climate',{})
            a.observations['climate']={**env,'tick':world.tick}
            if env['weather']!=previous.get('weather') and (env['drought']>.5 or env['temperature']<0 or env['weather']=='thunderstorm'):
                world.event('environment_observed',f'{a.name} observed local {env["weather"]} and temperature {env["temperature"]:g}.',[a.id])
                a.next_reason_tick=world.tick
