"""Free-form, resource-backed modular architecture in a 2-D authoritative world.

The renderer displays a 3-D stack, but vertical navigation and real voxel
physics are deliberately *not* implied.  No 'build castle' decision tree exists:
the model chooses its own layouts from neutral building parts.
"""
import math
import re

# Every part spends actual inventory/settlement materials. No free spawn path.
PARTS = {
    'stone': {'stone': 1},
    'wood': {'wood': 1},
    'bricks': {'bricks': 1},
    'planks': {'planks': 1},
    'door': {'wood': 1, 'planks': 1},
    'stairs': {'stone': 1},
}
SOLID = {'stone', 'wood', 'bricks'}
HEIGHT = 5
MAX_CELLS = 96
MAX_BLOCKS = 4096
MAX_PROJECTS = 256
_LAYOUT = re.compile(r'(-?\d+),(-?\d+),(\d+),([a-z_]+)')


def initialize(world):
    if not hasattr(world, 'blocks'):
        world.blocks = {}
    if not hasattr(world, 'architecture_projects'):
        world.architecture_projects = {}
    if not hasattr(world, 'next_structure'):
        world.next_structure = 1


def key(x, y, z):
    return f'{int(x)}:{int(y)}:{int(z)}'


def cost(kind):
    return PARTS[kind]


def traversable(world, x, y):
    block = world.blocks.get(key(x, y, 0))
    return not block or block['kind'] not in SOLID and (block['kind'] != 'door' or block.get('open', True))


def _occupant(world, x, y):
    from .predators import occupied
    return occupied(world, x, y)


def _ground_allowed(world, x, y):
    if not (0 <= x < world.width and 0 <= y < world.height):
        return False
    from .world import PASSABLE
    return world.terrain[y][x] in PASSABLE and not any(
        round(b.x) == x and round(b.y) == y for b in world.buildings.values()
    )


def _supported(blocks, x, y, z):
    if z == 0:
        return True
    if key(x, y, z - 1) in blocks:
        return True
    return any(key(x + dx, y + dy, z) in blocks for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def _parse(world, actor, base_x, base_y, layout):
    if any(type(n) is not int for n in (base_x, base_y)) or not isinstance(layout, str):
        raise ValueError('The blueprint anchor must be integer coordinates and its layout must be text')
    if len(layout) > 2048:
        raise ValueError('Blueprint layout must be at most 2048 characters')
    if math.hypot(base_x - actor.x, base_y - actor.y) > 12:
        raise ValueError('Blueprint anchor must be within 12 tiles of its author')
    raw = layout.split(';')
    if not 1 <= len(raw) <= MAX_CELLS or any(not cell.strip() for cell in raw):
        raise ValueError('Blueprint must contain 1..96 nonempty parts')
    result = []
    indices = set()
    occupied = set(world.blocks)
    for item in raw:
        match = _LAYOUT.fullmatch(item.strip())
        if not match:
            raise ValueError('Use dx,dy,z,material;dx,dy,z,material (integer offsets)')
        dx, dy, z = (int(v) for v in match.group(1, 2, 3))
        kind = match.group(4)
        x, y = base_x + dx, base_y + dy
        address = key(x, y, z)
        if kind not in PARTS or not 0 <= z <= HEIGHT or abs(dx) > 15 or abs(dy) > 15:
            raise ValueError('Unsupported part, height, or layout extent')
        if not _ground_allowed(world, x, y):
            raise ValueError('A part is outside buildable terrain or overlaps an existing facility')
        if address in indices or address in occupied or any(
            key(x, y, z) in (key(p['x'], p['y'], p['z']) for p in job['parts'])
            for job in world.architecture_projects.values()
            if job['state'] == 'active'
        ):
            raise ValueError('Duplicate or occupied blueprint position')
        if z == 0 and _occupant(world, x, y):
            raise ValueError('A ground-level part would enclose an existing occupant')
        indices.add(address)
        result.append({'x': x, 'y': y, 'z': z, 'kind': kind})
    # There must be a support path to the ground; reject floating designs.
    available = dict(world.blocks)
    pending = list(result)
    while pending:
        released = [p for p in pending if _supported(available, p['x'], p['y'], p['z'])]
        if not released:
            raise ValueError('The design contains unsupported floating parts')
        for p in released:
            available[key(p['x'], p['y'], p['z'])] = {'kind': p['kind']}
            pending.remove(p)
    return sorted(result, key=lambda p: (p['z'], p['y'], p['x']))


def propose(world, actor, command):
    try:
        title, purpose = command.get('title', ''), command.get('purpose', '')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 60:
            raise ValueError('Give the design a title of 1..60 characters')
        if not isinstance(purpose, str) or len(purpose) > 240:
            raise ValueError('Purpose must be a short text field')
        if len(world.architecture_projects) >= MAX_PROJECTS:
            # Keep bounded state; retire only old cancelled/completed designs.
            archive = sorted((p for p in world.architecture_projects.values() if p['state'] != 'active'), key=lambda p: p['created'])
            if not archive:
                raise ValueError('The project limit was reached')
            del world.architecture_projects[archive[0]['id']]
        x, y = command.get('x'), command.get('y')
        parts = _parse(world, actor, x, y, command.get('layout'))
        if len(world.blocks) + sum(len(p['parts'])-p['progress'] for p in world.architecture_projects.values() if p['state']=='active') + len(parts) > MAX_BLOCKS:
            raise ValueError('World block capacity reached')
        project_id = f'structure_{world.next_structure}'
        world.next_structure += 1
        world.architecture_projects[project_id] = {
            'id': project_id, 'title': title.strip(), 'purpose': purpose,
            'home': actor.home, 'author': actor.id, 'created': world.tick,
            'state': 'active', 'parts': parts, 'progress': 0,
            'workers': [], 'last_work': world.tick,
        }
        world.event('structure_designed', f'{actor.name} proposed {title.strip()} ({len(parts)} parts).', [actor.id], project=project_id)
        return {'ok': True, 'message': f'Design registered: {project_id}', 'project': project_id}
    except (ValueError, TypeError, OverflowError) as error:
        return {'ok': False, 'message': str(error)}


def _unbuilt(world, project):
    return [part for part in project['parts'] if key(part['x'], part['y'], part['z']) not in world.blocks]


def _next_part(world, actor, project):
    available = [p for p in _unbuilt(world, project) if _supported(world.blocks, p['x'], p['y'], p['z'])]
    if not available:
        return None
    return min(available, key=lambda p: (
        math.hypot(actor.x - p['x'], actor.y - p['y']),
        p['z'], p['y'], p['x']
    ))


def _supplies(world, actor, required):
    missing = {name: amount - actor.inventory.get(name, 0)
               for name, amount in required.items() if actor.inventory.get(name, 0) < amount}
    if not missing:
        return 'ready'
    settlement = world.settlements[actor.home]
    if not (world.governance[actor.home].get('sharing', True) or actor.id in settlement.council):
        return 'unavailable'
    if not all(settlement.inventory.get(name, 0) >= amount for name, amount in missing.items()):
        return 'unavailable'
    from .combat import distance
    if distance(actor, settlement) > 2:
        return 'moving' if world.move(actor, settlement.x, settlement.y) else 'unavailable'
    from .registry import mass
    if mass(actor.inventory) + mass(missing) > actor.carry_capacity:
        return 'unavailable'
    for name, amount in missing.items():
        if not world.transfer(settlement.inventory, actor.inventory, name, amount):
            return 'unavailable'
    return 'ready'


def _place(world, actor, part, project=None):
    from .combat import distance
    x, y, z, kind = (part[k] for k in ('x', 'y', 'z', 'kind'))
    address = key(x, y, z)
    if address in world.blocks or not _ground_allowed(world, x, y):
        return {'ok': False, 'message': 'Location is occupied or inaccessible'}
    if not _supported(world.blocks, x, y, z):
        return {'ok': False, 'message': 'This part still needs supporting blocks'}
    if z == 0 and _occupant(world, x, y):
        return {'ok': False, 'message': 'Move inhabitants away before placing a ground barrier'}
    if distance(actor, type('Point', (), {'x': x, 'y': y})()) > 2.5 or actor.stamina < 3:
        return {'ok': False, 'message': 'Move within 2.5 tiles and recover stamina'}
    required = cost(kind)
    if any(actor.inventory.get(item, 0) < amount for item, amount in required.items()):
        return {'ok': False, 'message': 'Not enough owned materials'}
    for item, amount in required.items():
        actor.inventory[item] -= amount
    actor.stamina -= 3
    actor.activity = 'build'
    world.blocks[address] = {
        'x': x, 'y': y, 'z': z, 'kind': kind,
        'home': actor.home, 'creator': actor.id, 'project': project,
        'open': True if kind == 'door' else False,
    }
    if z == 0:
        world._paths.clear()
        world._blocked_tick = -1
    world.event('block_placed', f'{actor.name} placed a {kind} building part.', [actor.id],
                project=project, x=x, y=y, z=z)
    return {'ok': True, 'message': 'Placed one physical, paid-for part'}


def work(world, actor, command):
    project_id = command.get('project')
    candidate = world.architecture_projects.get(project_id) if project_id else None
    if candidate is None and not project_id:
        candidate = next((p for p in sorted(world.architecture_projects.values(), key=lambda p: p['created'])
                          if p['state'] == 'active' and p['home'] == actor.home), None)
    if not candidate or candidate['state'] != 'active' or candidate['home'] != actor.home:
        return {'ok': False, 'message': 'No accessible active design'}
    part = _next_part(world, actor, candidate)
    if part is None:
        if len(_unbuilt(world, candidate)) == 0:
            candidate['state'] = 'completed'
            return {'ok': True, 'message': 'Design completed'}
        return {'ok': False, 'message': 'Remaining parts need physical support'}
    from .combat import distance
    # Acquire materials before walking to site; otherwise workers can oscillate
    # between the site and their store without ever loading supplies.
    state = _supplies(world, actor, cost(part['kind']))
    if state == 'moving':
        return {'ok': True, 'pending': True, 'message': 'Collecting existing communal materials'}
    if state != 'ready':
        return {'ok': False, 'message': 'Need available owned or shared building materials'}
    position = type('Point', (), {'x': part['x'], 'y': part['y']})()
    if distance(actor, position) > 2.5:
        if not world.move(actor, part['x'], part['y']):
            return {'ok': False, 'message': 'Cannot reach the next part of this design'}
        return {'ok': True, 'pending': True, 'message': 'Walking to the construction site'}
    if actor.stamina < 3:
        return {'ok': True, 'pending': True, 'message': 'Recovering before the next placement'}
    result = _place(world, actor, part, candidate['id'])
    if result['ok']:
        candidate['progress'] += 1
        candidate['last_work'] = world.tick
        if actor.id not in candidate['workers']:
            candidate['workers'].append(actor.id)
        if candidate['progress'] == len(candidate['parts']):
            candidate['state'] = 'completed'
            world.stats['built'] += 1
            world.event('structure_completed', f'{candidate["title"]} was completed.', candidate['workers'],
                        project=candidate['id'])
        else:
            result['pending'] = True
            result['message'] = f'Completed {candidate["progress"]}/{len(candidate["parts"])} parts'
    return result


def direct(world, actor, command):
    if len(world.blocks) >= MAX_BLOCKS:
        return {'ok': False, 'message': 'World block capacity reached'}
    part = {k: command.get(k) for k in ('x', 'y', 'z', 'kind')}
    if any(type(part[k]) is not int for k in ('x', 'y', 'z')) or part['kind'] not in PARTS:
        return {'ok': False, 'message': 'Use integer x,y,z and a supported material'}
    if not 0 <= part['z'] <= HEIGHT:
        return {'ok': False, 'message': 'Height outside supported 0..5 levels'}
    if not (0 <= part['x'] < world.width and 0 <= part['y'] < world.height):
        return {'ok': False, 'message': 'Outside world bounds'}
    if any(key(part['x'], part['y'], part['z']) in {key(p['x'], p['y'], p['z']) for p in project['parts']}
           for project in world.architecture_projects.values() if project['state']=='active'):
        return {'ok': False, 'message': 'Tile reserved by an active design'}
    return _place(world, actor, part)


def remove(world, actor, command):
    x, y, z = (command.get(k) for k in ('x', 'y', 'z'))
    if any(type(n) is not int for n in (x, y, z)):
        return {'ok': False, 'message': 'Use integer block coordinates'}
    address = key(x, y, z)
    block = world.blocks.get(address)
    from .combat import distance
    if not block or block['home'] != actor.home or distance(actor, type('Point', (), {'x': x, 'y': y})()) > 2.5:
        return {'ok': False, 'message': 'No accessible home block at this location'}
    if actor.stamina < 3:
        return {'ok': False, 'message': 'Need stamina'}
    if any(key(x, y, upper) in world.blocks for upper in range(z+1, HEIGHT+1)):
        return {'ok': False, 'message': 'Remove overhead layers first'}
    if z == 0 and _occupant(world, x, y):
        return {'ok': False, 'message': 'Tile contains an inhabitant'}
    del world.blocks[address]
    if block.get('project') in world.architecture_projects:
        project = world.architecture_projects[block['project']]
        project['progress'] = max(0, project['progress'] - 1)
        # A deliberate demolition does not silently requeue construction.
        project['state'] = 'cancelled'
    actor.stamina -= 3
    # Dismantling yields no refund: never conjure supplies from project edits.
    world._paths.clear()
    world._blocked_tick = -1
    world.event('block_removed', f'{actor.name} dismantled a structure part.', [actor.id], x=x, y=y, z=z)
    return {'ok': True, 'message': 'Part dismantled; materials were not refunded'}


def toggle(world, actor, command):
    x, y, z = (command.get(k) for k in ('x', 'y', 'z'))
    opened = command.get('open')
    if any(type(n) is not int for n in (x, y, z)) or type(opened) is not bool:
        return {'ok': False, 'message': 'Use integer coordinates and a boolean open state'}
    block = world.blocks.get(key(x, y, z))
    from .combat import distance
    if not block or block['kind'] != 'door' or block['home'] != actor.home or distance(actor, type('Point', (), {'x': x, 'y': y})()) > 2.5:
        return {'ok': False, 'message': 'No accessible home door'}
    if not opened and z == 0 and _occupant(world, x, y):
        return {'ok': False, 'message': 'Cannot close a door on an occupant'}
    block['open'] = opened
    world._paths.clear()
    world._blocked_tick = -1
    world.event('block_gate_changed', f'{actor.name} changed a modular door.', [actor.id], x=x, y=y, z=z)
    return {'ok': True, 'message': 'Door updated'}


def cancel(world, actor, command):
    project = world.architecture_projects.get(command.get('project'))
    if not project or project['state'] != 'active' or project['home'] != actor.home:
        return {'ok': False, 'message': 'No active home design'}
    if actor.id != project['author'] and actor.id not in world.settlements[actor.home].council:
        return {'ok': False, 'message': 'Only the designer or council may cancel'}
    project['state'] = 'cancelled'
    world.event('structure_cancelled', f'{actor.name} cancelled a blueprint; constructed parts remain.', [actor.id],
                project=project['id'])
    return {'ok': True, 'message': 'Cancelled future work; finished parts retained'}


def autonomous(world, actor):
    if actor.occupation != 'builder':
        return False
    projects = [p for p in world.architecture_projects.values() if p['home'] == actor.home and p['state'] == 'active']
    if not projects:
        return False
    nearest = min(projects, key=lambda p: (
        min(math.hypot(actor.x-b['x'], actor.y-b['y']) for b in p['parts']),
        p['created']
    ))
    outcome = work(world, actor, {'project': nearest['id']})
    return bool(outcome['ok'])


def validate_world(world):
    from .registry import RESOURCES
    if type(world.next_structure) is not int or world.next_structure < 1:
        raise ValueError('Invalid modular structure serial')
    if not isinstance(world.blocks, dict) or len(world.blocks) > MAX_BLOCKS:
        raise ValueError('Invalid modular world blocks')
    for address, block in world.blocks.items():
        if not isinstance(block, dict) or address != key(block.get('x'),block.get('y'),block.get('z')):
            raise ValueError('Invalid block coordinate identity')
        x, y, z = (block[k] for k in ('x', 'y', 'z'))
        if any(type(v) is not int for v in (x, y, z)) or not (0 <= x < world.width and 0 <= y < world.height and 0 <= z <= HEIGHT):
            raise ValueError('Invalid modular block coordinates')
        if block.get('kind') not in PARTS or block.get('home') not in world.settlements or type(block.get('open')) is not bool:
            raise ValueError('Invalid modular block material, home, or door')
        if not _ground_allowed(world,x,y):
            raise ValueError('Invalid modular block site')
    if not isinstance(world.architecture_projects, dict) or len(world.architecture_projects)>MAX_PROJECTS:
        raise ValueError('Invalid architecture project collection')
    for identity, project in world.architecture_projects.items():
        if identity != project.get('id') or project.get('home') not in world.settlements or not isinstance(project.get('author'), str):
            raise ValueError('Invalid architecture project ownership')
        if project.get('state') not in ('active','completed','cancelled') or not isinstance(project.get('title'),str):
            raise ValueError('Invalid architecture project state')
        cells = project.get('parts')
        if not isinstance(cells,list) or not 1<=len(cells)<=MAX_CELLS or len({key(p['x'],p['y'],p['z']) for p in cells})!=len(cells):
            raise ValueError('Invalid blueprint parts')
        if type(project.get('progress')) is not int or not 0<=project['progress']<=len(cells):
            raise ValueError('Invalid blueprint progress')
        for part in cells:
            if any(type(part.get(k)) is not int for k in ('x','y','z')) or part.get('kind') not in PARTS:
                raise ValueError('Invalid blueprint part')
            if not (0<=part['x']<world.width and 0<=part['y']<world.height and 0<=part['z']<=HEIGHT):
                raise ValueError('Invalid blueprint location')
        completed = sum(key(p['x'],p['y'],p['z']) in world.blocks for p in cells)
        if completed != project['progress'] and project['state'] != 'cancelled':
            raise ValueError('Blueprint progress disagrees with built cells')
        if project['state']=='completed' and completed!=len(cells):
            raise ValueError('Incomplete design marked completed')
        if not isinstance(project.get('workers'),list) or any(not isinstance(w,str) for w in project['workers']):
            raise ValueError('Invalid structure workers')
    return world
