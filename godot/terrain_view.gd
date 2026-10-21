extends Node2D
## Retained terrain layer. Redraws only when terrain or season changes, not each frame.
const TILE := 24.0
const COLORS := {
    "plains": Color("849768"), "forest": Color("788c61"),
    "mountain": Color("8a927b"), "river": Color("4a899c"), "lake": Color("427e95"),
    "farmland": Color("a18b58"), "road": Color("b6a27b"), "bridge": Color("508597")
}
var state: Dictionary = {}
var fingerprint := 0
var redraw_count := 0
var bridge_tiles: Dictionary = {}

func update_world(value: Dictionary) -> void:
    bridge_tiles.clear()
    for building in value.get("buildings",{}).values():
        if building.kind == "bridge" and building.complete:
            bridge_tiles[Vector2i(roundi(building.x),roundi(building.y))] = true
    var next := hash([value.get("terrain", []), value.get("season", "spring"), bridge_tiles])
    state = value
    if next != fingerprint:
        fingerprint = next
        queue_redraw()

func variation(x: int, y: int, salt: int = 0) -> float:
    return float(absi(x * 73856093 ^ y * 19349663 ^ salt * 83492791) % 1000) / 1000.0

func tile_at(x: int, y: int) -> String:
    if y < 0 or y >= state.height or x < 0 or x >= state.width: return ""
    return "bridge" if bridge_tiles.has(Vector2i(x,y)) else state.terrain[y][x]

func _draw() -> void:
    if state.is_empty(): return
    redraw_count += 1
    for y in range(state.height):
        for x in range(state.width):
            var kind: String = tile_at(x,y)
            var origin := Vector2(x, y) * TILE
            var center := origin + Vector2.ONE * TILE / 2
            var color: Color = COLORS.get(kind, COLORS.plains)
            var n := variation(x, y)
            color = color.lightened(n * .07).darkened((1 - n) * .05)
            if kind in ["forest", "plains"]:
                if state.season == "autumn": color = color.lerp(Color("bca26c"), .25)
                if state.season == "winter": color = color.lerp(Color("ced6c8"), .45)
            draw_rect(Rect2(origin, Vector2.ONE * TILE), color)
            match kind:
                "river", "lake", "bridge":
                    for i in range(2):
                        var ripple := origin + Vector2(3 + variation(x, y, i + 1) * 8, 6 + i * 10)
                        draw_line(ripple, ripple + Vector2(6 + n * 4, -1), Color("79b1ba"), 1, true)
                    for offset in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
                        if tile_at(x + offset.x, y + offset.y) not in ["river", "lake", "bridge"]:
                            var edge := center + Vector2(offset) * TILE / 2
                            var tangent := Vector2(-offset.y, offset.x) * TILE / 2
                            draw_line(edge - tangent, edge + tangent, Color("c3bc8c"), 2)
                    if kind == "bridge":
                        draw_rect(Rect2(origin + Vector2(1, 5), Vector2(22, 14)), Color("73634b"))
                        for i in range(6):
                            draw_line(origin + Vector2(i*4+2, 6), origin + Vector2(i*4+2, 18), Color("c8ac7a"), 3)
                        draw_line(origin+Vector2(0,4), origin+Vector2(24,4), Color("4d493b"), 2)
                        draw_line(origin+Vector2(0,20), origin+Vector2(24,20), Color("4d493b"), 2)
                "forest":
                    tree(center + Vector2(-4, 2), n, state.season)
                    if n > .45: tree(center + Vector2(6, -4), 1-n, state.season)
                "mountain":
                    var peak := center + Vector2(n*5-2, -9)
                    draw_colored_polygon(PackedVector2Array([center+Vector2(-11,9), peak, center+Vector2(11,9)]), Color("67716d"))
                    draw_colored_polygon(PackedVector2Array([peak, center+Vector2(2,9), center+Vector2(11,9)]), Color("aeb0a0"))
                    draw_colored_polygon(PackedVector2Array([peak, peak+Vector2(-4,6), peak+Vector2(4,6)]), Color("e0dfc9"))
                "farmland":
                    for i in range(4):
                        draw_line(origin+Vector2(3, 4+i*5), origin+Vector2(21, 4+i*5), Color("716244"), 2)
                        draw_line(origin+Vector2(4, 3+i*5), origin+Vector2(19, 3+i*5), Color("c4bc72"), 1)
                "road":
                    for i in range(4):
                        var stone := origin + Vector2(3+variation(x,y,i+1)*16, 3+variation(y,x,i+4)*16)
                        draw_line(stone, stone+Vector2(3,0), Color("d0bd93"), 2)
                    for offset in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
                        if tile_at(x+offset.x, y+offset.y) not in ["road", "bridge"]:
                            var edge := center+Vector2(offset)*11
                            var tangent := Vector2(-offset.y, offset.x)*12
                            draw_line(edge-tangent, edge+tangent, Color("958764"), 1)
                _:
                    for i in range(2):
                        var grass := origin+Vector2(3+variation(x,y,i+1)*17, 4+variation(y,x,i+5)*16)
                        draw_line(grass, grass+Vector2(-1,-2), color.darkened(.18), 1)
                        draw_line(grass+Vector2(1,0), grass+Vector2(2,-3), color.lightened(.12), 1)
                    if n > .94:
                        draw_circle(center+Vector2(6,3), 1, Color("e3cc8e"))

func tree(center: Vector2, n: float, season: String) -> void:
    draw_circle(center+Vector2(2,3), 7, Color(0.12, .22, .16, .22))
    draw_line(center+Vector2(0,4), center+Vector2(0,-3), Color("675a3e"), 3)
    var foliage := Color("3f654c").lightened(n*.12)
    if season == "autumn": foliage = foliage.lerp(Color("ba9052"), n*.65)
    if season == "winter": foliage = foliage.lerp(Color("c8d3b8"), .38)
    draw_circle(center+Vector2(0,-3), 7, foliage)
    draw_circle(center+Vector2(-2,-5), 4, foliage.lightened(.12))
