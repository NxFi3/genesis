extends Node2D

const TILE := 18.0
const TERRAIN := {
    "forest": Color("284d3d"), "plains": Color("597750"),
    "mountain": Color("707b7e"), "river": Color("326d8a"),
    "lake": Color("326d8a"), "farmland": Color("879158"),
    "road": Color("a4936a"), "bridge": Color("b4a27f")
}
var state: Dictionary = {}
var selected := "a0"
var camera_offset := Vector2.ZERO
var zoom := 1.0
var smooth_positions: Dictionary = {}
var follow_agent := false
var view_size := Vector2(864, 540)

func _process(delta: float) -> void:
    for a in state.get("agents", {}).values():
        var target := Vector2(a.x, a.y)
        var shown: Vector2 = smooth_positions.get(a.id, target)
        smooth_positions[a.id] = target if shown.distance_to(target) > 4 else shown.lerp(target, minf(1.0, delta * 10))
    for id in smooth_positions.keys():
        if not state.get("agents", {}).has(id):
            smooth_positions.erase(id)
    if follow_agent and state.get("agents", {}).has(selected):
        camera_offset = view_size * .5 - world_point(state.agents[selected]) * zoom
    queue_redraw()

func world_point(entity: Dictionary) -> Vector2:
    var coordinates := Vector2(entity.x, entity.y)
    if state.get("agents", {}).has(entity.id):
        coordinates = smooth_positions.get(entity.id, coordinates)
    return (coordinates + Vector2(.5, .5)) * TILE

func screen_point(entity: Dictionary) -> Vector2:
    return camera_offset + world_point(entity) * zoom

func zoom_at(factor: float, local_position: Vector2) -> void:
    var before := (local_position - camera_offset) / zoom
    zoom = clampf(zoom * factor, .5, 3.5)
    camera_offset = local_position - before * zoom
    follow_agent = false

func reset_camera() -> void:
    camera_offset = Vector2.ZERO
    zoom = 1.0
    follow_agent = false

func _draw() -> void:
    if state.is_empty():
        return
    draw_set_transform(camera_offset, 0, Vector2.ONE * zoom)
    for y in range(state.height):
        for x in range(state.width):
            var rect := Rect2(Vector2(x, y) * TILE, Vector2(TILE - .4, TILE - .4))
            var terrain: String = state.terrain[y][x]
            draw_rect(rect, TERRAIN.get(terrain, Color("597750")))
            var center := rect.get_center()
            if terrain == "forest":
                draw_colored_polygon(PackedVector2Array([center+Vector2(0,-6), center+Vector2(5,4), center+Vector2(-5,4)]), Color("173c30"))
            elif terrain == "mountain":
                draw_polyline(PackedVector2Array([center+Vector2(-6,4), center+Vector2(0,-6), center+Vector2(6,4)]), Color("b5bfba"), 1)
    for s in state.settlements.values():
        draw_arc(world_point(s), 55, 0, TAU, 48, Color("d7c28c") if s.conflict == "peace" else Color("f5ac62"), 1.5)
        draw_string(ThemeDB.fallback_font, world_point(s)+Vector2(-45,-62), s.name+" / "+s.conflict, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("fff1ca"))
    for r in state.resources.values():
        if r.quantity > 0:
            draw_circle(world_point(r), 4, Color("e6cf74") if r.kind != "water" else Color("a6dded"))
    for b in state.buildings.values():
        var rect := Rect2(world_point(b)-Vector2(7,7), Vector2(14,14))
        draw_rect(rect, Color("dccaaa") if b.complete else Color("8c7856"), b.complete)
        draw_line(rect.position, rect.position+Vector2(7,-5), Color("463c34"), 2)
        draw_line(rect.position+Vector2(7,-5), rect.position+Vector2(14,0), Color("463c34"), 2)
        if zoom >= 1.5:
            draw_string(ThemeDB.fallback_font, world_point(b)+Vector2(9,0), b.kind, HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color("f6e5c6"))
    for animal in state.wildlife.values():
        draw_circle(world_point(animal), 3.5, Color("bca38d"))
    for c in state.conflicts.values():
        if c.state == "active" and state.agents.has(c.a) and state.agents.has(c.b):
            var a: Dictionary = state.agents[c.a]
            var b: Dictionary = state.agents[c.b]
            draw_line(world_point(a), world_point(b), Color("ffd580"), 2)
            draw_string(ThemeDB.fallback_font, (world_point(a)+world_point(b))/2+Vector2(0,-13), "DISPUTE", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color("ffe7ac"))
    for a in state.agents.values():
        var pos := world_point(a)
        var color := Color("b8e2bb") if a.home == "a" else Color("a9c9ed")
        if a.player:
            color = Color("ffe3a0")
        if a.incapacitated:
            color = Color("a6a4b2")
        draw_circle(pos, 4.5, color)
        if a.occupation == "guard":
            draw_arc(pos, 6, 0, TAU, 12, Color("d9e1e4"), 1)
        if a.hp < a.max_hp:
            draw_rect(Rect2(pos+Vector2(-6,-10), Vector2(12,2)), Color("303336"))
            draw_rect(Rect2(pos+Vector2(-6,-10), Vector2(12*a.hp/a.max_hp,2)), Color("e8ba7c"))
        if a.id == selected:
            draw_arc(pos, 9, 0, TAU, 24, Color.WHITE, 1.5)
        if a.id == selected or zoom >= 2:
            draw_string(ThemeDB.fallback_font, pos+Vector2(10,-8), a.name+": "+a.activity, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color.WHITE)
    draw_set_transform(Vector2.ZERO)
