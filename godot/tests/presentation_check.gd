extends SceneTree
## A deliberately synthetic state exercises every procedural silhouette without an LLM.
const View = preload("res://world_view.gd")
const UIStyle = preload("res://ui_style.gd")
var view: Node2D

func _initialize() -> void:
    call_deferred("run")

func run() -> void:
    view = View.new()
    root.add_child(view)
    var terrain: Array = []
    var kinds := ["forest","plains","mountain","river","lake","farmland","road","bridge"]
    for y in range(24):
        var row: Array = []
        for x in range(32): row.append(kinds[x%kinds.size()])
        terrain.append(row)
    var state := {"tick":0,"width":32,"height":24,"season":"spring","terrain":terrain,
        "agents":{},"wildlife":{},"buildings":{},"resources":{},"settlements":{},"conflicts":{},"conversations":{},"shipments":{},"events":[]}
    var i := 0
    for kind in ["house","farm","storage","workshop","market","road","bridge","well","hall","watchtower"]:
        state.buildings[kind] = {"id":kind,"kind":kind,"home":"a","x":2+i*2,"y":3,"complete":true,"progress":20}
        i += 1
    state.buildings.site = {"id":"site","kind":"hall","home":"a","x":5,"y":7,"complete":false,"progress":8}
    for id in ["a0","b0","player","injured"]:
        state.agents[id] = {"id":id,"name":id,"home":"a" if id != "b0" else "b","x":3+state.agents.size()*4,"y":10,"hp":20 if id == "injured" else 100,"max_hp":100,"player":id=="player","incapacitated":id=="injured","occupation":"guard" if id=="a0" else "builder","activity":"build","inventory":{"wood":6}}
    for species in ["deer","boar"]:
        state.wildlife[species] = {"id":species,"x":8+state.wildlife.size()*4,"y":13,"species":species}
    state.threats={"z":{"id":"z","x":11,"y":15,"hp":35,"species":"zombie","activity":"pursue"}}
    state.conversations.d1 = {"id":"d1","participants":["a0","b0"],"state":"active"}
    state.shipments.s1 = {"id":"s1","state":"in_transit","courier":"player"}
    view.accept_state(state)
    await process_frame
    await process_frame
    assert(view.terrain_layer.redraw_count > 0)
    assert(view.conversation_agents.size() == 2)
    assert(view.cargo_agents.has("player"))
    view.selected="z"
    assert(view.selected_entity().species=="zombie","Flat fallback must render and select threats")
    var draws: int = view.terrain_layer.redraw_count
    view.accept_state(state)
    await process_frame
    assert(view.terrain_layer.redraw_count == draws, "Unchanged snapshots must reuse cached terrain")
    state.tick = 1
    state.events = [{"id":1,"kind":"built","actors":["a0"]}]
    view.accept_state(state)
    assert(view.effects.size() == 1)
    view.accept_state(state)
    assert(view.effects.size() == 1, "Polling must not replay old event effects")
    state.tick = 0
    view.accept_state(state)
    assert(view.effects.is_empty(), "Loading an earlier world clears transient feedback")
    var before: float = view.zoom
    view.zoom_at(1.4,Vector2(200,200))
    assert(view.zoom > before)
    view.selected = "player"
    view.focus_selected()
    assert(view.screen_point(state.agents.player).distance_to(view.view_size*.5) < .01)
    assert(UIStyle.safe("[url=bad]text") == "[lb]url=bad]text", "Speech must not inject UI markup")
    state.season = "winter"
    view.accept_state(state)
    await process_frame
    await process_frame
    assert(view.terrain_layer.redraw_count > draws)
    print("Presentation checks passed: 8 terrain types, 10 building types, construction, agents, wildlife, conversations, cargo, event deduplication, cache, camera, escaping")
    quit(0)
