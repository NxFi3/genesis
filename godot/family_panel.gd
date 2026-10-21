extends ScrollContainer
## Local family-tree inspection; portraits reflect persisted appearance only.
var content: VBoxContainer
var state: Dictionary={}
var identity := ""
var revision := ""
class Portrait extends Control:
    var traits: Dictionary={}
    func _draw() -> void:
        var skin:=Color("ebc9a3").lerp(Color("77513e"),float(traits.get("skin",.35)))
        draw_circle(Vector2(24,27),17,skin)
        draw_arc(Vector2(24,24),17,PI,TAU,20,Color(str(traits.get("hair","#68503d"))),10,true)
        for x in [18,30]:draw_circle(Vector2(x,27),2,Color(str(traits.get("eyes","#574337"))))
func _ready() -> void:
    content=VBoxContainer.new()
    content.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    add_child(content)
func update_world(value: Dictionary, selected: String) -> void:
    state=value
    if identity!=selected:identity=selected
    rebuild()
func person(key: String) -> Dictionary:
    return state.get("agents",{}).get(key,state.get("family_archive",{}).get(key,{}))
func show_person(key: String) -> void:
    identity=key
    revision=""
    rebuild()
func rebuild() -> void:
    var p:=person(identity)
    var next:=JSON.stringify([identity,p,state.get("family_archive",{}).size(),state.get("agents",{}).size()])
    if content==null or next==revision:return
    revision=next
    for node in content.get_children():content.remove_child(node);node.queue_free()
    if p.is_empty():return
    add_person(identity,"Selected")
    var home: Dictionary=state.get("households",{}).get(p.get("household",""),{})
    text("Household: "+str(home.get("id","Historical record")))
    text("Residence: "+str(home.get("residence","—")))
    for relation in ["parents","children"]:
        text(str(relation).capitalize())
        for key in p.get(relation,[]):add_person(key,relation.trim_suffix("s"))
    if p.get("partner")!=null:add_person(p.partner,"Partner")
    text("Siblings")
    var all: Dictionary=state.get("family_archive",{}).duplicate()
    all.merge(state.get("agents",{}))
    for key in all:
        if key==identity:continue
        for parent in p.get("parents",[]):
            if parent in all[key].get("parents",[]):add_person(key,"Sibling");break
    text("Life events")
    for event in p.get("family_history",[]).slice(-8):text("%d · %s" % [event.tick,event.text])
func text(value: String) -> void:
    var label:=Label.new()
    label.text=value
    label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
    label.custom_minimum_size.x=300
    content.add_child(label)
func add_person(key: String, relation: String) -> void:
    var p:=person(key)
    if p.is_empty():return
    var row:=HBoxContainer.new()
    var portrait:=Portrait.new()
    portrait.traits=p.get("appearance",{})
    portrait.custom_minimum_size=Vector2(50,52)
    row.add_child(portrait)
    var link:=Button.new()
    link.text="%s · %s\n%s · age %.1f%s" % [relation,p.get("name",key),p.get("life_stage","adult"),p.get("age",0)," · deceased" if p.has("death_tick") else ""]
    link.pressed.connect(func():show_person(key))
    row.add_child(link)
    content.add_child(row)
