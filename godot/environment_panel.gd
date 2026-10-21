extends PopupPanel
## Explicit observer controls; no God Mode commands are exposed to NPC plans.
signal command_requested(command: Dictionary)
const Style = preload("res://ui_style.gd")
var fields: Dictionary = {}
var readings: RichTextLabel
var state: Dictionary = {}
var region_ids := ["world","a","b","region"]

func _ready() -> void:
    size = Vector2i(760,730)
    var frame := VBoxContainer.new()
    frame.add_theme_constant_override("separation",8)
    add_child(frame)
    var heading := Label.new()
    heading.text = "GOD MODE  /  Environment & world"
    heading.add_theme_font_size_override("font_size",22)
    frame.add_child(heading)
    var tabs := TabContainer.new()
    tabs.custom_minimum_size = Vector2(728,600)
    tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
    frame.add_child(tabs)
    var weather := column(tabs,"Climate")
    note(weather,"Interventions change real conditions, persist in saves and enter world history.")
    options(weather,"Apply to","region",["Entire world","Willowmere","Stonehaven","Rectangle below"])
    options(weather,"Weather","weather",["clear","rain","heavy_rain","snow","blizzard","thunderstorm","fog","wind","heatwave","cold_snap","drought"])
    amount(weather,"Duration (ticks)","duration",1,10000,240,1)
    var custom := CheckBox.new()
    custom.text = "Use custom temperature and intensities below"
    fields.custom = custom
    weather.add_child(custom)
    amount(weather,"Temperature (game °C)","temperature",-40,50,15,1)
    amount(weather,"Rainfall","precipitation",0,1,.5,.05)
    amount(weather,"Wind","wind",0,1,.3,.05)
    amount(weather,"Snow","snow",0,1,0,.05)
    amount(weather,"Drought severity","drought",0,1,0,.05)
    var bounds := HBoxContainer.new()
    weather.add_child(bounds)
    for key in ["x0","y0","x1","y1"]:
        var field := SpinBox.new()
        field.prefix=key+" "
        field.min_value=0;field.max_value=200;field.step=1;field.value=15 if key.ends_with("1") else 0
        field.size_flags_horizontal=Control.SIZE_EXPAND_FILL
        fields[key]=field
        bounds.add_child(field)
    action(weather,"Apply weather to selected region",apply_weather)
    action(weather,"Return this region to natural weather",func(): emit_command("natural",true))
    var world := column(tabs,"World")
    amount(world,"Time of day","hour",0,23.9,12,.1)
    action(world,"Set time",func(): emit_command("time",false,{"hour":fields.hour.value}))
    options(world,"Season","season",["spring","summer","autumn","winter"])
    action(world,"Set season",func(): emit_command("season",false,{"season":option("season")}))
    amount(world,"Ticks per second","speed",.25,20,2,.25)
    action(world,"Set simulation speed",func(): emit_command("speed",false,{"value":fields.speed.value}))
    action(world,"Pause world",func(): emit_command("pause",false,{"paused":true}))
    action(world,"Resume world",func(): emit_command("pause",false,{"paused":false}))
    amount(world,"Difficulty","difficulty",.25,2,1,.25)
    action(world,"Set environmental difficulty",func(): emit_command("difficulty",false,{"value":fields.difficulty.value}))
    action(world,"Replenish 25% of regional deposits",func(): emit_command("replenish",true,{"fraction":.25}))
    options(world,"Wildlife","species",["deer","boar","wolf","sheep"])
    var spawn := HBoxContainer.new()
    world.add_child(spawn)
    for key in ["spawn_x","spawn_y"]:
        var field := SpinBox.new()
        field.prefix="X " if key=="spawn_x" else "Y "
        field.min_value=0;field.max_value=200;field.step=1;field.value=10
        fields[key]=field
        spawn.add_child(field)
    action(world,"Spawn wildlife at this tile",func(): emit_command("spawn",false,{"species":option("species"),"x":fields.spawn_x.value,"y":fields.spawn_y.value}))
    var threats := CheckBox.new()
    threats.text="Enable bounded optional fantasy threats"
    threats.toggled.connect(func(value): emit_command("threats",false,{"enabled":value}))
    fields.threats=threats
    world.add_child(threats)
    action(world,"Return all climate and clock controls to nature",func(): command_requested.emit({"action":"god","operation":"natural","region":"world"}))
    readings = RichTextLabel.new()
    readings.name="Observations"
    readings.bbcode_enabled=true
    readings.selection_enabled=true
    tabs.add_child(readings)
    var close := Button.new()
    close.text="Return to the living world"
    close.pressed.connect(hide)
    frame.add_child(close)

func column(tabs: TabContainer, title: String) -> VBoxContainer:
    var scroll := ScrollContainer.new()
    scroll.name=title
    tabs.add_child(scroll)
    var box := VBoxContainer.new()
    box.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    box.add_theme_constant_override("separation",5)
    scroll.add_child(box)
    return box

func row(box: VBoxContainer, caption: String) -> HBoxContainer:
    var line := HBoxContainer.new()
    var label := Label.new()
    label.text=caption;label.custom_minimum_size.x=225
    line.add_child(label)
    box.add_child(line)
    return line

func note(box: VBoxContainer, text: String) -> void:
    var label := Label.new()
    label.text=text
    label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
    label.custom_minimum_size.x=660
    box.add_child(label)

func options(box: VBoxContainer, caption: String, key: String, values: Array) -> void:
    var field := OptionButton.new()
    field.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    for value in values: field.add_item(value)
    fields[key]=field
    row(box,caption).add_child(field)

func amount(box: VBoxContainer, caption: String, key: String, low: float, high: float, value: float, step: float) -> void:
    var field := SpinBox.new()
    field.min_value=low;field.max_value=high;field.step=step;field.value=value
    field.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    fields[key]=field
    row(box,caption).add_child(field)

func action(box: VBoxContainer, text: String, callback: Callable) -> void:
    var button := Button.new()
    button.text=text
    button.pressed.connect(callback)
    box.add_child(button)

func option(key: String) -> String:
    return fields[key].get_item_text(fields[key].selected)

func emit_command(operation: String, regional := false, extra: Dictionary = {}) -> void:
    var command := {"action":"god","operation":operation,"region":region_ids[fields.region.selected] if regional else "world"}
    if command.region=="region": command.bounds=[fields.x0.value,fields.y0.value,fields.x1.value,fields.y1.value]
    command.merge(extra)
    command_requested.emit(command)

func apply_weather() -> void:
    var values := {"weather":option("weather"),"duration":int(fields.duration.value)}
    if fields.custom.button_pressed:
        for key in ["temperature","precipitation","wind","snow","drought"]:values[key]=fields[key].value
    emit_command("weather",true,values)

func update_world(value: Dictionary) -> void:
    state=value
    var text := Style.heading("REGIONAL ENVIRONMENT")
    for sid in state.get("environment",{}):
        var env: Dictionary=state.environment[sid]
        text+=Style.heading(str(state.settlements.get(sid,{}).get("name",sid)))
        text+="%s · %.1f °C\nRain %.0f%% · Snow %.0f%% · Wind %.0f%%\nSoil moisture %.0f%% · Fertility %.0f%%\nDrought %.0f%% · Environmental reserves %.1f water\n\n" % [str(env.weather).capitalize(),env.temperature,env.precipitation*100,env.snow*100,env.wind*100,env.moisture*100,env.fertility*100,env.drought*100,env.get("water_reserve",0)]
    text+=Style.heading("ACTIVE INTERVENTIONS")
    for scope in state.get("climate",{}).get("overrides",{}):
        var effect: Dictionary=state.climate.overrides[scope]
        text+="%s · %s · %d ticks remaining\n" % [scope,effect.weather,maxi(0,int(effect.expires)-int(state.tick))]
    text+="\n"+Style.heading("PRODUCTION & CROPS")
    for job in state.get("production_jobs",{}).values():
        if job.state=="working":text+="%s · %s · %.0f / %.0f work\n" % [job.actor,job.recipe,job.progress,job.duration]
    for crop in state.get("crops",{}).values():text+="%s · %s · %s · %.0f growth\n" % [crop.building,crop.kind,crop.stage,crop.growth]
    readings.text=text
    for pair in [["x0",state.get("width",48)-1],["x1",state.get("width",48)-1],["y0",state.get("height",30)-1],["y1",state.get("height",30)-1],["spawn_x",state.get("width",48)-1],["spawn_y",state.get("height",30)-1]]:
        fields[pair[0]].max_value=pair[1]
    fields.threats.set_pressed_no_signal(state.get("climate",{}).get("threats_enabled",false))
