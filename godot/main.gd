extends Node2D

const API = "http://127.0.0.1:8765"
const ORIGIN = Vector2(24, 104)
const TILE = 18.0
const TERRAIN = {
    "forest": Color("284d3d"), "plains": Color("597750"),
    "mountain": Color("707b7e"), "river": Color("326d8a"),
    "lake": Color("326d8a"), "farmland": Color("879158"), "road": Color("a4936a")
}
var state: Dictionary = {}
var selected: String = "a0"
var follow_agent := false
var poll: HTTPRequest
var sender: HTTPRequest
var command_queue: Array = []
var busy := false
var elapsed := 0.0
var status_label: Label
var selector: OptionButton
var selector_ids: Array[String] = []
var details: RichTextLabel
var timeline: RichTextLabel
var top_stats: Label
var dialogue: LineEdit
var seed_input: LineEdit
var population_input: SpinBox
var status_message := "Connecting to local simulation…"
var auto_smoke := false
var smoke_frames := 0

func _ready() -> void:
    poll = HTTPRequest.new()
    add_child(poll)
    poll.request_completed.connect(_received_state)
    sender = HTTPRequest.new()
    sender.timeout = 15
    add_child(sender)
    sender.request_completed.connect(_received_command)
    _make_ui()
    poll.request(API + "/state")
    auto_smoke = "--smoke" in OS.get_cmdline_user_args()

func label_at(text: String, pos: Vector2, size: int = 16) -> Label:
    var item := Label.new()
    item.text = text
    item.position = pos
    item.add_theme_font_size_override("font_size", size)
    add_child(item)
    return item

func button_at(text: String, pos: Vector2, callback: Callable, width: float = 100) -> Button:
    var item := Button.new()
    item.text = text
    item.position = pos
    item.size = Vector2(width, 30)
    item.pressed.connect(callback)
    add_child(item)
    return item

func _make_ui() -> void:
    label_at("G E N E S I S", Vector2(24, 16), 30).modulate = Color("e3ce9a")
    label_at("THE LIVING WORLD   /   An autonomous civilization", Vector2(260, 30), 15)
    top_stats = label_at("Loading…", Vector2(24, 65), 15)
    button_at("Pause / Resume", Vector2(900, 16), func(): send({"action": "pause", "paused": not state.get("paused", false)}), 155)
    button_at("1×", Vector2(1065, 16), func(): send({"action": "speed", "speed": 2}), 55)
    button_at("5×", Vector2(1125, 16), func(): send({"action": "speed", "speed": 10}), 55)
    button_at("Step", Vector2(1190, 16), func(): send({"action": "step"}), 65)
    button_at("Save", Vector2(900, 55), func(): send({"action": "save"}))
    button_at("Load", Vector2(1010, 55), func(): send({"action": "load"}))
    button_at("Follow", Vector2(1120, 55), func(): follow_agent = not follow_agent, 135)
    label_at("INHABITANT / WORLD INSPECTOR", Vector2(910, 104), 17).modulate = Color("e3ce9a")
    selector = OptionButton.new()
    selector.position = Vector2(910, 134)
    selector.size = Vector2(350, 28)
    selector.item_selected.connect(func(index: int): selected = selector_ids[index]; _inspect())
    add_child(selector)
    details = RichTextLabel.new()
    details.position = Vector2(910, 170)
    details.size = Vector2(350, 382)
    details.bbcode_enabled = false
    add_child(details)
    label_at("PLAYER ACTIONS  •  select a nearby inhabitant", Vector2(910, 560), 14)
    button_at("Gather", Vector2(910, 590), func(): send({"action": "gather"}))
    button_at("Rest", Vector2(1020, 590), func(): send({"action": "rest"}))
    button_at("Eat", Vector2(1130, 590), func(): send({"action": "eat"}), 60)
    button_at("Drink", Vector2(1195, 590), func(): send({"action": "drink"}), 65)
    button_at("Trade wood/food", Vector2(910, 626), func(): send({"action": "trade", "target": selected}), 165)
    button_at("Negotiate", Vector2(1085, 626), func(): send({"action": "negotiate", "target": selected}), 175)
    button_at("Retreat", Vector2(910, 662), func(): send({"action": "retreat", "target": selected}))
    button_at("Defend", Vector2(1020, 662), func(): send({"action": "defend", "target": selected}))
    button_at("Fight", Vector2(1130, 662), func(): send({"action": "fight", "target": selected}), 60)
    button_at("Dispute", Vector2(1195, 662), func(): send({"action": "challenge", "target": selected}), 65)
    dialogue = LineEdit.new()
    dialogue.position = Vector2(910, 704)
    dialogue.size = Vector2(350, 32)
    dialogue.placeholder_text = "Speak or share an unverified claim…"
    add_child(dialogue)
    button_at("Talk (Ollama)", Vector2(910, 744), func(): send({"action": "talk", "target": selected, "message": dialogue.text}), 165)
    button_at("Share claim", Vector2(1085, 744), func(): send({"action": "claim", "target": selected, "message": dialogue.text}), 175)
    button_at("Plan farm", Vector2(24, 679), func(): send({"action": "build", "kind": "farm"}), 105)
    button_at("Build work", Vector2(137, 679), func(): send({"action": "work"}), 105)
    button_at("Store wood", Vector2(250, 679), func(): send({"action": "store", "kind": "wood"}), 110)
    button_at("Get food", Vector2(368, 679), func(): send({"action": "retrieve", "kind": "food"}), 100)
    label_at("EVENT TIMELINE", Vector2(490, 686), 16).modulate = Color("e3ce9a")
    timeline = RichTextLabel.new()
    timeline.position = Vector2(24, 720)
    timeline.size = Vector2(855, 120)
    timeline.bbcode_enabled = false
    add_child(timeline)
    seed_input = LineEdit.new()
    seed_input.position = Vector2(910, 790)
    seed_input.size = Vector2(90, 30)
    seed_input.text = "42"
    seed_input.tooltip_text = "World seed"
    add_child(seed_input)
    population_input = SpinBox.new()
    population_input.position = Vector2(1010, 790)
    population_input.size = Vector2(100, 30)
    population_input.min_value = 1
    population_input.max_value = 100
    population_input.value = 10
    population_input.tooltip_text = "Inhabitants per settlement"
    add_child(population_input)
    button_at("New world", Vector2(1120, 790), func(): send({"action": "new", "seed": int(seed_input.text), "population": int(population_input.value)}), 140)
    status_label = label_at(status_message, Vector2(24, 855), 14)
    status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    status_label.size = Vector2(1230, 42)
    label_at("WASD / arrows: walk as Traveler  •  click: inspect agent, building or settlement", Vector2(24, 651), 14)

func send(command: Dictionary) -> void:
    if command_queue.size() < 10:
        command_queue.append(command)

func _process(delta: float) -> void:
    elapsed += delta
    if elapsed > 0.25 and poll.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED:
        elapsed = 0
        poll.request(API + "/state")
    if not busy and not command_queue.is_empty():
        busy = true
        var error := sender.request(API + "/command", ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(command_queue.pop_front()))
        if error != OK:
            busy = false
    if auto_smoke:
        smoke_frames += 1
        if not state.is_empty() and smoke_frames > 20:
            assert(state.agents.size() >= 21)
            assert(state.terrain.size() == 30)
            assert(not details.text.is_empty())
            print("GENESIS client smoke passed: world state, inspector, and scene loop active")
            get_tree().quit(0)
        elif smoke_frames > 600:
            push_error("GENESIS smoke timed out waiting for backend")
            get_tree().quit(1)
    queue_redraw()

func _received_state(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
    if code != 200:
        status_label.text = "Backend unavailable. Start with python run.py."
        return
    var parsed = JSON.parse_string(body.get_string_from_utf8())
    if not parsed is Dictionary:
        return
    state = parsed
    top_stats.text = "Tick %d   •   %s   •   %d inhabitants   •   %d buildings   •   %.2f ms/tick   •   %s" % [state.tick, state.season, state.agents.size()-1, state.buildings.size(), state.tick_ms, "PAUSED" if state.paused else "RUNNING"]
    var lines: Array[String] = []
    for e in state.events.slice(maxi(0, state.events.size()-7)):
        lines.append("[%04d] %s" % [e.tick, e.text])
    timeline.text = "\n".join(lines)
    var new_ids: Array[String] = []
    for category in ["agents", "settlements", "buildings", "resources", "wildlife"]:
        for key in state[category]:
            new_ids.append(key)
    if new_ids != selector_ids:
        selector_ids = new_ids
        selector.clear()
        for category in ["agents", "settlements", "buildings", "resources", "wildlife"]:
            for entity in state[category].values():
                selector.add_item("%s / %s" % [category, entity.get("name", entity.id)])
    if selected in selector_ids:
        selector.select(selector_ids.find(selected))
    _inspect()

func _received_command(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
    busy = false
    var response = JSON.parse_string(body.get_string_from_utf8())
    if response is Dictionary:
        status_label.text = str(response.get("message", "Command accepted" if response.get("ok", false) else "Command failed"))
    elif code != 200:
        status_label.text = "Command failed: backend unreachable"

func _inspect() -> void:
    if state.agents.has(selected):
        var a: Dictionary = state.agents[selected]
        var s: Dictionary = state.settlements[a.home]
        var text := "%s  /  %s\n%s • age %d • home %s\n\nHP %.0f / %.0f    Stamina %.0f\nHunger %.0f    Thirst %.0f    Fatigue %.0f\nSpeed %.2f    Defense %.0f\nEquipment: %s\n\nActivity: %s\nWhy: %s\n\nInventory: %s\nGoals: %s\nRelationships: %s\n\nSettlement: %s / stability %.0f\nStores: %s\n\nRecent memories:\n" % [a.name, a.id, a.occupation, a.age, s.name, a.hp, a.max_hp, a.stamina, a.hunger, a.thirst, a.fatigue, a.speed, a.defense, ", ".join(a.equipment), a.activity, a.reason, JSON.stringify(a.inventory), JSON.stringify(a.goals), JSON.stringify(a.relationships), s.conflict, s.stability, JSON.stringify(s.inventory)]
        for m in a.memories.slice(maxi(0, a.memories.size()-4)):
            text += "[%d] %s\n" % [m.tick, m.content]
        details.text = text
    elif state.buildings.has(selected):
        details.text = "Building\n" + JSON.stringify(state.buildings[selected], "  ")
    elif state.settlements.has(selected):
        details.text = "Settlement / council and diplomacy\n" + JSON.stringify(state.settlements[selected], "  ")
    elif state.resources.has(selected):
        details.text = "Resource\n" + JSON.stringify(state.resources[selected], "  ")
    elif state.wildlife.has(selected):
        details.text = "Wildlife\n" + JSON.stringify(state.wildlife[selected], "  ")

func point(entity: Dictionary) -> Vector2:
    return ORIGIN + Vector2(entity.x + 0.5, entity.y + 0.5) * TILE

func _draw() -> void:
    if state.is_empty():
        return
    for y in range(state.height):
        for x in range(state.width):
            var rect := Rect2(ORIGIN + Vector2(x, y)*TILE, Vector2(TILE-0.5, TILE-0.5))
            var terrain: String = state.terrain[y][x]
            draw_rect(rect, TERRAIN[terrain])
            if terrain == "forest":
                var center := rect.get_center()
                draw_colored_polygon(PackedVector2Array([center+Vector2(0,-6), center+Vector2(5,4), center+Vector2(-5,4)]), Color("173c30"))
            elif terrain == "mountain":
                var center := rect.get_center()
                draw_polyline(PackedVector2Array([center+Vector2(-6,4), center+Vector2(0,-6), center+Vector2(6,4)]), Color("b5bfba"), 1)
    for s in state.settlements.values():
        draw_arc(point(s), 55, 0, TAU, 48, Color("d7c28c") if s.conflict == "peace" else Color("f5ac62"), 1.5)
        draw_string(ThemeDB.fallback_font, point(s)+Vector2(-45,-62), s.name+" / "+s.conflict, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("fff1ca"))
    for r in state.resources.values():
        if r.quantity > 0:
            draw_circle(point(r), 4, Color("e6cf74") if r.kind != "water" else Color("a6dded"))
    for b in state.buildings.values():
        var rect := Rect2(point(b)-Vector2(7,7), Vector2(14,14))
        draw_rect(rect, Color("dccaaa") if b.complete else Color("8c7856"), b.complete)
        draw_line(rect.position, rect.position+Vector2(7,-5), Color("463c34"), 2)
        draw_line(rect.position+Vector2(7,-5), rect.position+Vector2(14,0), Color("463c34"), 2)
    for animal in state.wildlife.values():
        draw_circle(point(animal), 3.5, Color("bca38d"))
    for c in state.conflicts.values():
        if c.state == "active":
            var a: Dictionary = state.agents[c.a]
            var b: Dictionary = state.agents[c.b]
            draw_line(point(a), point(b), Color("ffd580"), 2)
            draw_string(ThemeDB.fallback_font, (point(a)+point(b))/2+Vector2(0,-13), "DISPUTE", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color("ffe7ac"))
    for a in state.agents.values():
        var pos := point(a)
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
            if follow_agent:
                draw_string(ThemeDB.fallback_font, pos+Vector2(12,-8), a.name+": "+a.activity, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color.WHITE)

func _unhandled_input(event: InputEvent) -> void:
    if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and not state.is_empty():
        var closest := 15.0
        for category in ["agents", "buildings", "settlements", "resources", "wildlife"]:
            for entity in state[category].values():
                var dist := point(entity).distance_to(event.position)
                if dist < closest:
                    selected = entity.id
                    closest = dist
        _inspect()
    if event is InputEventKey and event.pressed and not event.echo:
        var focused := get_viewport().gui_get_focus_owner()
        if focused is LineEdit:
            return
        var directions := {KEY_W: [0,-1], KEY_UP: [0,-1], KEY_S: [0,1], KEY_DOWN: [0,1], KEY_A: [-1,0], KEY_LEFT: [-1,0], KEY_D: [1,0], KEY_RIGHT: [1,0]}
        if directions.has(event.keycode):
            var d: Array = directions[event.keycode]
            send({"action": "move", "dx": d[0], "dy": d[1]})
