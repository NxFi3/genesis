extends Node2D
## Orthographic presentation of authoritative simulation X/Y as world X/Z.
const Art = preload("res://art/low_poly.gd")
const Palette = preload("res://terrain_view.gd")
const TILE := 24.0 # Compatibility for the retained top-down fallback only.
var state: Dictionary = {}
var selected := "a0"
var follow_agent := false
var view_size := Vector2(864,516)
var labels_visible := true
var details_visible := true
var zoom := 1.0
var viewport_3d: SubViewport
var scene: Node3D
var camera: Camera3D
var ground: Node3D
var structures: Node3D
var people: Node3D
var foliage: Node3D
var terrain_layer: Node2D # Exposes retained-layer count to the existing smoke checks.
var terrain_revision := 0
var terrain_hash := 0
var building_hash := 0
var models: Dictionary = {}
var appearances: Dictionary = {}
var positions: Dictionary = {}
var center := Vector3(24,0,15)
var base_size := 42.0
var clock := 0.0
var conversation_agents: Dictionary = {}
var cargo_agents: Dictionary = {}
var batches: Dictionary = {}
var heights: Array = []
var sunlight: DirectionalLight3D
var environment: Environment

func _ready() -> void:
    viewport_3d = SubViewport.new()
    viewport_3d.size = Vector2i(view_size)
    viewport_3d.own_world_3d = true
    viewport_3d.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport_3d.msaa_3d = Viewport.MSAA_2X
    add_child(viewport_3d)
    scene = Node3D.new()
    viewport_3d.add_child(scene)
    ground = Node3D.new()
    structures = Node3D.new()
    people = Node3D.new()
    foliage = Node3D.new()
    for node in [ground,structures,people,foliage]: scene.add_child(node)
    var sky := WorldEnvironment.new()
    environment = Environment.new()
    environment.background_mode = Environment.BG_COLOR
    environment.background_color = Color("a4b8b7")
    environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    environment.ambient_light_color = Color("b6c2bb")
    environment.ambient_light_energy = .7
    sky.environment = environment
    scene.add_child(sky)
    sunlight = DirectionalLight3D.new()
    sunlight.rotation_degrees = Vector3(-50,-35,0)
    sunlight.light_color = Color("fff0cb")
    sunlight.light_energy = 1.1
    sunlight.shadow_enabled = true
    sunlight.directional_shadow_max_distance = 100
    scene.add_child(sunlight)
    camera = Camera3D.new()
    camera.projection = Camera3D.PROJECTION_ORTHOGONAL
    camera.far = 200
    scene.add_child(camera)
    _camera()

func _camera() -> void:
    if camera == null: return
    camera.size = base_size/zoom
    camera.position = center+Vector3(38,38,38)
    camera.look_at(center,Vector3.UP)

func height_at(x: float, y: float) -> float:
    if state.is_empty(): return 0
    if heights.is_empty(): return 0
    var fx := clampf(x,0,int(state.width)-1)
    var fy := clampf(y,0,int(state.height)-1)
    var ix := floori(fx)
    var iy := floori(fy)
    var nx := mini(ix+1,int(state.width)-1)
    var ny := mini(iy+1,int(state.height)-1)
    return lerpf(lerpf(heights[iy][ix],heights[iy][nx],fx-ix),lerpf(heights[ny][ix],heights[ny][nx],fx-ix),fy-iy)

func accept_state(value: Dictionary) -> void:
    var first := state.is_empty()
    state = value
    var next := hash([state.terrain,state.get("elevation",[]),state.get("season","spring")])
    if next != terrain_hash:
        terrain_hash = next
        heights.clear()
        for y in range(state.height):
            var row: Array = []
            for x in range(state.width):
                var kind: String = state.terrain[y][x]
                var h: float = float(state.elevation[y][x]) if state.has("elevation") else .13+.13*sin(x*.28)*cos(y*.34)+(maxf(0,(x-float(state.width)*.72))*.13 if kind=="mountain" else 0)
                row.append(-.1 if kind in ["river","lake"] else h)
            heights.append(row)
        _terrain()
    var visuals: Array = []
    for b in state.buildings.values(): visuals.append([b.id,b.kind,b.complete,b.get("condition",100)])
    next = hash(visuals)
    if next != building_hash:
        building_hash = next
        _buildings()
    conversation_agents.clear()
    cargo_agents.clear()
    for c in state.get("conversations",{}).values():
        if c.state == "active":
            for id in c.participants: conversation_agents[id] = true
    for s in state.get("shipments",{}).values():
        if s.state in ["in_transit","returning"]: cargo_agents[s.courier] = true
    _entities()
    if first: reset_camera()

func _clear(node: Node) -> void:
    for child in node.get_children():
        node.remove_child(child)
        child.queue_free()

func _terrain() -> void:
    _clear(ground)
    _clear(foliage)
    batches.clear()
    var surfaces: Dictionary = {}
    for y in range(state.height):
        for x in range(state.width):
            var kind: String = state.terrain[y][x]
            if not surfaces.has(kind):
                var surface := SurfaceTool.new()
                surface.begin(Mesh.PRIMITIVE_TRIANGLES)
                surfaces[kind] = surface
            var st: SurfaceTool = surfaces[kind]
            var color: Color = Palette.COLORS.get(kind,Color("8c9c70"))
            color = color.lightened(float((x*37+y*13)%11)*.005)
            if state.season == "winter" and kind not in ["river","lake"]: color = color.lerp(Color("d3dbcd"),.58)
            if state.season == "autumn" and kind in ["plains","forest"]: color = color.lerp(Color("bb9d68"),.25)
            var corners: Array[Vector3] = []
            for corner in [Vector2(-.5,-.5),Vector2(.5,-.5),Vector2(.5,.5),Vector2(-.5,.5)]:
                var h := height_at(x+corner.x,y+corner.y)
                if kind in ["river","lake"]: h = -.1
                corners.append(Vector3(x+corner.x,h,y+corner.y))
            for i in [0,2,1,0,3,2]:
                st.set_color(color)
                st.add_vertex(corners[i])
            if kind == "forest" and (x*17+y*13)%4 != 0:
                var tree := Art.tree(x+y*state.width)
                _batch(tree,Vector3(x,height_at(x,y),y),float(x%6)*.8)
                tree.free()
            elif kind == "mountain" and (x+y)%4 == 0:
                var rock := Node3D.new()
                Art.part(rock,"sphere",Vector3(0,.3,0),Vector3(.8,.8,1.0),Color("929990"))
                _batch(rock,Vector3(x,height_at(x,y),y),x*.3)
                rock.free()
            elif kind == "farmland" and (x+y)%2 == 0:
                var patch := Node3D.new()
                for z in [-.25,0,.25]: Art.part(patch,"box",Vector3(0,.025,z),Vector3(.8,.05,.05),Color("9e8956"))
                _batch(patch,Vector3(x,height_at(x,y),y),0)
                patch.free()
    for kind in surfaces:
        var st: SurfaceTool = surfaces[kind]
        st.generate_normals()
        var instance := MeshInstance3D.new()
        instance.mesh = st.commit()
        var material := StandardMaterial3D.new()
        material.vertex_color_use_as_albedo = true
        material.cull_mode = BaseMaterial3D.CULL_DISABLED
        material.roughness = .95
        instance.material_override = material
        ground.add_child(instance)
    for data in batches.values():
        var instance := MultiMeshInstance3D.new()
        var multi := MultiMesh.new()
        multi.transform_format = MultiMesh.TRANSFORM_3D
        multi.mesh = data.mesh
        multi.instance_count = data.transforms.size()
        for i in range(data.transforms.size()): multi.set_instance_transform(i,data.transforms[i])
        instance.multimesh = multi
        instance.material_override = data.material
        foliage.add_child(instance)
    batches.clear()
    # A dark soil skirt gives the diorama a physical edge.
    Art.part(ground,"box",Vector3(float(state.width-1)/2,-.5,float(state.height-1)/2),Vector3(state.width, .75, state.height),Color("635f49"))
    terrain_revision += 1

func _batch(prototype: Node3D, at: Vector3, yaw: float) -> void:
    var base := Transform3D(Basis(Vector3.UP,yaw),at)
    for child in prototype.get_children():
        if child is MeshInstance3D:
            var key := str(child.mesh.get_instance_id())+":"+str(child.material_override.get_instance_id())
            if not batches.has(key): batches[key] = {"mesh":child.mesh,"material":child.material_override,"transforms":[]}
            batches[key].transforms.append(base*child.transform)

func _buildings() -> void:
    _clear(structures)
    for b in state.buildings.values():
        var color := Color("7ec4a2") if b.home == "a" else Color("91b9d6")
        var model := Art.building(b.kind,b.complete,color)
        model.name = b.id
        model.position = Vector3(b.x,height_at(b.x,b.y),b.y)
        # Legacy saves place house and storage on the same tile; separate display footprints only.
        if b.kind == "storage" and state.buildings.values().any(func(other): return other.id != b.id and other.x == b.x and other.y == b.y): model.position.x += .65
        structures.add_child(model)

func _entities() -> void:
    var living: Dictionary = {}
    for category in ["agents","wildlife","threats"]:
        for a in state.get(category,{}).values():
            living[a.id] = true
            var appearance := [category,a.get("occupation",""),a.get("species",""),a.get("home",""),a.get("player",false)]
            if models.has(a.id) and appearances[a.id] != appearance:
                models[a.id].queue_free()
                models.erase(a.id)
            if not models.has(a.id):
                var color := Color("7ec4a2") if a.get("home","") == "a" else Color("91b9d6")
                var model: Node3D = Art.human(color,a.get("occupation",""),a.get("player",false)) if category == "agents" else Art.animal(a.get("species","wolf"))
                model.name = a.id
                people.add_child(model)
                models[a.id] = model
                appearances[a.id] = appearance
                positions[a.id] = Vector3(a.x,height_at(a.x,a.y),a.y)
    for id in models.keys():
        if not living.has(id):
            models[id].queue_free()
            models.erase(id)
            positions.erase(id)
            appearances.erase(id)

func _process(delta: float) -> void:
    clock += delta
    if state.is_empty(): return
    for category in ["agents","wildlife","threats"]:
        for a in state.get(category,{}).values():
            if not models.has(a.id): continue
            var target := Vector3(a.x,height_at(a.x,a.y),a.y)
            var current: Vector3 = positions.get(a.id,target)
            var motion := target-current
            var shown := target if motion.length() > 5 else current.lerp(target,1-exp(-delta*10))
            positions[a.id] = shown
            var model: Node3D = models[a.id]
            model.position = shown
            if Vector2(motion.x,motion.z).length() > .02: model.rotation.y = atan2(motion.x,motion.z)+PI
            var down: bool = a.get("incapacitated",false) or a.get("activity","") in ["sleep","rest","incapacitated"]
            model.rotation.z = PI*.48 if down else 0.0
            if category == "agents":
                var working: bool = a.get("activity","") in ["build","work","gather","mine","craft","hunt","defend","fight"]
                var walking := Vector2(motion.x,motion.z).length() > .02
                for side in ["L","R"]:
                    var sign_value := 1 if side == "L" else -1
                    model.get_node("Leg"+side).rotation.x = sin(clock*10)*.55*sign_value if walking and not down else 0.0
                    model.get_node("Arm"+side).rotation.x = sin(clock*8)*.75 if working else sin(clock*10)*.4*-sign_value if walking and not down else 0.0
    if follow_agent:
        var entity := selected_entity()
        if not entity.is_empty(): center = center.lerp(Vector3(entity.x,height_at(entity.x,entity.y),entity.y),1-exp(-delta*5))
    _camera()
    sunlight.light_energy = .65 if not state.get("daylight",true) else 1.1
    queue_redraw()

func selected_entity() -> Dictionary:
    for category in ["agents","settlements","buildings","resources","wildlife","threats"]:
        if state.get(category,{}).has(selected): return state[category][selected]
    return {}

func screen_point(entity: Dictionary) -> Vector2:
    var p: Vector3 = positions.get(entity.id,Vector3(entity.x,height_at(entity.x,entity.y),entity.y))
    return camera.unproject_position(p+Vector3(0,.45,0))

func screen_to_tile(point: Vector2) -> Vector2:
    var origin := camera.project_ray_origin(point)
    var ray := camera.project_ray_normal(point)
    var at := Vector3.ZERO
    var h := 0.0
    for i in range(5):
        var hit: Variant = Plane(Vector3.UP,h).intersects_ray(origin,ray)
        if hit == null: return Vector2(-1,-1)
        at = hit
        h = height_at(at.x,at.z)
    return Vector2(at.x,at.z)

func pan(pixels: Vector2) -> void:
    follow_agent = false
    var before := screen_to_tile(view_size*.5)
    var after := screen_to_tile(view_size*.5+pixels)
    center += Vector3(before.x-after.x,0,before.y-after.y)
    center.x = clampf(center.x,-5,state.get("width",48)+5)
    center.z = clampf(center.z,-5,state.get("height",30)+5)
    _camera()

func zoom_at(factor: float, point: Vector2) -> void:
    var before := screen_to_tile(point)
    zoom = clampf(zoom*factor,.5,6)
    _camera()
    var after := screen_to_tile(point)
    center += Vector3(before.x-after.x,0,before.y-after.y)
    follow_agent = false
    _camera()

func reset_camera() -> void:
    center = Vector3(float(state.get("width",48)-1)/2,0,float(state.get("height",30)-1)/2)
    base_size = maxf(state.get("width",48)*.82,state.get("height",30)*1.25)
    zoom = 1
    follow_agent = false
    _camera()

func focus_selected() -> void:
    var entity := selected_entity()
    if entity.is_empty(): return
    center = Vector3(entity.x,height_at(entity.x,entity.y),entity.y)
    zoom = maxf(zoom,2.1)
    _camera()

func tag(at: Vector2, text: String, color := Color("f2e5c4"), font_size := 13) -> void:
    if at.x < 0 or at.y < 0 or at.x > view_size.x or at.y > view_size.y: return
    var font := ThemeDB.fallback_font
    var size := font.get_string_size(text,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size)
    at.x = clampf(at.x-size.x*.5,5,maxf(5,view_size.x-size.x-5))
    draw_rect(Rect2(at+Vector2(-4,-font_size),size+Vector2(8,4)),Color(.08,.14,.12,.87))
    draw_string(font,at,text,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size,color)

func _draw() -> void:
    if viewport_3d == null or state.is_empty(): return
    draw_texture_rect(viewport_3d.get_texture(),Rect2(Vector2.ZERO,view_size),false)
    if labels_visible:
        for s in state.settlements.values(): tag(screen_point(s)+Vector2(0,-50*zoom),s.name,Color("d7e2c0"),14)
    var entity := selected_entity()
    if not entity.is_empty():
        var p := screen_point(entity)
        draw_arc(p,11,0,TAU,24,Color("ffe0a0"),2,true)
        tag(p+Vector2(0,30),str(entity.get("name",entity.get("kind",entity.get("species",selected))))+" · "+str(entity.get("activity","")))
    if details_visible:
        for a in state.agents.values():
            var p := screen_point(a)
            if conversation_agents.has(a.id): tag(p+Vector2(0,-19),"···",Color("dbead0"),14)
            if a.hp < a.max_hp:
                draw_rect(Rect2(p+Vector2(-8,-14),Vector2(16,3)),Color("3c4941"))
                draw_rect(Rect2(p+Vector2(-8,-14),Vector2(16*float(a.hp)/a.max_hp,3)),Color("d5b873"))
            if cargo_agents.has(a.id): tag(p+Vector2(12,0),"▣",Color("dab788"),12)
        for b in state.buildings.values():
            if not b.complete and zoom > 1.1: tag(screen_point(b)+Vector2(0,-14),"Building · %.0f" % b.progress,Color("e6c384"),11)
    var weather: String = state.get("weather","clear")
    if weather in ["rain","heavy_rain","thunderstorm"]:
        for i in range(54):
            var p := Vector2(fposmod(i*173+clock*60,view_size.x),fposmod(i*79+clock*180,view_size.y))
            draw_line(p,p+Vector2(-3,9),Color(.7,.84,.88,.35),1)
    elif weather in ["snow","blizzard"]:
        for i in range(48): draw_circle(Vector2(fposmod(i*137+clock*18,view_size.x),fposmod(i*73+clock*35,view_size.y)),1.4,Color(.95,.98,1,.65))
    if weather in ["fog","blizzard"]: draw_rect(Rect2(Vector2.ZERO,view_size),Color(.8,.85,.83,.18))
