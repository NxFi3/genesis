extends Node2D
## Procedural colony artwork. All visible states come from authoritative snapshots.
const TerrainView = preload("res://terrain_view.gd")
const TILE := TerrainView.TILE
const HOME_COLORS := {"a": Color("85ceb0"), "b": Color("9abfe1")}
const INK := Color("26382e")
const CREAM := Color("eee4c8")
var state: Dictionary = {}
var selected := "a0"
var camera_offset := Vector2.ZERO
var zoom := 1.0
var smooth_positions: Dictionary = {}
var follow_agent := false
var view_size := Vector2(864, 516)
var terrain_layer: Node2D
var clock := 0.0
var effects: Array[Dictionary] = []
var last_event := -1
var last_tick := -1
var labels_visible := true
var details_visible := true
var conversation_agents: Dictionary = {}
var cargo_agents: Dictionary = {}

func _ready() -> void:
    terrain_layer = TerrainView.new()
    terrain_layer.show_behind_parent = true
    add_child(terrain_layer)

func accept_state(value: Dictionary) -> void:
    var first := state.is_empty()
    state = value
    terrain_layer.update_world(value)
    if first: reset_camera()
    conversation_agents.clear()
    cargo_agents.clear()
    for c in state.get("conversations", {}).values():
        if c.state == "active":
            for id in c.participants: conversation_agents[id] = c
    for cargo in state.get("shipments", {}).values():
        if cargo.get("state", "") in ["in_transit", "returning"]:
            cargo_agents[cargo.get("courier", "")] = true
    var previous_event := last_event
    var fresh := not first and int(state.tick) >= last_tick
    for event in state.get("events", []):
        if fresh and int(event.id) > previous_event and event.kind in ["built", "agreement_fulfilled", "conflict_start", "conflict_end", "settlement_trade", "council_decision"]:
            if not event.actors.is_empty() and state.agents.has(event.actors[0]):
                effects.append({"position": world_point(state.agents[event.actors[0]]), "text": {"built": "Built", "agreement_fulfilled": "Exchanged", "conflict_start": "Dispute", "conflict_end": "Resolved", "settlement_trade": "Trade", "council_decision": "Council"}[event.kind], "until": clock+3.0})
        last_event = int(event.id)
    if not fresh: effects.clear()
    if effects.size() > 6: effects = effects.slice(-6)
    last_tick = int(state.tick)

func _process(delta: float) -> void:
    clock += delta
    for category in ["agents", "wildlife"]:
        for a in state.get(category, {}).values():
            var target := Vector2(a.x, a.y)
            var shown: Vector2 = smooth_positions.get(a.id, target)
            smooth_positions[a.id] = target if shown.distance_to(target) > 4 else shown.lerp(target, 1-exp(-delta*10))
    for id in smooth_positions.keys():
        if not state.get("agents", {}).has(id) and not state.get("wildlife", {}).has(id): smooth_positions.erase(id)
    if follow_agent:
        var target := selected_entity()
        if not target.is_empty():
            camera_offset = camera_offset.lerp(view_size*.5-world_point(target)*zoom, 1-exp(-delta*6))
    if terrain_layer:
        terrain_layer.position = camera_offset
        terrain_layer.scale = Vector2.ONE*zoom
    effects = effects.filter(func(e): return float(e.until) > clock)
    queue_redraw()

func selected_entity() -> Dictionary:
    for category in ["agents", "settlements", "buildings", "resources", "wildlife"]:
        if state.get(category, {}).has(selected): return state[category][selected]
    return {}

func world_point(entity: Dictionary) -> Vector2:
    var coordinates: Vector2 = smooth_positions.get(entity.id, Vector2(entity.x, entity.y))
    return (coordinates + Vector2(.5, .5)) * TILE

func screen_point(entity: Dictionary) -> Vector2:
    return camera_offset + world_point(entity) * zoom

func zoom_at(factor: float, local_position: Vector2) -> void:
    var before := (local_position-camera_offset)/zoom
    zoom = clampf(zoom*factor, .35, 4.0)
    camera_offset = local_position-before*zoom
    follow_agent = false

func reset_camera() -> void:
    var dimensions := Vector2(state.get("width", 48), state.get("height", 30))*TILE
    zoom = minf(view_size.x/dimensions.x, view_size.y/dimensions.y)
    camera_offset = (view_size-dimensions*zoom)*.5
    follow_agent = false

func focus_selected() -> void:
    var entity := selected_entity()
    if not entity.is_empty():
        zoom = maxf(zoom, 1.3)
        camera_offset = view_size*.5-world_point(entity)*zoom

func _draw() -> void:
    if state.is_empty(): return
    draw_set_transform(camera_offset, 0, Vector2.ONE*zoom)
    for s in state.settlements.values():
        var color: Color = HOME_COLORS.get(s.id, CREAM)
        draw_arc(world_point(s), TILE*3.8, 0, TAU, 64, Color(color, .22), 2, true)
    for resource in state.resources.values():
        if resource.quantity <= 0 or resource.kind == "water": continue
        var p := world_point(resource)
        match resource.kind:
            "food":
                draw_circle(p, 4, Color("587243"))
                for offset in [Vector2(-2,-2), Vector2(2,0), Vector2(0,2)]:
                    draw_circle(p+offset, 1.5, Color("d7aa6c"))
            "wood":
                draw_line(p+Vector2(-4,3), p+Vector2(4,0), Color("65503b"), 5, true)
                draw_circle(p+Vector2(4,0), 2, Color("c5ad7c"))
            _:
                draw_colored_polygon(PackedVector2Array([p+Vector2(-5,3),p+Vector2(-3,-3),p+Vector2(3,-4),p+Vector2(6,2)]), Color("b6c1bb") if resource.kind == "stone" else Color("c98d64"))
    var buildings: Array = state.buildings.values()
    buildings.sort_custom(func(a,b): return a.y < b.y)
    for building in buildings: draw_building(building)
    for animal in state.wildlife.values(): draw_animal(animal)
    for c in state.conflicts.values():
        if c.state == "active" and state.agents.has(c.a) and state.agents.has(c.b):
            var p: Vector2 = world_point(state.agents[c.a])
            var q: Vector2 = world_point(state.agents[c.b])
            draw_dashed_line(p,q,Color("f1bb76"),2,5)
    var people: Array = state.agents.values()
    people.sort_custom(func(a,b): return a.y < b.y)
    for a in people: draw_person(a)
    draw_set_transform(Vector2.ZERO)
    # Screen-space labels remain legible at every zoom level.
    if labels_visible:
        for s in state.settlements.values():
            var color: Color = HOME_COLORS.get(s.id, CREAM)
            tag(screen_point(s)+Vector2(0,-TILE*3.5*zoom), s.name, color, 14)
        if zoom > 1.7:
            for b in buildings:
                if b.id == selected: continue
                tag(screen_point(b)+Vector2(0,16*zoom), str(b.kind).capitalize(), CREAM, 11)
    var chosen := selected_entity()
    if not chosen.is_empty():
        var caption := str(chosen.get("name", chosen.get("kind", chosen.get("species", selected))))
        if chosen.has("activity"): caption += "  ·  " + str(chosen.activity).capitalize()
        if follow_agent: caption += "  / Following"
        tag(screen_point(chosen)+Vector2(0,24*zoom), caption, Color("f8df9e"), 13)
    for e in effects:
        tag(camera_offset+e.position*zoom+Vector2(0,-24-(3-(e.until-clock))*10), e.text, Color("f5d7a1"), 12)

func tag(center: Vector2, text: String, color: Color, font_size: int) -> void:
    if center.x < -20 or center.y < -20 or center.x > view_size.x+20 or center.y > view_size.y+20: return
    var font := ThemeDB.fallback_font
    var measure := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
    var position := Vector2(clampf(center.x-measure.x*.5,4,maxf(4,view_size.x-measure.x-4)), clampf(center.y,16,view_size.y-6))
    draw_style_box(_label_box(), Rect2(position+Vector2(-5,-font_size), measure+Vector2(10,4)))
    draw_string(font,position,text,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size,color)

func _label_box() -> StyleBoxFlat:
    var style := StyleBoxFlat.new()
    style.bg_color = Color(.08,.13,.11,.9)
    style.set_corner_radius_all(4)
    return style

func draw_building(b: Dictionary) -> void:
    var p := world_point(b)
    var color: Color = HOME_COLORS.get(b.home, CREAM)
    if b.id == selected: draw_arc(p,17,0,TAU,32,Color("f8df9e"),2,true)
    if not b.complete:
        draw_rect(Rect2(p-Vector2(10,9),Vector2(20,18)), Color("6b6549"))
        draw_rect(Rect2(p-Vector2(9,8),Vector2(18,16)), Color("c3aa76"), false, 1.5)
        for x in [-9,9]: draw_line(p+Vector2(x,7),p+Vector2(x,-12),CREAM,2)
        draw_line(p+Vector2(-10,-7),p+Vector2(10,-7),CREAM,2)
        draw_line(p+Vector2(-8,6),p+Vector2(8,-7),Color("9d8258"),2)
        draw_rect(Rect2(p+Vector2(-10,11),Vector2(20,3)),INK)
        # Backend progress is measured in work units, not percent.
        var duration := {"house":12,"farm":10,"storage":15,"workshop":18,"market":12,"watchtower":20,"road":4,"bridge":18,"hall":20,"well":15}
        draw_rect(Rect2(p+Vector2(-10,11),Vector2(20*clampf(float(b.progress)/duration.get(b.kind,20),0,1),3)),Color("edc777"))
        return
    draw_circle(p+Vector2(2,5),12,Color(0.10,.15,.11,.18))
    match b.kind:
        "farm":
            draw_rect(Rect2(p-Vector2(11,10),Vector2(22,20)),Color("766344"))
            for i in range(4):
                draw_line(p+Vector2(-8,-7+i*5),p+Vector2(8,-7+i*5),Color("d8c774"),2)
                for x in [-6,0,6]: draw_line(p+Vector2(x,-6+i*5),p+Vector2(x-1,-10+i*5),Color("9bad60"),1)
            draw_line(p+Vector2(10,4),p+Vector2(10,-9),CREAM,1.5)
        "well":
            draw_circle(p,9,Color("b5b9ab"))
            draw_circle(p,5,Color("417f96"))
            for x in [-8,8]: draw_line(p+Vector2(x,4),p+Vector2(x,-12),Color("594f3a"),2)
            roof(p+Vector2(0,-7),10,Color("be9b65"))
        "road": pass
        "bridge":
            for y in [-8,8]: draw_line(p+Vector2(-12,y),p+Vector2(12,y),Color("e1c59a"),2)
        "market":
            draw_rect(Rect2(p+Vector2(-11,1),Vector2(22,8)),Color("9d7f53"))
            for x in [-9,9]: draw_line(p+Vector2(x,7),p+Vector2(x,-10),INK,2)
            for i in range(5): draw_rect(Rect2(p+Vector2(-12+i*5,-10),Vector2(5,11)),color if i%2 == 0 else CREAM)
            for i in range(3): draw_circle(p+Vector2(-6+i*6,3),2,Color("dec26d"))
        "watchtower":
            draw_rect(Rect2(p+Vector2(-7,-12),Vector2(14,23)),Color("b6b6a2"))
            draw_rect(Rect2(p+Vector2(-10,-16),Vector2(20,8)),Color("d4d1b8"))
            for i in range(3): draw_rect(Rect2(p+Vector2(-10+i*8,-19),Vector2(4,5)),Color("d4d1b8"))
            draw_rect(Rect2(p+Vector2(-2,-5),Vector2(4,7)),INK)
            draw_line(p+Vector2(7,-19),p+Vector2(7,-28),INK,1.5)
            draw_colored_polygon(PackedVector2Array([p+Vector2(7,-28),p+Vector2(16,-25),p+Vector2(7,-23)]),color)
        _:
            var wide := 13.0 if b.kind == "hall" else 10.0
            draw_rect(Rect2(p+Vector2(-wide,-7),Vector2(wide*2,17)),Color("d3c5a0"))
            draw_rect(Rect2(p+Vector2(-3,2),Vector2(6,8)),Color("675640"))
            var roof_color := {"house":Color("ac7255"),"hall":Color("6f8490"),"storage":Color("a18b60"),"workshop":Color("647a70")}
            roof(p+Vector2(0,-5),wide+2,roof_color.get(b.kind,Color("ac7255")))
            draw_rect(Rect2(p+Vector2(-8,-1),Vector2(4,4)),Color("f4d995"))
            if b.kind == "storage":
                for x in [6,11]:
                    draw_rect(Rect2(p+Vector2(x,3),Vector2(5,6)),Color("c29c65"))
                    draw_rect(Rect2(p+Vector2(x,3),Vector2(5,6)),INK,false,1)
            elif b.kind == "workshop":
                draw_rect(Rect2(p+Vector2(5,-18),Vector2(5,10)),Color("a5a89b"))
                draw_line(p+Vector2(5,7),p+Vector2(11,1),INK,2)
                draw_line(p+Vector2(7,0),p+Vector2(12,4),INK,3)
            elif b.kind == "hall":
                draw_rect(Rect2(p+Vector2(7,-4),Vector2(3,10)),color)
    if b.get("condition",100) < 50:
        draw_circle(p+Vector2(11,-13),3,Color("e3aa71"))

func roof(p: Vector2, width: float, color: Color) -> void:
    draw_colored_polygon(PackedVector2Array([p+Vector2(-width,2),p+Vector2(0,-10),p+Vector2(width,2)]),INK)
    draw_colored_polygon(PackedVector2Array([p+Vector2(-width+1,0),p+Vector2(0,-9),p+Vector2(width-1,0)]),color)
    draw_line(p+Vector2(0,-9),p+Vector2(width-1,0),color.lightened(.2),1)

func draw_person(a: Dictionary) -> void:
    var p := world_point(a)
    var color: Color = HOME_COLORS.get(a.home, CREAM)
    if a.player: color = Color("f2cf80")
    oval(p+Vector2(1,6),Vector2(7,3),Color(.08,.16,.10,.35))
    if a.id == selected:
        draw_arc(p+Vector2(0,3),11,0,TAU,32,Color("fff1c1"),1.7,true)
        if follow_agent: draw_arc(p+Vector2(0,3),14,0,PI,20,Color("e6c17b"),1,true)
    if a.incapacitated:
        draw_line(p+Vector2(-6,2),p+Vector2(3,2),color.lerp(Color("92958e"),.65),6,true)
        draw_circle(p+Vector2(6,1),3,Color("d4b99b"))
        draw_line(p+Vector2(-1,-7),p+Vector2(5,-7),CREAM,2)
        draw_line(p+Vector2(2,-10),p+Vector2(2,-4),CREAM,2)
    else:
        draw_line(p+Vector2(-3,3),p+Vector2(-3,8),INK,2)
        draw_line(p+Vector2(3,3),p+Vector2(3,8),INK,2)
        draw_colored_polygon(PackedVector2Array([p+Vector2(-3,-4),p+Vector2(3,-4),p+Vector2(6,5),p+Vector2(-6,5)]),INK)
        draw_colored_polygon(PackedVector2Array([p+Vector2(-2,-4),p+Vector2(2,-4),p+Vector2(4,4),p+Vector2(-4,4)]),color)
        draw_circle(p+Vector2(0,-7),3.8,Color("dab895"))
        draw_arc(p+Vector2(0,-7),3.7,PI,TAU,8,Color("594b39"),2,true)
        if a.occupation == "guard":
            draw_line(p+Vector2(8,6),p+Vector2(8,-11),Color("d9d5bd"),1.5)
            draw_colored_polygon(PackedVector2Array([p+Vector2(-8,-2),p+Vector2(-3,-2),p+Vector2(-4,4),p+Vector2(-6,6),p+Vector2(-8,4)]),Color("ccd4cd"))
        if a.player:
            draw_colored_polygon(PackedVector2Array([p+Vector2(-3,-18),p+Vector2(3,-18),p+Vector2(0,-14)]),Color("ffe4a3"))
    if a.hp < a.max_hp or a.id == selected:
        draw_rect(Rect2(p+Vector2(-7,-14),Vector2(14,2)),INK)
        draw_rect(Rect2(p+Vector2(-7,-14),Vector2(14*clampf(float(a.hp)/maxf(1,a.max_hp),0,1),2)),Color("a8d49b") if a.hp > a.max_hp*.4 else Color("e6ae74"))
    if not details_visible: return
    if conversation_agents.has(a.id):
        var bubble := p+Vector2(11,-18)
        draw_style_box(_label_box(),Rect2(bubble-Vector2(6,4),Vector2(14,9)))
        for i in range(3): draw_circle(bubble+Vector2(-2+i*3,0),.8,CREAM)
        draw_line(bubble+Vector2(-5,4),bubble+Vector2(-7,7),CREAM,1)
    elif a.activity in ["build", "work", "repair"]:
        draw_line(p+Vector2(9,-3),p+Vector2(14,-11),Color("e5c891"),2)
        draw_line(p+Vector2(11,-12),p+Vector2(17,-8),Color("d6dcce"),3)
    elif a.activity in ["sleep", "rest"]:
        draw_string(ThemeDB.fallback_font,p+Vector2(8,-10),"z",HORIZONTAL_ALIGNMENT_LEFT,-1,10,CREAM)
    if cargo_agents.has(a.id) or (a.activity in ["move", "gather", "trade"] and float(a.inventory.get("wood",0))+float(a.inventory.get("stone",0))+float(a.inventory.get("metal",0)) >= 3):
        draw_rect(Rect2(p+Vector2(-10,0),Vector2(6,6)),Color("c49e64"))
        draw_rect(Rect2(p+Vector2(-10,0),Vector2(6,6)),INK,false,1)

func oval(p: Vector2, radius: Vector2, color: Color) -> void:
    var points := PackedVector2Array()
    for i in range(16): points.append(p+Vector2(cos(i*TAU/16)*radius.x,sin(i*TAU/16)*radius.y))
    draw_colored_polygon(points,color)

func draw_animal(a: Dictionary) -> void:
    var p := world_point(a)
    var deer: bool = a.get("species","deer") == "deer"
    var fur := Color("b79970") if deer else Color("929b96")
    oval(p+Vector2(1,5),Vector2(8,3),Color(.1,.15,.1,.2))
    for x in [-4,3]: draw_line(p+Vector2(x,0),p+Vector2(x+1,7),INK,1.5)
    oval(p,Vector2(7,4),fur)
    draw_line(p+Vector2(4,0),p+Vector2(7,-5),fur,4,true)
    draw_circle(p+Vector2(7,-6),3,fur.lightened(.12))
    draw_line(p+Vector2(-6,-1),p+Vector2(-10,-4),fur,2)
    if deer:
        for x in [5,8]:
            draw_line(p+Vector2(x,-8),p+Vector2(x-1,-13),Color("d9cfaa"),1)
            draw_line(p+Vector2(x,-10),p+Vector2(x+3,-12),Color("d9cfaa"),1)
    else:
        draw_colored_polygon(PackedVector2Array([p+Vector2(5,-7),p+Vector2(5,-12),p+Vector2(8,-7)]),fur)
    if a.id == selected: draw_arc(p,12,0,TAU,24,CREAM,1.5,true)
