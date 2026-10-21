extends Control

var api := "http://127.0.0.1:8765"
const MAP_RECT := Rect2(24, 130, 864, 516)
const UIStyle = preload("res://ui_style.gd")
const WorldView = preload("res://world_3d.gd")
const EnvironmentPanel = preload("res://environment_panel.gd")
var god_panel: PopupPanel
const FlatView = preload("res://world_view.gd")
var flat_renderer := false
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
var capture_path := ""
var smoke_frames := 0
var panning := false
var settings_open := false
var player_buttons: Array[Button] = []
var actions_popup: PopupPanel
var actions_open := false
var action_fields: Dictionary = {}
var agreement_ids: Array[String] = []
var proposal_ids: Array[String] = []
var placing_site := false
var chat_status: Label
var talk_button: Button
var journal: PopupPanel
var journal_events: RichTextLabel
var journal_conversations: RichTextLabel
var show_all_conversations := false
var journal_open := false

func _ready() -> void:
    for argument in OS.get_cmdline_user_args():
        if argument == "--flat": flat_renderer = true
        if argument.begins_with("--capture="):
            capture_path = argument.trim_prefix("--capture=")
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
    theme = UIStyle.make_theme()
    mouse_filter = Control.MOUSE_FILTER_IGNORE
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
    item.bbcode_enabled = true
    item.add_theme_constant_override("line_separation", 4)
    item.meta_clicked.connect(_focus_link)
    item.selection_enabled = true
    item.add_theme_font_size_override("normal_font_size", 14)
    tabs.add_child(item)
    return item

func _make_ui() -> void:
    for rect in [Rect2(14, 120, 884, 536), Rect2(900, 124, 370, 732)]:
        var panel := Panel.new()
        panel.position = rect.position
        panel.size = rect.size
        panel.add_theme_stylebox_override("panel", UIStyle.box(Color("172923"), Color("43584a"), 9))
        panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
        add_child(panel)
    label_at("G E N E S I S  3", Vector2(24, 14), 28).modulate = Color("e3ce9a")
    label_at("THE LIVING WORLD  /  Civilization & survival", Vector2(305, 28), 14)
    top_stats = label_at("Connecting to local simulation…", Vector2(24, 64), 14)
    cognition_stats = label_at("OFFLINE — local deterministic decisions", Vector2(24, 88), 13)
    button_at("God Mode",Vector2(775,15),_open_god_mode,110)
    mode_button = button_at("Player mode", Vector2(900, 15), _toggle_mode, 130)
    button_at("Pause / Resume", Vector2(1040, 15), func(): send({"action": "pause", "paused": not state.get("paused", false)}), 145)
    button_at("Settings", Vector2(1195, 15), _open_settings, 70)
    button_at("Save", Vector2(900, 53), func(): send({"action": "save"}), 70)
    button_at("Load", Vector2(977, 53), func(): send({"action": "load"}), 70)
    button_at("1×", Vector2(1054, 53), func(): send({"action": "speed", "speed": 2}), 50)
    button_at("5×", Vector2(1111, 53), func(): send({"action": "speed", "speed": 10}), 50)
    button_at("Step", Vector2(1168, 53), func(): send({"action": "step"}), 97)
    button_at("Follow", Vector2(900, 91), func(): view.follow_agent = not view.follow_agent, 95)
    button_at("Focus", Vector2(1005, 91), func(): view.focus_selected(), 60)
    button_at("Map", Vector2(1075, 91), func(): view.reset_camera(), 60)
    button_at("Reason now", Vector2(1145, 91), func(): send({"action": "request_reasoning", "target": selected}), 120)
    var clip := Control.new()
    clip.position = MAP_RECT.position
    clip.size = MAP_RECT.size
    clip.clip_contents = true
    clip.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(clip)
    view = FlatView.new() if flat_renderer else WorldView.new()
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
    label_at("WASD move / pan · wheel zoom · middle drag · F focus · Home map · F1/F2 towns · P player", Vector2(24, 657), 12)
    label_at("ACTIONS  /  requires reach & supplies", Vector2(910, 552), 12)
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
    for kind in ["house", "farm", "storage", "workshop", "market", "watchtower", "road", "bridge", "hall", "well","barn","warehouse","mine","furnace","blacksmith","carpenter","rain_collector","campfire","hearth","wall","gate"]:
        building_choice.add_item(kind)
    add_child(building_choice)
    button_at("Plan building", Vector2(179, 681), func(): player_command({"action": "build", "kind": building_choice.get_item_text(building_choice.selected)}), 120, true)
    button_at("Build work", Vector2(309, 681), func(): player_command({"action": "work"}), 110, true)
    button_at("More actions…", Vector2(440, 681), _open_actions, 135, true)
    label_at("Gold traveler · Green Willowmere · Blue Stonehaven", Vector2(24, 112), 11)
    button_at("Journal", Vector2(590, 681), func(): journal.popup_centered(); journal_open = true, 95)
    button_at("Map labels", Vector2(695, 681), func(): view.labels_visible = not view.labels_visible, 100)
    button_at("Icons", Vector2(805, 681), func(): view.details_visible = not view.details_visible, 75)
    history_tabs = TabContainer.new()
    history_tabs.position = Vector2(24, 724)
    history_tabs.size = Vector2(864, 132)
    add_child(history_tabs)
    timeline = rich_tab(history_tabs, "Events")
    conversation_history = rich_tab(history_tabs, "Conversations")
    dialogue = TextEdit.new()
    dialogue.position = Vector2(910, 704)
    dialogue.size = Vector2(350, 78)
    dialogue.placeholder_text = "Type any message to the selected nearby inhabitant…"
    dialogue.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
    add_child(dialogue)
    chat_status = label_at("Select an inhabitant to talk", Vector2(910, 787), 12)
    chat_status.size = Vector2(350, 22)
    chat_status.clip_text = true
    talk_button = button_at("Send message", Vector2(910, 814), _talk, 120, true)
    button_at("Share news", Vector2(1040, 814), func(): player_command({"action": "claim", "target": selected, "message": dialogue.text}), 120, true)
    button_at("New world…", Vector2(1170, 814), _new_world_dialog, 85)
    status_label = label_at("Ready. LLM status is shown above; dialogue never blocks world rendering.", Vector2(24, 862), 13)
    status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    status_label.size = Vector2(1240, 35)
    _make_settings()
    _make_actions()
    _make_journal()
    god_panel=EnvironmentPanel.new()
    god_panel.command_requested.connect(send)
    add_child(god_panel)

func _open_god_mode() -> void:
    if player_mode: _toggle_mode()
    god_panel.update_world(state)
    god_panel.popup_centered()

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
    if not god_panel.visible and not settings_open and not actions_open and not journal_open and not placing_site and not (focused is LineEdit or focused is TextEdit):
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
                view.pan(-direction.normalized()*delta*250)
    if auto_smoke:
        smoke_frames += 1
        if not state.is_empty() and smoke_frames > 30:
            auto_smoke = false
            assert(state.agents.size() >= 2)
            assert(state.terrain.size() > 0)
            assert(not details.text.is_empty())
            assert(not inventory_details.text.is_empty())
            var old_zoom: float = view.zoom
            view.zoom_at(1.1, Vector2(100,100))
            assert(view.zoom > old_zoom)
            view.focus_selected()
            assert(view.zoom >= 1.3)
            assert(view.terrain_layer.redraw_count > 0 if flat_renderer else view.terrain_revision > 0)
            assert(theme != null)
            god_panel.popup_centered()
            await get_tree().process_frame
            assert(god_panel.visible)
            assert(god_panel.fields.weather.item_count==11)
            assert(god_panel.fields.region.item_count==4)
            god_panel.hide()
            assert(details.bbcode_enabled)
            journal.popup_centered()
            assert(journal.visible)
            await get_tree().process_frame
            await get_tree().process_frame
            var journal_close := journal.find_child("CloseJournal",true,false) as Button
            var journal_tabs := journal.find_child("JournalTabs",true,false) as TabContainer
            assert(journal_close.size.y < 60)
            assert(not journal_close.get_rect().intersects(journal_tabs.get_rect()))
            journal.hide()
            view.reset_camera()
            _open_settings()
            assert(settings.visible)
            assert(not setting_fields.model.text.is_empty())
            assert(setting_fields.context_limit.text.is_valid_int())
            assert(setting_fields.max_concurrency.text.is_valid_int())
            settings.hide()
            _open_actions()
            assert(actions_popup.visible)
            assert(action_fields.recipe.item_count == 4)
            await get_tree().process_frame
            await get_tree().process_frame
            var actions_close := actions_popup.find_child("CloseActions",true,false) as Button
            var actions_tabs := actions_popup.find_child("ActionTabs",true,false) as TabContainer
            assert(actions_close.size.y < 60)
            assert(not actions_close.get_rect().intersects(actions_tabs.get_rect()))
            actions_popup.hide()
            _toggle_mode()
            assert(not player_mode)
            _toggle_mode()
            assert(player_mode)
            print("GENESIS 3 client smoke passed: live state, inspector, inventory, camera, modes, cognition settings and action panels")
            auto_smoke = false
            _finish_smoke()
        elif smoke_frames > 1200:
            push_error("GENESIS smoke timed out waiting for backend")
            get_tree().quit(1)

func _finish_smoke() -> void:
    if not capture_path.is_empty():
        await get_tree().process_frame
        await get_tree().process_frame
        await RenderingServer.frame_post_draw
        var picture := get_viewport().get_texture().get_image()
        if picture == null or picture.is_empty():
            push_error("Capture requires a graphical rendering driver")
            get_tree().quit(1)
            return
        var error := picture.save_png(capture_path)
        if error != OK:
            push_error("Cannot write capture: " + error_string(error))
            get_tree().quit(1)
            return
        print("Rendered capture: " + capture_path)
        view.focus_selected()
        await RenderingServer.frame_post_draw
        get_viewport().get_texture().get_image().save_png(capture_path.get_basename()+"-detail.png")
    get_tree().quit(0)

func _received_state(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
    if code != 200:
        status_label.text = "Backend unavailable. Start with python run.py."
        return
    var parsed = JSON.parse_string(body.get_string_from_utf8())
    if not parsed is Dictionary:
        return
    state = parsed
    god_panel.update_world(state)
    view.accept_state(state)
    view.selected = selected
    var environment: Dictionary = state.get("environment", {})
    top_stats.text = "%s · %s · Day %d, %02d:00 · %d inhabitants · %d buildings · %s" % [str(state.season).capitalize(),str(state.get("weather","clear")).capitalize(),1+int(state.tick)/240,int(state.get("hour",0)),state.agents.size()-1,state.buildings.size(),"Paused" if state.get("paused",false) else "Living world"]
    top_stats.tooltip_text = "Tick %d · %.2f ms per simulation tick" % [state.tick,state.get("tick_ms",0)]
    top_stats.mouse_filter = Control.MOUSE_FILTER_PASS
    var cognition: Dictionary = state.get("cognition", {})
    var metrics: Dictionary = cognition.get("metrics", {})
    var config: Dictionary = cognition.get("config", {})
    cognition_stats.tooltip_text = "Completed %d · Failed %d · %.0f ms last reply · %.1f calls/min\n%s" % [metrics.get("completed",0),metrics.get("failed",0),metrics.get("latency_ms",0),metrics.get("throughput_per_minute",0),str(metrics.get("last_error",""))]
    cognition_stats.mouse_filter = Control.MOUSE_FILTER_PASS
    if not str(state.get("error", "")).is_empty():
        status_label.text = "Simulation paused: " + str(state.error)
    if cognition.get("mode","offline") == "offline":
        cognition_stats.text = "OFFLINE · Deterministic simulation · Enable local Ollama in Settings"
    else:
        cognition_stats.text = "LLM MINDS · %s · %d thinking · %d queued%s" % [config.get("model","local model"),metrics.get("inflight",0),metrics.get("queued",0)," · Provider error (hover for details)" if not str(metrics.get("last_error","")).is_empty() else ""]
    var lines: Array[String] = []
    for e in state.events.slice(maxi(0, state.events.size()-50)):
        if e.kind == "reasoning": continue
        var caption := UIStyle.safe(e.text)
        if not e.actors.is_empty(): caption = "[url=%s]%s[/url]" % [e.actors[0], caption]
        lines.append("[color=#a2b4ad]%04d · %-10s[/color] %s" % [e.tick, str(e.kind).replace("_", " ").capitalize(), caption])
    _write_rich(timeline, "\n".join(lines), true)
    _write_rich(journal_events, timeline.text, true)
    var new_ids: Array[String] = []
    for category in ["agents", "settlements", "buildings", "resources", "wildlife","threats"]:
        for key in state.get(category,{}): new_ids.append(key)
    if new_ids != selector_ids:
        selector_ids = new_ids
        selector.clear()
        for category in ["agents", "settlements", "buildings", "resources", "wildlife","threats"]:
            for entity in state.get(category,{}).values():
                selector.add_item("%s / %s" % [category, entity.get("name", entity.id)])
    if selected in selector_ids:
        selector.select(selector_ids.find(selected))
    else:
        selected = "player"
    _inspect()
    if actions_open: _refresh_action_lists()

func _received_command(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
    busy = false
    var response = JSON.parse_string(body.get_string_from_utf8())
    if response is Dictionary:
        var default_text := "Queued — reply will appear in Conversations while the world continues." if response.get("queued", false) else ("Command accepted" if response.get("ok", false) else "Command failed")
        status_label.text = str(response.get("message", default_text))
    elif code != 200:
        status_label.text = "Command failed: backend unreachable"

func _write_rich(item: RichTextLabel, value: String, stick_bottom := false) -> void:
    if item.text == value: return
    var bar := item.get_v_scroll_bar()
    var old_value := bar.value
    var at_bottom := bar.value >= bar.max_value-bar.page-4
    item.text = value
    if stick_bottom and at_bottom:
        item.scroll_to_line(maxi(0,item.get_line_count()-1))
    else:
        bar.set_deferred("value",old_value)

func _focus_link(id: Variant) -> void:
    selected = str(id)
    _inspect()
    view.focus_selected()

func _inventory_mass(goods: Dictionary) -> float:
    var total:=0.0
    var definitions: Dictionary=state.get("catalogue",{}).get("resources",{})
    for kind in goods: total+=float(goods[kind])*float(definitions.get(kind,{}).get("mass",1))
    return total

func _name(id: String) -> String:
    return str(state.agents.get(id, state.settlements.get(id, {})).get("name", id))

func _inspect() -> void:
    view.selected = selected
    var home := "a"
    if state.agents.has(selected):
        var a: Dictionary = state.agents[selected]
        home = a.home
        var text := UIStyle.heading(a.name + "  /  " + str(a.occupation).capitalize())
        text += "%s · age %d\n\n" % [UIStyle.safe(_name(a.home)), a.age]
        text += UIStyle.heading("WELLBEING")
        text += "Health  %.0f / %.0f     Stamina  %.0f\nHunger  %.0f    Thirst  %.0f    Fatigue  %.0f\nSafety need  %.0f    Company need  %.0f\n\n" % [a.hp,a.max_hp,a.stamina,a.hunger,a.thirst,a.fatigue,a.get("safety",0),a.get("social",0)]
        text += UIStyle.heading(str(a.activity).capitalize()) + UIStyle.safe(a.reason) + "\n\n"
        text += "Warmth need %.0f · Carrying %.0f / %.0f units\n\n" % [a.get("warmth",0),_inventory_mass(a.inventory),a.get("carry_capacity",120)]
        var job: Dictionary=state.get("production_jobs",{}).get(a.get("production_job",""),{})
        if not job.is_empty() and job.get("state","")=="working": text+="Producing %s · %.0f / %.0f work\n\n" % [job.recipe,job.progress,job.duration]
        if a.get("extraction",{}).get("progress",0)>0: text+="Extraction · %.0f work on %s\n\n" % [a.extraction.progress,UIStyle.safe(a.extraction.get("target",""))]
        text += UIStyle.heading("CARRIED GOODS") + UIStyle.goods(a.inventory) + "\n\n"
        text += UIStyle.heading("EQUIPMENT") + UIStyle.safe(", ".join(a.equipment) if not a.equipment.is_empty() else "No equipment") + "\n\n"
        text += UIStyle.heading("SKILLS & CHARACTER")
        for skill in a.skills: text += "%s  %.1f  ·  " % [UIStyle.safe(str(skill).capitalize()),a.skills[skill]]
        text += "\n"
        for attribute in a.personality: text += "%s %d%%  ·  " % [UIStyle.safe(str(attribute).capitalize()),a.personality[attribute]*100]
        text += "\n\n" + UIStyle.heading("RELATIONSHIPS")
        if a.relationships.is_empty(): text += "No established relationships yet.\n"
        for id in a.relationships:
            var r: Dictionary = a.relationships[id]
            text += "%s\n  Trust %+.0f%% · Familiarity %.0f%%\n  Cooperation %.0f%% · Rivalry %.0f%%\n" % [UIStyle.safe(_name(id)),r.get("trust",0)*100,r.get("familiarity",0)*100,r.get("cooperation",0)*100,r.get("rivalry",0)*100]
        _write_rich(details,text)
        var mind := UIStyle.heading("PERSONAL GOALS")
        for goal in a.goals.slice(-4): mind += "• %s\n" % UIStyle.safe(goal.get("description",goal))
        mind += "\n" + UIStyle.heading("PLAN  /  " + str(a.get("plan_status","idle")).capitalize())
        var plan: Array = a.get("plan",[])
        for index in range(plan.size()):
            var step: Dictionary = plan[index]
            var pieces: Array[String] = []
            for key in step:
                if key != "action" and not str(key).begins_with("_"): pieces.append("%s: %s" % [key,step[key]])
            mind += "%s %d. %s %s\n" % ["✓" if index < a.get("plan_index",0) else "→",index+1,UIStyle.safe(str(step.action).capitalize()),UIStyle.safe(", ".join(pieces))]
        if not str(a.get("plan_error","")).is_empty(): mind += "[color=#e6ae74]"+UIStyle.safe(a.plan_error)+"[/color]\n"
        mind += "\n"+UIStyle.safe(a.get("plan_feedback",""))+"\n"
        mind += "\n"+UIStyle.heading("COMMITMENTS")
        for commitment in a.get("commitments",[]).slice(-6):
            mind += "%s · %s\n" % [UIStyle.safe(commitment.get("agreement",commitment.get("description","Task"))),UIStyle.safe(commitment.get("state","pending"))]
        mind += "\n"+UIStyle.heading("REMEMBERED FROM YOU")
        var remembered := false
        for belief in a.knowledge:
            if belief.get("source","") == "player":
                mind += "• %s\n  Heard at %d · %s · confidence %.0f%%\n" % [UIStyle.safe(belief.claim),belief.tick,UIStyle.safe(belief.get("status","unverified")),belief.get("confidence",.5)*100]
                remembered = true
        if not remembered: mind += "No remembered report from the traveler yet.\n"
        mind += "\n"+UIStyle.heading("PRIVATE KNOWLEDGE")
        for belief in a.knowledge.slice(-8):
            mind += "• %s\n  Source: %s · confidence %.0f%%\n" % [UIStyle.safe(belief.claim),UIStyle.safe(_name(str(belief.source))),belief.get("confidence",.5)*100]
        mind += "\n"+UIStyle.heading("REFLECTION")+UIStyle.safe(a.get("reflection",""))+"\n\n"+UIStyle.heading("RECENT MEMORIES")
        for memory in a.memories.slice(-8): mind += "Tick %d · %s\n" % [memory.get("tick",0),UIStyle.safe(memory.get("content",""))]
        _write_rich(memory_details,mind)
    else:
        for category in ["buildings","settlements","resources","wildlife"]:
            if state.get(category,{}).has(selected):
                var entity: Dictionary = state[category][selected]
                home = entity.get("home",entity.id if category == "settlements" else "a")
                var text := UIStyle.heading(str(entity.get("name",entity.get("kind",entity.get("species",category)))).capitalize())
                for key in entity:
                    if key in ["id","name","kind","species"]: continue
                    if entity[key] is Dictionary:
                        text += "\n"+UIStyle.heading(str(key).capitalize())
                        for subkey in entity[key]: text += "%s: %s\n" % [UIStyle.safe(subkey),UIStyle.safe(entity[key][subkey])]
                    else: text += "%s: %s\n" % [UIStyle.safe(str(key).capitalize()),UIStyle.safe(entity[key])]
                _write_rich(details,text)
                _write_rich(memory_details,"Select an inhabitant to inspect its individual mind.")
    var player: Dictionary = state.agents.get("player",{})
    _write_rich(inventory_details, UIStyle.heading("THE TRAVELER")+"Health %.0f · Hunger %.0f · Thirst %.0f\n\n" % [player.get("hp",0),player.get("hunger",0),player.get("thirst",0)] + UIStyle.heading("INVENTORY")+UIStyle.goods(player.get("inventory",{}))+"\n\n"+UIStyle.heading("EQUIPMENT")+UIStyle.safe(", ".join(player.get("equipment",[])))+"\n\n"+UIStyle.heading("PROPERTY")+UIStyle.safe(", ".join(player.get("property",[])))+"\n\nActions require reach, stamina and owned materials.")
    var town: Dictionary = state.settlements.get(home,{})
    var town_text := UIStyle.heading(str(town.get("name",home)))+"%s · %s\n\n" % [str(town.get("conflict","peace")).capitalize(),str(town.get("policy","")).replace("_"," ").capitalize()]
    town_text += UIStyle.heading("COMMUNITY STORES")+UIStyle.goods(town.get("inventory",{}))+"\n\n"+UIStyle.heading("COUNCIL")
    for id in town.get("council",[]): town_text += UIStyle.safe(_name(id))+"\n"
    town_text += "\n"+UIStyle.heading("PROJECTS & TRANSPORT")
    for b in state.buildings.values():
        if b.home == home and not b.complete: town_text += "%s · %.0f work completed\n" % [str(b.kind).capitalize(),b.progress]
    for shipment in state.get("shipments",{}).values():
        if shipment.get("origin","") == home: town_text += "%s → %s · %s\n" % [UIStyle.safe(shipment.id),UIStyle.safe(_name(str(shipment.get("destination","")))),UIStyle.safe(shipment.state)]
    var local_env: Dictionary=state.get("environment",{}).get(home,{})
    if not local_env.is_empty():
        town_text+="\n"+UIStyle.heading("LOCAL ENVIRONMENT")+"%s · %.0f °C\nMoisture %.0f%% · Water reserve %.0f\n" % [str(local_env.weather).capitalize(),local_env.temperature,local_env.moisture*100,local_env.get("water_reserve",0)]
    for crop in state.get("crops",{}).values():
        if state.buildings.get(crop.building,{}).get("home","")==home: town_text+="%s: %s · %s\n" % [crop.building,crop.kind,crop.stage]
    _write_rich(settlement_details,town_text)
    _update_conversations()

func _conversation_text(all_people: bool) -> String:
    var lines: Array[String] = []
    for c in state.get("conversations",{}).values():
        if not all_people and selected not in c.get("participants",[]): continue
        var names: Array[String] = []
        for id in c.participants: names.append(_name(id))
        lines.append(UIStyle.heading(" & ".join(names)) + "[color=#a2b4ad]%s · %s[/color]" % [UIStyle.safe(c.get("topic", "Conversation")),UIStyle.safe(str(c.state).replace("_"," "))])
        if c.has("error"): lines.append("[color=#e6ae74]"+UIStyle.safe(c.error)+"[/color]")
        for outcome in c.get("outcomes",[]).slice(-4):
            lines.append("[color=#e0bd7c]Confirmed: %s · %s[/color]" % [UIStyle.safe(outcome.action),UIStyle.safe(outcome.message)])
        for turn in c.get("turns",[]):
            lines.append("[color=#89c5b3]%s[/color] [color=#a2b4ad]· %d · %s[/color]\n%s\n" % [UIStyle.safe(_name(str(turn.speaker))),turn.get("tick",0),UIStyle.safe(turn.get("source","unknown")),UIStyle.safe(turn.get("text",""))])
    return "\n".join(lines) if not lines.is_empty() else "No conversations yet. In LLM mode, nearby inhabitants may choose to talk. Select someone nearby to send your own message."

func _update_conversations() -> void:
    _write_rich(conversation_history,_conversation_text(false),true)
    _write_rich(journal_conversations,_conversation_text(show_all_conversations),true)
    var mode: String = state.get("cognition",{}).get("mode","offline")
    chat_status.text = "Offline · enable Ollama in Settings" if mode == "offline" else "Ready · select a nearby inhabitant"
    var jobs: Dictionary = state.get("cognition",{}).get("agents",{})
    if jobs.has(selected): chat_status.text = "%s · %s" % [_name(selected),str(jobs[selected]).capitalize()]
    for c in state.get("conversations",{}).values():
        if selected in c.participants and "player" in c.participants:
            if c.state == "waiting_player": chat_status.text = "Your turn · reply below"
            elif c.state == "active": chat_status.text = "Awaiting reply · the world continues"
            elif c.state == "failed": chat_status.text = "Reply failed · see Conversations"
    chat_status.tooltip_text = chat_status.text

func _make_journal() -> void:
    journal = PopupPanel.new()
    journal.size = Vector2i(900,650)
    journal.popup_hide.connect(func(): journal_open = false)
    add_child(journal)
    var frame := Control.new()
    journal.add_child(frame)
    var tabs := TabContainer.new()
    tabs.name = "JournalTabs"
    tabs.position = Vector2(0,36)
    tabs.size = Vector2(868,530)
    frame.add_child(tabs)
    journal_events = rich_tab(tabs,"World chronicle")
    journal_conversations = rich_tab(tabs,"Conversations")
    var all_toggle := CheckBox.new()
    all_toggle.text = "Observe all conversations (otherwise selected inhabitant)"
    all_toggle.position = Vector2.ZERO
    all_toggle.toggled.connect(func(value): show_all_conversations = value; _update_conversations())
    frame.add_child(all_toggle)
    var close := Button.new()
    close.name = "CloseJournal"
    close.text = "Return to world"
    close.position = Vector2(710,576)
    close.pressed.connect(func(): journal.hide())
    frame.add_child(close)

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
    for key in defaults:
        var value = config.get(key,defaults[key])
        setting_fields[key].text = str(int(value)) if key in ["context_limit","max_concurrency","per_agent_budget","global_budget"] else str(value)
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
    if god_panel.visible or settings_open or actions_open or journal_open: return
    if event is InputEventKey and event.pressed:
        if event.keycode in [KEY_F1,KEY_F2,KEY_P]:
            selected="a" if event.keycode==KEY_F1 else "b" if event.keycode==KEY_F2 else "player"
            _inspect()
            view.focus_selected()
            view.follow_agent=true
        if event.keycode == KEY_F: view.focus_selected()
        if event.keycode == KEY_HOME: view.reset_camera()
    if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE and placing_site:
        placing_site = false
        status_label.text = "Building placement cancelled."
        return
    if event is InputEventMouseButton:
        if event.button_index == MOUSE_BUTTON_MIDDLE:
            panning = event.pressed and MAP_RECT.has_point(event.position)
        if event.pressed and MAP_RECT.has_point(event.position):
            if event.button_index == MOUSE_BUTTON_WHEEL_UP:
                view.zoom_at(1.15, event.position - MAP_RECT.position)
            elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
                view.zoom_at(1/1.15, event.position - MAP_RECT.position)
            elif event.button_index == MOUSE_BUTTON_LEFT and placing_site:
                var world_position: Vector2 = view.screen_to_tile(event.position-MAP_RECT.position)
                action_fields.site_x.value = floorf(world_position.x)
                action_fields.site_y.value = floorf(world_position.y)
                action_fields.use_site.button_pressed = true
                placing_site = false
                _open_actions()
            elif event.button_index == MOUSE_BUTTON_LEFT and not state.is_empty():
                var closest := 14.0
                for category in ["agents", "buildings", "settlements", "resources", "wildlife","threats"]:
                    for entity in state.get(category,{}).values():
                        var dist: float = view.screen_point(entity).distance_to(event.position - MAP_RECT.position)
                        if dist < closest:
                            selected = entity.id
                            closest = dist
                _inspect()
    elif event is InputEventMouseMotion and panning:
        view.follow_agent = false
        view.pan(event.relative)

func action_row(box: VBoxContainer, caption: String) -> HBoxContainer:
    var row := HBoxContainer.new()
    var label := Label.new()
    label.text = caption
    label.custom_minimum_size.x = 160
    row.add_child(label)
    box.add_child(row)
    return row

func action_options(box: VBoxContainer, caption: String, key: String, values: Array) -> void:
    var row := action_row(box, caption)
    var options := OptionButton.new()
    options.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    for value in values: options.add_item(str(value))
    row.add_child(options)
    action_fields[key] = options

func action_amount(box: VBoxContainer, caption: String, key: String, minimum := 1.0, maximum := 20.0) -> void:
    var row := action_row(box, caption)
    var amount := SpinBox.new()
    amount.min_value = minimum
    amount.max_value = maximum
    amount.value = minimum
    amount.step = 1
    row.add_child(amount)
    action_fields[key] = amount

func action_button(box: VBoxContainer, caption: String, callback: Callable) -> void:
    var button := Button.new()
    button.text = caption
    button.pressed.connect(callback)
    box.add_child(button)

func action_note(box: VBoxContainer, text: String) -> void:
    var note := Label.new()
    note.text = text
    note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    note.custom_minimum_size.x = 540
    note.add_theme_font_size_override("font_size", 13)
    box.add_child(note)

func action_value(key: String) -> String:
    var field: OptionButton = action_fields[key]
    return field.get_item_text(field.selected) if field.selected >= 0 else ""

func _make_actions() -> void:
    actions_popup = PopupPanel.new()
    actions_popup.size = Vector2i(620, 620)
    actions_popup.popup_hide.connect(func(): actions_open = false)
    add_child(actions_popup)
    var frame := Control.new()
    actions_popup.add_child(frame)
    var tabs := TabContainer.new()
    tabs.name = "ActionTabs"
    tabs.position = Vector2.ZERO
    tabs.size = Vector2(588, 540)
    frame.add_child(tabs)
    var trade := VBoxContainer.new()
    trade.name = "Trade"
    tabs.add_child(trade)
    action_note(trade, "Offers target the selected nearby inhabitant. They transfer nothing until accepted. Incoming offers may expire or fail if stock/proximity changes.")
    var goods := ["food", "water", "wood", "stone", "metal", "tools","iron_ore","copper_ore","gold_ore","silver_ore","coal","clay","sand","plant_fiber","seeds","hides","wool","planks","bricks","charcoal","iron_ingot","copper_ingot","gold_ingot","silver_ingot","wheat","vegetables","fruit","raw_meat","cooked_meat","fish","bread"]
    action_options(trade, "Give", "offered", goods)
    action_fields.offered.select(2)
    action_options(trade, "Request", "wanted", goods)
    action_amount(trade, "Units each", "amount")
    action_button(trade, "Propose offer to selected inhabitant", func(): player_command({"action": "offer", "target": selected, "offered": action_value("offered"), "wanted": action_value("wanted"), "amount": action_fields.amount.value}))
    action_options(trade, "Incoming offer", "agreement", [])
    action_button(trade, "Accept selected incoming offer", func(): _agreement_action("accept"))
    action_button(trade, "Reject selected incoming offer", func(): _agreement_action("reject"))
    var workshop := VBoxContainer.new()
    workshop.name = "Workshop"
    tabs.add_child(workshop)
    action_note(workshop, "Crafting requires a nearby completed home workshop, owned materials and stamina. Equipment is added only after consuming its recipe inputs.")
    action_options(workshop, "Recipe", "recipe", ["tools", "staff", "shield", "padded_coat"])
    action_button(workshop, "Craft selected recipe", func(): player_command({"action": "craft", "item": action_value("recipe")}))
    action_options(workshop, "Store item", "stock_kind", goods)
    action_amount(workshop, "Store units", "stock_amount")
    action_button(workshop, "Retrieve from home store", func(): player_command({"action": "retrieve", "kind": action_value("stock_kind"), "amount": action_fields.stock_amount.value}))
    action_button(workshop, "Deposit in home store", func(): player_command({"action": "store", "kind": action_value("stock_kind"), "amount": action_fields.stock_amount.value}))
    var teach_row := action_row(workshop, "Teach skill / claim")
    var topic := LineEdit.new()
    topic.text = "gather"
    topic.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    teach_row.add_child(topic)
    action_fields.topic = topic
    action_button(workshop, "Teach selected nearby inhabitant", func(): player_command({"action": "teach", "target": selected, "topic": action_fields.topic.text.strip_edges()}))
    action_button(workshop, "Repair selected building (uses owned wood)", func(): player_command({"action": "repair", "building": selected}))
    var civic := VBoxContainer.new()
    civic.name = "Council"
    tabs.add_child(civic)
    action_note(civic, "Proposals enter the settlement's decision process; they are not immediate commands. Only council members can cast binding votes. Group projects need materials and work.")
    action_options(civic, "Policy", "policy", ["share_surplus", "rationing", "open_trade", "defense"])
    action_button(civic, "Submit policy proposal", func(): player_command({"action": "propose", "policy": action_value("policy")}))
    action_button(civic, "Propose building selected in main toolbar", func(): player_command({"action": "propose", "policy": "group_project", "kind": building_choice.get_item_text(building_choice.selected)}))
    action_options(civic, "Open proposal", "proposal", [])
    action_button(civic, "Vote to approve (council only)", func(): _proposal_vote(true))
    action_button(civic, "Vote to reject (council only)", func(): _proposal_vote(false))
    var build := VBoxContainer.new()
    build.name = "Build"
    tabs.add_child(build)
    action_note(build, "Uses the building kind selected in the main toolbar. Roads and bridges require a valid site, proximity and materials. Explicit placement is validated by the engine.")
    var use_site := CheckBox.new()
    use_site.text = "Use the explicit map tile below"
    build.add_child(use_site)
    action_fields.use_site = use_site
    action_amount(build, "Tile X", "site_x", 0, 200)
    action_amount(build, "Tile Y", "site_y", 0, 200)
    action_button(build, "Pick a tile on the map", func(): placing_site = true; actions_popup.hide(); status_label.text = "Click a map tile for the building site. Escape cancels.")
    action_button(build, "Start selected construction", _build_at_site)
    action_button(build, "Contribute work to selected project", func(): player_command({"action": "work", "building": selected}))
    action_button(build, "Repair selected building", func(): player_command({"action": "repair", "building": selected}))
    var life := VBoxContainer.new()
    life.name="Survival"
    tabs.add_child(life)
    action_note(life,"Select a deposit, animal, farm or fire in the world, then act nearby. Mining/fishing take repeated work ticks; crops, fuel and yields are real.")
    action_button(life,"Mine selected finite deposit",func(): player_command({"action":"mine","resource":selected}))
    action_button(life,"Fish selected habitat",func(): player_command({"action":"fish","resource":selected}))
    action_button(life,"Collect selected water reserve",func(): player_command({"action":"collect_water","resource":selected}))
    action_button(life,"Hunt selected wildlife (non-graphic)",func(): player_command({"action":"hunt","target":selected}))
    action_options(life,"Crop","crop",["wheat","vegetables"])
    action_button(life,"Plant at selected farm",func(): player_command({"action":"plant","building":selected,"crop":action_value("crop")}))
    action_button(life,"Harvest selected mature farm",func(): player_command({"action":"harvest","building":selected}))
    action_button(life,"Irrigate farm with two owned water",func(): player_command({"action":"irrigate","building":selected,"amount":2}))
    action_button(life,"Fuel selected hearth / campfire (one wood)",func(): player_command({"action":"fuel","building":selected,"kind":"wood","amount":1}))
    action_button(life,"Extinguish selected fire",func(): player_command({"action":"extinguish","building":selected}))
    var industry := VBoxContainer.new()
    industry.name="Industry"
    tabs.add_child(industry)
    action_note(industry,"Production reserves owned inputs and progresses while you remain near the required home facility. Leaving pauses the job. Cancel returns reserved inputs once.")
    action_options(industry,"Recipe","production",["planks","bricks","charcoal","smelt_iron","smelt_copper","smelt_gold","smelt_silver","bread","cook_meat","cook_fish","refined_tools","iron_blade","wool_coat","leather_coat"])
    action_button(industry,"Start / check timed production",func(): player_command({"action":"produce","recipe":action_value("production")}))
    action_button(industry,"Cancel production and reclaim inputs",func(): player_command({"action":"cancel_production"}))
    action_options(industry,"Repair equipment","equipment_repair",["staff","shield","padded_coat","iron_blade","wool_coat","leather_coat"])
    action_button(industry,"Repair using one tool at a workshop",func(): player_command({"action":"repair_equipment","item":action_value("equipment_repair")}))
    action_button(industry,"Repel selected nearby fantasy threat",func(): player_command({"action":"repel","target":selected}))
    action_button(industry,"Open selected home gate",func(): player_command({"action":"gate","building":selected,"open":true}))
    action_button(industry,"Close selected home gate",func(): player_command({"action":"gate","building":selected,"open":false}))
    var close := Button.new()
    close.name = "CloseActions"
    close.text = "Close"
    close.position = Vector2(0, 550)
    close.size = Vector2(588, 32)
    close.pressed.connect(func(): actions_popup.hide())
    frame.add_child(close)

func _open_actions() -> void:
    if not player_mode:
        status_label.text = "Switch to Player mode to act in the world."
        return
    _refresh_action_lists()
    actions_open = true
    actions_popup.popup_centered()

func _refresh_action_lists() -> void:
    var previous_agreement := agreement_ids[action_fields.agreement.selected] if action_fields.agreement.selected >= 0 and action_fields.agreement.selected < agreement_ids.size() else ""
    var previous_proposal := proposal_ids[action_fields.proposal.selected] if action_fields.proposal.selected >= 0 and action_fields.proposal.selected < proposal_ids.size() else ""
    agreement_ids.clear()
    action_fields.agreement.clear()
    for agreement in state.get("agreements", {}).values():
        if agreement.get("recipient") == "player" and agreement.get("state") == "proposed":
            agreement_ids.append(agreement.id)
            var name: String = str(state.agents.get(agreement.proposer, {}).get("name", agreement.proposer))
            action_fields.agreement.add_item("%s: %s %s for %s" % [name, agreement.amount, agreement.offered, agreement.wanted])
    if previous_agreement in agreement_ids: action_fields.agreement.select(agreement_ids.find(previous_agreement))
    proposal_ids.clear()
    action_fields.proposal.clear()
    var home: String = str(state.get("agents", {}).get("player", {}).get("home", "a"))
    for proposal in state.get("proposals", {}).values():
        if proposal.get("settlement") == home and proposal.get("state") == "open":
            proposal_ids.append(proposal.id)
            action_fields.proposal.add_item("%s: %s %s" % [proposal.id, proposal.policy, proposal.get("kind", "")])
    if previous_proposal in proposal_ids: action_fields.proposal.select(proposal_ids.find(previous_proposal))

func _agreement_action(action: String) -> void:
    var index: int = action_fields.agreement.selected
    if index < 0 or index >= agreement_ids.size():
        status_label.text = "No pending incoming offer is selected."
        return
    player_command({"action": action, "agreement": agreement_ids[index]})

func _proposal_vote(approve: bool) -> void:
    var index: int = action_fields.proposal.selected
    if index < 0 or index >= proposal_ids.size():
        status_label.text = "No open home-settlement proposal is selected."
        return
    player_command({"action": "vote", "proposal": proposal_ids[index], "approve": approve})

func _build_at_site() -> void:
    var command := {"action": "build", "kind": building_choice.get_item_text(building_choice.selected)}
    if action_fields.use_site.button_pressed:
        command.x = int(action_fields.site_x.value)
        command.y = int(action_fields.site_y.value)
    player_command(command)
