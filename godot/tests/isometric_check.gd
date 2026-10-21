extends SceneTree
const View = preload("res://world_3d.gd")
const Art = preload("res://art/low_poly.gd")
func _initialize() -> void:
    call_deferred("run")
func run() -> void:
    var view := View.new()
    root.add_child(view)
    var terrain: Array = []
    for y in range(24):
        var row: Array = []
        for x in range(32): row.append("forest" if x%3==0 else "river" if x==16 else "plains")
        terrain.append(row)
    var state := {"width":32,"height":24,"terrain":terrain,"season":"spring","agents":{},"buildings":{},"wildlife":{},"resources":{},"settlements":{"a":{"id":"a","name":"Test town","x":8,"y":8}},"tick":0}
    view.accept_state(state)
    assert(view.camera.projection==Camera3D.PROJECTION_ORTHOGONAL)
    assert(view.terrain_revision==1)
    assert(view.foliage.get_child_count()<100,"Vegetation must use shared MultiMesh batches")
    view.selected="a"
    view.focus_selected()
    var projected := view.screen_point(state.settlements.a)
    var tile := view.screen_to_tile(projected)
    assert(tile.distance_to(Vector2(8,8))<.7,"Projection must select the authoritative tile")
    var before: float=view.zoom
    view.zoom_at(1.2,Vector2(200,200))
    assert(view.zoom>before)
    view.pan(Vector2(20,10))
    view.accept_state(state)
    assert(view.terrain_revision==1,"Polling must reuse static landscape")
    state.settlements.b={"id":"b","name":"Other town","x":25,"y":18}
    state.environment={"a":{"weather":"rain","precipitation":.55,"moisture":.9},"b":{"weather":"clear","precipitation":0.,"moisture":.5}}
    view.accept_state(state)
    assert(view.climate_at(Vector2(8,8)).weather=="rain")
    assert(view.climate_at(Vector2(25,18)).weather=="clear")
    state.climate={"overrides":{"region":{"weather":"drought","bounds":[5,5,10,10],"expires":10}},"regions":{"region":{"moisture":.2}}}
    view.accept_state(state)
    assert(view.climate_at(Vector2(8,8)).drought==1.)
    assert(view.climate_at(Vector2(25,18)).weather=="clear")
    for kind in ["house","farm","storage","workshop","market","road","bridge","well","hall","watchtower","barn","warehouse","mine","furnace","blacksmith","carpenter","rain_collector","campfire","hearth","wall","gate"]:
        var asset := Art.building(kind,true,Color.WHITE)
        assert(asset.get_child_count()>0,"Every supported building requires usable geometry")
        asset.free()
    for occupation in ["guard","farmer","builder","miner","trader","craftsperson"]:
        var asset := Art.human(Color.WHITE,occupation,false)
        assert(asset.has_node("LegL") and asset.has_node("ArmR"))
        asset.free()
    print("Isometric checks passed: orthographic scene, batched landscape, projected picking, camera, retained geometry, local climate, 21 building assets and animated role figures")
    quit(0)
