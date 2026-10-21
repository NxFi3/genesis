extends SceneTree
const WorldControls = preload("res://environment_panel.gd")
var sent: Array=[]
func _initialize() -> void:
    call_deferred("run")
func run() -> void:
    var panel := WorldControls.new()
    root.add_child(panel)
    panel.command_requested.connect(func(command):sent.append(command))
    panel.update_world({"tick":4,"width":48,"height":30,"settlements":{},"climate":{"threats_enabled":false,"threat_settings":{"intensity":.5,"max_zombies":2,"spawn_interval":240,"grace_ticks":600,"night_only":true,"wolf_aggression":.2,"spawn_regions":[[1,1,8,3]]}}})
    assert(not panel.fields.threats.button_pressed)
    assert(panel.fields.threat_intensity.value==.5 and panel.fields.threat_cap.value==2)
    assert(panel.fields.threat_region.selected==1)
    panel.fields.threat_intensity.value=.75
    panel.apply_threats()
    assert(sent.size()==1 and sent[0].operation=="threats")
    assert(sent[0].settings.intensity==.75 and sent[0].settings.spawn_regions==[[1,1,8,3]])
    panel.fields.threats.button_pressed=true
    assert(sent[-1].enabled==true)
    panel.fields.threats.button_pressed=false
    assert(sent[-1].enabled==false,"Zombies need an explicit off control")
    print("Threat controls passed: saved balance, spawn region, validated command mapping and zombie off switch")
    quit(0)
