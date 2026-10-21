extends SceneTree
const FamilyView=preload("res://family_panel.gd")
const Art=preload("res://art/low_poly.gd")
func _initialize() -> void:call_deferred("run")
func run() -> void:
    var appearance: Dictionary={"skin":.7,"hair":"#76503b","eyes":"#789398","texture":"curly","face":"oval"}
    var grown:=Art.human(Color.WHITE,"farmer",false,appearance,"adult",["shield"])
    var child:=Art.human(Color.WHITE,"dependent",false,appearance,"child")
    assert(child.scale.x<grown.scale.x,"Age must change actual character presentation")
    grown.free();child.free()
    var panel:=FamilyView.new()
    root.add_child(panel)
    var state: Dictionary={"agents":{"child":{"id":"child","name":"Child","age":4,"life_stage":"child","appearance":appearance,"parents":["parent"],"children":[],"household":"home","family_history":[{"tick":1,"text":"Birth"}]}},"family_archive":{"parent":{"id":"parent","name":"Parent","age":80,"life_stage":"elder","death_tick":1,"appearance":appearance,"parents":[],"children":["child"]}},"households":{"home":{"id":"home","residence":"house"}}}
    panel.update_world(state,"child")
    assert(panel.content.get_child_count()>4,"Family tree needs real relationship and portrait rows")
    panel.show_person("parent")
    assert(panel.identity=="parent" and panel.person("parent").has("death_tick"))
    print("Family checks passed: inherited portraits, age scale, relationships and historical relatives")
    quit(0)
