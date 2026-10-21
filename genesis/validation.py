"""Semantic save validation before malformed state can enter the engine."""
import math


def validate_world(world):
    from .world import BUILDINGS, PASSABLE
    def finite(value, minimum=0, maximum=float('inf')):
        return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum
    def require(condition, message):
        if not condition:
            raise ValueError('Invalid saved world: '+message)
    def inventory(items):
        require(isinstance(items, dict) and all(isinstance(k, str) and finite(v) for k, v in items.items()), 'invalid inventory quantities')
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
        require(all(finite(getattr(agent, name), 0, 100) for name in ('stamina', 'hunger', 'thirst', 'fatigue', 'shelter', 'safety', 'social')), 'invalid need or stamina')
        require(finite(agent.speed, .01) and finite(agent.defense), 'invalid physical attributes')
        require(agent.incapacitated == (agent.hp < agent.max_hp*.2) if agent.incapacitated else agent.hp > 0, 'invalid incapacitation state')
        inventory(agent.inventory)
    for sid, settlement in world.settlements.items():
        require(sid == settlement.id, 'invalid settlement identity')
        position(settlement)
        inventory(settlement.inventory)
    for resource in world.resources.values():
        position(resource)
        require(finite(resource.capacity) and finite(resource.quantity, 0, resource.capacity), 'invalid resource quantity')
    for building in world.buildings.values():
        position(building)
        require(building.home in world.settlements and building.kind in BUILDINGS and finite(building.progress) and finite(building.condition, 0, 100), 'invalid building')
    for shipment in world.shipments.values():
        inventory(shipment['cargo'])
    return world
