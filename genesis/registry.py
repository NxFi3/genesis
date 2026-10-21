"""Data-driven game units, nutrition, mass, decay and finite transformation recipes."""
import json
from pathlib import Path

_DATA = json.loads((Path(__file__).parent/'data'/'resources.json').read_text())
RESOURCES = _DATA['resources']
PRODUCTION = _DATA['recipes']
ALIASES = {'drinking_water': 'water'}
MINERALS = {key for key, value in RESOURCES.items() if value['category'] == 'mineral'}


def inventory():
    return dict.fromkeys(RESOURCES, 0.)


def expand(items):
    return {**inventory(), **items}


def mass(items):
    return sum(amount*RESOURCES.get(kind, {}).get('mass', 1) for kind, amount in items.items())


def room(actor, kind):
    return max(0, actor.carry_capacity-mass(actor.inventory))/RESOURCES[kind]['mass']


def validate_registry():
    if len(RESOURCES) != len(set(RESOURCES)):
        raise ValueError('Duplicate resource identifiers')
    for key, item in RESOURCES.items():
        if item['id'] != key or item['mass'] <= 0 or not 0 <= item['spoilage'] <= 1:
            raise ValueError('Invalid resource definition')
    for recipe in PRODUCTION.values():
        if recipe['duration'] <= 0 or not recipe['inputs'] or not recipe['facilities']:
            raise ValueError('Recipe requires duration, inputs and facility')
        for items in (recipe['inputs'], recipe['outputs']):
            if any(k not in RESOURCES or type(v) not in (int,float) or v <= 0 for k,v in items.items()):
                raise ValueError('Invalid recipe transaction')
    return True


validate_registry()
