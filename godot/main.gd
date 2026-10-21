extends Node2D

var api := "http://127.0.0.1:8765"
const MAP_RECT := Rect2(24, 130, 864, 516)
const WorldView = preload("res://world_view.gd")
var state: Dictionary = {}
var selected := "a0"
var player_mode := true
var poll: HTTPRequest
var sender: HTTPRequest
var command_queue: Array = []
var busy := false
var elapsed := 0.0
var movement_elapsed := 0.0
var status_label: Label
var selector: OptionButton
var selector_ids: Array[String] = []
var details: RichTextLabel
var memory_details: RichTextLabel
var inventory_details: RichTextLabel
var settlement_details: RichTextLabel
var timeline: RichTextLabel
var conversation_history: RichTextLabel
var history_tabs: TabContainer
var top_stats: Label
var cognition_stats: Label
var mode_button: Button
var dialogue: TextEdit
var seed_input: LineEdit
var population_input: SpinBox
var building_choice: OptionButton
var view: Node2D
var settings: PopupPanel
var setting_fields: Dictionary = {}
var auto_smoke := false
var smoke_frames := 0
var panning := false
var settings_open := false
var player_buttons: Array[Button] = []

func _ready() -> void:
    for argument in OS.get_cmdline_user_args():
        if argument.begins_with("--api="):
            api = argument.trim_prefix("--api=")
    poll = HTTPRequest.new()
    poll.timeout = 5
    add_child(poll)
    poll.request_completed.connect(_received_state)
    sender = HTTPRequest.new()
    sender.timeout = 15
    add_child(sender)
    sender.request_completed.connect(_received_command)
    _make_ui()
    poll.request(api + "/state")
    auto_smoke = "--smoke" in OS.get_cmdline_user_args()

func label_at(text: String, pos: Vector2, size: int = 16) -> Label:
    var item := Label.new()
    item.text = text
    item.position = pos
    item.add_theme_font_size_override("font_size", size)
    item.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(item)
    return item

func button_at(text: String, pos: Vector2, callback: Callable, width: float = 100, is_player := false) -> Button:
    var item := Button.new()
    item.text = text
    item.position = pos
    item.size = Vector2(width, 30)
    item.pressed.connect(callback)
    add_child(item)
    if is_player:
        player_buttons.append(item)
    return item

func rich_tab(tabs: TabContainer, title: String) -> RichTextLabel:
    var item := RichTextLabel.new()
    item.name = title
    item.bbcode_enabled = false
    item.selection_enabled = true
    item.add_theme_font_size_override("normal_font_size", 14)
    tabs.add_child(item)
    return item

func _make_ui() -> void:
    label_at("G E N E S I S  2", Vector2(24, 14), 28).modulate = Color("e3ce9a")
    label_at("THE LIVING WORLD  /  Independent minds, shared world", Vector2(305, 28), 14)
    top_stats = label_at("Connecting to local simulation…", Vector2(24, 64), 14)
    cognition_stats = label_at("OFFLINE — local deterministic decisions", Vector2(24, 88), 13)
    mode_button = button_at("Player mode", Vector2(900, 15), _toggle_mode, 130)
    button_at("Pause / Resume", Vector2(1040, 15), func(): send({"action": "pause", "paused": not state.get("paused", false)}), 145)
    button_at("Settings", Vector2(1195, 15), _open_settings, 70)
    button_at("Save", Vector2(900, 53), func(): send({"action": "save"}), 70)
    button_at("Load", Vector2(977, 53), func(): send({"action": "load"}), 70)
    button_at("1×", Vector2(1054, 53), func(): send({"action": "speed", "speed": 2}), 50)
    button_at("5×", Vector2(1111, 53), func(): send({"action": "speed", "speed": 10}), 50)
    button_at("Step", Vector2(1168, 53), func(): send({"action": "step"}), 97)
    button_at("Follow", Vector2(900, 91), func(): view.follow_agent = not view.follow_agent, 95)
    button_at("Reset camera", Vector2(1005, 91), func(): view.reset_camera(), 130)
    button_at("Reason now", Vector2(1145, 91), func(): send({"action": "request_reasoning", "target": selected}), 120)
    var clip := Control.new()
    clip.position = MAP_RECT.position
    clip.size = MAP_RECT.size
    clip.clip_contents = true
    clip.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(clip)
    view = WorldView.new()
    view.view_size = MAP_RECT.size
    clip.add_child(view)
    selector = OptionButton.new()
    selector.position = Vector2(910, 134)
    selector.size = Vector2(350, 28)
    selector.item_selected.connect(func(index: int): selected = selector_ids[index]; _inspect())
    add_child(selector)
    var inspector := TabContainer.new()
    inspector.position = Vector2(910, 170)
    inspector.size = Vector2(350, 374)
    add_child(inspector)
    details = rich_tab(inspector, "Agent")
    memory_details = rich_tab(inspector, "Mind")
    inventory_details = rich_tab(inspector, "Player")
    settlement_details = rich_tab(inspector, "Town")
    label_at("WASD: player / observer camera • wheel: zoom • middle drag: pan", Vector2(24, 652), 13)
    label_at("PLAYER ACTIONS — proximity and inventory rules apply", Vector2(910, 552), 12)
    button_at("Gather", Vector2(910, 578), func(): player_command({"action": "gather"}), 80, true)
    button_at("Rest", Vector2(998, 578), func(): player_command({"action": "rest"}), 80, true)
    button_at("Eat", Vector2(1086, 578), func(): player_command({"action": "eat"}), 80, true)
    button_at("Drink", Vector2(1174, 578), func(): player_command({"action": "drink"}), 80, true)
    button_at("Trade", Vector2(910, 616), func(): player_command({"action": "trade", "target": selected}), 80, true)
    button_at("Negotiate", Vector2(998, 616), func(): player_command({"action": "negotiate", "target": selected}), 100, true)
    button_at("Retreat", Vector2(1106, 616), func(): player_command({"action": "retreat", "target": selected}), 70, true)
    button_at("Defend", Vector2(1184, 616), func(): player_command({"action": "defend", "target": selected}), 70, true)
    button_at("Fight", Vector2(910, 654), func(): player_command({"action": "fight", "target": selected}), 80, true)
    button_at("Dispute", Vector2(998, 654), func(): player_command({"action": "challenge", "target": selected}), 80, true)
    button_at("Get food", Vector2(1086, 654), func(): player_command({"action": "retrieve", "kind": "food"}), 80, true)
    button_at("Store wood", Vector2(1174, 654), func(): player_command({"action": "store", "kind": "wood"}), 80, true)
    building_choice = OptionButton.new()
    building_choice.position = Vector2(24, 681)
    building_choice.size = Vector2(145, 30)
    for kind in ["house", "farm", "storage", "workshop", "market", "watchtower", "road", "bridge", "public_hall"]:
        building_choice.add_item(kind)
    add_child(building_choice)
    button_at("Plan building", Vector2(179, 681), func(): player_command({"action": "build", "kind": building_choice.get_item_text(building_choice.selected)}), 120, true)
    button_at("Build work", Vector2(309, 681), func(): player_command({"action": "work"}), 110, true)
    label_at("Gold: player   Green / Blue: settlements   Amber: dispute", Vector2(440, 689), 12)
    history_tabs = TabContainer.new()
    history_tabs.position = Vector2(24, 724)
    history_tabs.size = Vector2(864, 132)
    add_child(history_tabs)
    timeline = rich_tab(history_tabs, "Events")
    conversation_history = rich_tab(history_tabs, "Conversations")
    dialogue = TextEdit.new()
    dialogue.position = Vector2(910, 704)
    dialogue.size = Vector2(350, 86)
    dialogue.placeholder_text = "Type any message to the selected nearby inhabitant…"
    dialogue.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
    add_child(dialogue)
    button_at("Talk", Vector2(910, 798), _talk, 100, true)
    button_at("Share claim", Vector2(1020, 798), func(): player_command({"action": "claim", "target": selected, "message": dialogue.text}), 120, true)
    button_at("New world…", Vector2(1150, 798), _new_world_dialog, 110)
    status_label = label_at("Ready. LLM status is shown above; dialogue never blocks world rendering.", Vector2(24, 862), 13)
    status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    status_label.size = Vector2(1240, 35)
    _make_settings()

func _toggle_mode() -> void:
    player_mode = not player_mode
    mode_button.text = "Player mode" if player_mode else "Observer mode"
    for item in player_buttons:
        item.disabled = not player_mode
    dialogue.editable = player_mode
    status_label.text = "Player controls active." if player_mode else "Observer: WASD pans the camera. Player actions are disabled."

func player_command(command: Dictionary) -> void:
    if player_mode:
        send(command)
    else:
        status_label.text = "Switch to Player mode to act in the world."

func _talk() -> void:
    if dialogue.text.strip_edges().is_empty():
        status_label.text = "Enter a message first."
        return
    player_command({"action": "talk", "target": selected, "message": dialogue.text})
    history_tabs.current_tab = 1

func send(command: Dictionary) -> void:
    if command_queue.size() >= 32:
        status_label.text = "Command queue is full; waiting for the backend."
        return
    if command.get("action") == "move" and command_queue.any(func(c): return c.get("action") == "move"):
        return
    command_queue.append(command)

func _process(delta: float) -> void:
    elapsed += delta
    movement_elapsed += delta
    if elapsed > .3 and poll.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED:
        elapsed = 0
        poll.request(api + "/state")
    if not busy and not command_queue.is_empty():
        busy = true
        var error := sender.request(api + "/command", ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(command_queue.pop_front()))
        if error != OK:
            busy = false
            status_label.text = "Could not send command: %s" % error_string(error)
    var focused := get_viewport().gui_get_focus_owner()
    if not settings_open and not (focused is LineEdit or focused is TextEdit):
        var direction := Vector2.ZERO
        if Input.is_physical_key_pressed(KEY_W) or Input.is_physical_key_pressed(KEY_UP): direction.y -= 1
        if Input.is_physical_key_pressed(KEY_S) or Input.is_physical_key_pressed(KEY_DOWN): direction.y += 1
        if Input.is_physical_key_pressed(KEY_A) or Input.is_physical_key_pressed(KEY_LEFT): direction.x -= 1
        if Input.is_physical_key_pressed(KEY_D) or Input.is_physical_key_pressed(KEY_RIGHT): direction.x += 1
        if direction != Vector2.ZERO:
            if player_mode and movement_elapsed > .14:
                movement_elapsed = 0
                if direction.x != 0: direction.y = 0
                player_command({"action": "move", "dx": int(direction.x), "dy": int(direction.y)})
            elif not player_mode:
                view.follow_agent = false
                view.camera_offset -= direction.normalized() * delta * 250
    if auto_smoke:
        smoke_frames += 1
        if not state.is_empty() and smoke_frames > 30:
            assert(state.agents.size() >= 2)
            assert(state.terrain.size() > 0)
            assert(not details.text.is_empty())
            assert(not inventory_details.text.is_empty())
            view.zoom_at(1.1, Vector2(100,100))
            assert(view.zoom > 1)
            view.reset_camera()
            _open_settings()
            assert(settings.visible)
            assert(not setting_fields.model.text.is_empty())
            settings.hide()
            _toggle_mode()
            assert(not player_mode)
            _toggle_mode()
            assert(player_mode)
            print("GENESIS 2 client smoke passed: live state, inspector, inventory, camera, modes and cognition settings")
            get_tree().quit(0)
        elif smoke_frames > 1200:
            push_error("GENESIS smoke timed out waiting for backend")
            get_tree().quit(1)

func _received_state(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
    if code != 200:
        status_label.text = "Backend unavailable. Start with python run.py."
        return
    var parsed = JSON.parse_string(body.get_string_from_utf8())
    if not parsed is Dictionary:
        return
    state = parsed
    view.state = state
    view.selected = selected
    var environment: Dictionary = state.get("environment", {})
    top_stats.text = "Tick %d • %s %s • %d inhabitants • %d buildings • %.2f ms/tick • %s" % [state.tick, state.season, environment.get("weather", ""), state.agents.size()-1, state.buildings.size(), state.get("tick_ms", 0), "PAUSED" if state.get("paused", false) else "RUNNING"]
    var cognition: Dictionary = state.get("cognition", {})
    var metrics: Dictionary = cognition.get("metrics", {})
    var config: Dictionary = cognition.get("config", {})
    cognition_stats.text = "%s • %s / %s • queued %d • active %d • completed %d • failed %d • %.0f ms • %.1f calls/min" % [str(cognition.get("mode", "offline")).to_upper(), config.get("provider", "disabled"), config.get("model", "no model"), metrics.get("queued", 0), metrics.get("inflight", 0), metrics.get("completed", 0), metrics.get("failed", 0), metrics.get("latency_ms", 0), metrics.get("throughput_per_minute", 0)]
    var lines: Array[String] = []
    for e in state.events.slice(maxi(0, state.events.size()-30)):
        lines.append("[%04d] %s" % [e.tick, e.text])
    timeline.text = "\n".join(lines)
    var new_ids: Array[String] = []
    for category in ["agents", "settlements", "buildings", "resources", "wildlife"]:
        for key in state[category]: new_ids.append(key)
    if new_ids != selector_ids:
        selector_ids = new_ids
        selector.clear()
        for category in ["agents", "settlements", "buildings", "resources", "wildlife"]:
            for entity in state[category].values():
                selector.add_item("%s / %s" % [category, entity.get("name", entity.id)])
    if selected in selector_ids:
        selector.select(selector_ids.find(selected))
    else:
        selected = "player"
    _inspect()

func _received_command(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
    busy = false
    var response = JSON.parse_string(body.get_string_from_utf8())
    if response is Dictionary:
        var default_text := "Queued — reply will appear in Conversations while the world continues." if response.get("queued", false) else ("Command accepted" if response.get("ok", false) else "Command failed")
        status_label.text = str(response.get("message", default_text))
    elif code != 200:
        status_label.text = "Command failed: backend unreachable"

func _inspect() -> void:
    view.selected = selected
    var home := "a"
    if state.agents.has(selected):
        var a: Dictionary = state.agents[selected]
        home = a.home
        var text := "%s / %s\n%s • age %d • home %s\n\nHP %.0f / %.0f   Stamina %.0f\nHunger %.0f   Thirst %.0f   Fatigue %.0f\nShelter: %s   Safety: %s   Social: %s\nSpeed %.2f   Defense %.0f\nEquipment: %s\n\nActivity: %s\nWhy: %s\n\nSkills: %s\nPersonality: %s\n\nInventory: %s\nRelationships: %s" % [a.name, a.id, a.occupation, a.age, a.home, a.hp, a.max_hp, a.stamina, a.hunger, a.thirst, a.fatigue, a.get("shelter", "n/a"), a.get("safety", "n/a"), a.get("social", "n/a"), a.speed, a.defense, ", ".join(a.equipment), a.activity, a.reason, JSON.stringify(a.skills), JSON.stringify(a.personality), JSON.stringify(a.inventory), JSON.stringify(a.relationships)]
        details.text = text
        memory_details.text = "GOALS\n%s\n\nPLAN\n%s\n\nPRIVATE KNOWLEDGE / BELIEFS\n%s\n\nREFLECTIONS\n%s\n\nRECENT MEMORIES\n" % [JSON.stringify(a.goals, "  "), JSON.stringify(a.get("plan", a.get("plans", [])), "  "), JSON.stringify(a.knowledge, "  "), JSON.stringify(a.get("reflections", []), "  ")]
        for m in a.memories.slice(maxi(0, a.memories.size()-8)):
            memory_details.text += "[%d] %s (source: %s, confidence: %s)\n" % [m.get("tick", 0), m.get("content", ""), m.get("source", "unknown"), m.get("confidence", 1)]
    else:
        for category in ["buildings", "settlements", "resources", "wildlife"]:
            if state[category].has(selected):
                var entity: Dictionary = state[category][selected]
                home = entity.get("home", entity.id if category == "settlements" else "a")
                details.text = category.to_upper() + "\n" + JSON.stringify(entity, "  ")
                memory_details.text = "Select an inhabitant to inspect its individual mind."
    var player: Dictionary = state.agents.get("player", {})
    inventory_details.text = "TRAVELER / PLAYER\n\nInventory\n%s\n\nEquipment\n%s\n\nProperty\n%s\n\nNeeds\nHP: %s   Hunger: %s   Thirst: %s\n\nMovement requires passable terrain and stamina. Actions use real items. Observer mode prevents player commands." % [JSON.stringify(player.get("inventory", {}), "  "), JSON.stringify(player.get("equipment", []), "  "), JSON.stringify(player.get("property", []), "  "), player.get("hp", "?"), player.get("hunger", "?"), player.get("thirst", "?")]
    settlement_details.text = JSON.stringify(state.settlements.get(home, {}), "  ")
    var histories = state.get("conversations", {})
    var conversations: Array = histories.values() if histories is Dictionary else histories
    var lines: Array[String] = []
    for conversation in conversations:
        if selected not in conversation.get("participants", []) and selected != "player": continue
        lines.append("— %s / %s —" % [conversation.get("id", "conversation"), conversation.get("state", "")])
        for turn in conversation.get("turns", []):
            var speaker: String = str(turn.get("speaker", "?"))
            var name: String = str(state.agents.get(speaker, {}).get("name", speaker))
            lines.append("[%d] %s (%s): %s" % [turn.get("tick", 0), name, turn.get("source", "unknown"), turn.get("text", "")])
    conversation_history.text = "\n".join(lines) if not lines.is_empty() else "No conversation history for this selection. Agent conversations appear here only when generated; offline events are not presented as model dialogue."

func _make_settings() -> void:
    settings = PopupPanel.new()
    settings.size = Vector2i(590, 590)
    settings.popup_hide.connect(func(): settings_open = false)
    add_child(settings)
    var box := VBoxContainer.new()
    box.position = Vector2(18, 12)
    box.size = Vector2(550, 560)
    settings.add_child(box)
    var title := Label.new()
    title.text = "LOCAL COGNITION SETTINGS"
    box.add_child(title)
    var enabled := CheckBox.new()
    enabled.text = "Enable shared LLM cognition for every inhabitant"
    setting_fields["enabled"] = enabled
    box.add_child(enabled)
    for field in ["provider", "model", "endpoint", "context_limit", "timeout", "max_concurrency", "per_agent_budget", "global_budget"]:
        var row := HBoxContainer.new()
        var caption := Label.new()
        caption.text = field.capitalize()
        caption.custom_minimum_size.x = 190
        row.add_child(caption)
        var entry := LineEdit.new()
        entry.size_flags_horizontal = Control.SIZE_EXPAND_FILL
        entry.placeholder_text = field
        row.add_child(entry)
        setting_fields[field] = entry
        box.add_child(row)
    var help := Label.new()
    help.text = "Provider: ollama or openai. Endpoint is on the backend machine.\nBudgets and concurrency limit shared inference requests.\nNo API key belongs in this form; configure credentials securely.\nDisabling inference keeps local survival and combat running."
    help.add_theme_font_size_override("font_size", 13)
    box.add_child(help)
    var apply := Button.new()
    apply.text = "Apply settings"
    apply.pressed.connect(_apply_settings)
    box.add_child(apply)
    var close := Button.new()
    close.text = "Close"
    close.pressed.connect(func(): settings.hide())
    box.add_child(close)

func _open_settings() -> void:
    var config: Dictionary = state.get("cognition", {}).get("config", {})
    var defaults := {"provider": "ollama", "model": "qwen2.5:7b", "endpoint": "http://127.0.0.1:11434", "context_limit": 8000, "timeout": 12, "max_concurrency": 2, "per_agent_budget": 4, "global_budget": 60}
    setting_fields.enabled.button_pressed = config.get("enabled", false)
    for key in defaults: setting_fields[key].text = str(config.get(key, defaults[key]))
    settings_open = true
    settings.popup_centered()

func _apply_settings() -> void:
    var config := {"enabled": setting_fields.enabled.button_pressed}
    for key in ["provider", "model", "endpoint"]:
        config[key] = setting_fields[key].text.strip_edges()
    for key in ["context_limit", "max_concurrency", "per_agent_budget", "global_budget"]:
        if not setting_fields[key].text.is_valid_int():
            status_label.text = "Settings error: %s must be an integer." % key
            return
        config[key] = int(setting_fields[key].text)
    if not setting_fields.timeout.text.is_valid_float():
        status_label.text = "Settings error: timeout must be a number."
        return
    config["timeout"] = float(setting_fields.timeout.text)
    send({"action": "configure_cognition", "config": config})
    settings.hide()

func _new_world_dialog() -> void:
    var dialog := ConfirmationDialog.new()
    dialog.title = "Create a new world"
    dialog.dialog_text = "Replaces the current in-memory world. Save first to retain it."
    dialog.size = Vector2i(470, 220)
    var row := HBoxContainer.new()
    row.position = Vector2(20, 90)
    seed_input = LineEdit.new()
    seed_input.text = "42"
    seed_input.placeholder_text = "Seed"
    seed_input.custom_minimum_size.x = 180
    row.add_child(seed_input)
    population_input = SpinBox.new()
    population_input.min_value = 1
    population_input.max_value = 100
    population_input.value = 10
    population_input.tooltip_text = "Inhabitants per settlement"
    row.add_child(population_input)
    dialog.add_child(row)
    dialog.confirmed.connect(func(): send({"action": "new", "seed": int(seed_input.text), "population": int(population_input.value)}); dialog.queue_free())
    dialog.canceled.connect(func(): dialog.queue_free())
    add_child(dialog)
    dialog.popup_centered()

func _unhandled_input(event: InputEvent) -> void:
    if event is InputEventMouseButton:
        if event.button_index == MOUSE_BUTTON_MIDDLE:
            panning = event.pressed and MAP_RECT.has_point(event.position)
        if event.pressed and MAP_RECT.has_point(event.position):
            if event.button_index == MOUSE_BUTTON_WHEEL_UP:
                view.zoom_at(1.15, event.position - MAP_RECT.position)
            elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
                view.zoom_at(1/1.15, event.position - MAP_RECT.position)
            elif event.button_index == MOUSE_BUTTON_LEFT and not state.is_empty():
                var closest := 14.0
                for category in ["agents", "buildings", "settlements", "resources", "wildlife"]:
                    for entity in state[category].values():
                        var dist: float = view.screen_point(entity).distance_to(event.position - MAP_RECT.position)
                        if dist < closest:
                            selected = entity.id
                            closest = dist
                _inspect()
    elif event is InputEventMouseMotion and panning:
        view.follow_agent = false
        view.camera_offset += event.relative
