extends RefCounted
## Original reusable procedural assets. Shared meshes/materials; no imported art.
static var materials: Dictionary = {}
static var meshes: Dictionary = {}

static func material(color: Color) -> StandardMaterial3D:
    var key := color.to_html()
    if not materials.has(key):
        var m := StandardMaterial3D.new()
        m.albedo_color = color
        m.roughness = .95
        materials[key] = m
    return materials[key]

static func part(parent: Node3D, shape: String, position: Vector3, scale: Vector3, color: Color) -> MeshInstance3D:
    if not meshes.has(shape):
        var mesh: PrimitiveMesh
        match shape:
            "sphere":
                mesh = SphereMesh.new()
                mesh.radial_segments = 8
                mesh.rings = 4
                mesh.height = 1
                mesh.radius = .5
            "cone":
                mesh = CylinderMesh.new()
                mesh.top_radius = 0
                mesh.bottom_radius = .5
                mesh.height = 1
                mesh.radial_segments = 6
            "cylinder":
                mesh = CylinderMesh.new()
                mesh.top_radius = .5
                mesh.bottom_radius = .5
                mesh.height = 1
                mesh.radial_segments = 8
            _:
                mesh = BoxMesh.new()
        meshes[shape] = mesh
    var instance := MeshInstance3D.new()
    instance.mesh = meshes[shape]
    instance.material_override = material(color)
    instance.position = position
    instance.scale = scale
    parent.add_child(instance)
    return instance

static func roof(parent: Node3D, y: float, width: float, depth: float, color: Color) -> void:
    for sign_value in [-1,1]:
        var slope := part(parent,"box",Vector3(sign_value*width*.24,y,0),Vector3(width*.64,.10,depth),color)
        slope.rotation.z = sign_value*-.63

static func tree(seed_value: int) -> Node3D:
    var root := Node3D.new()
    var height := 1.2+float(absi(seed_value)%7)*.10
    part(root,"cylinder",Vector3(0,height*.28,0),Vector3(.17,height*.55,.17),Color("786045"))
    if seed_value%3 == 0:
        part(root,"cone",Vector3(0,height*.72,0),Vector3(.95,height,.95),Color("43694e"))
        part(root,"cone",Vector3(0,height,0),Vector3(.72,height*.7,.72),Color("5a8155"))
    else:
        part(root,"sphere",Vector3(0,height*.8,0),Vector3(1.15,height*.82,1.05),Color("648659") if seed_value%2 else Color("78975f"))
        part(root,"sphere",Vector3(.3,height*.98,.1),Vector3(.6,.7,.7),Color("89a369"))
    return root

static func building(kind: String, complete: bool, faction: Color) -> Node3D:
    var root := Node3D.new()
    var timber := Color("735442")
    var stone := Color("a8a99c")
    var plaster := Color("e0d3ae")
    if not complete:
        part(root,"box",Vector3(0,.06,0),Vector3(1.05,.12,.9),Color("8a7757"))
        for x in [-.45,.45]:
            for z in [-.35,.35]: part(root,"box",Vector3(x,.55,z),Vector3(.06,1.1,.06),timber)
        for y in [.35,.8]: part(root,"box",Vector3(0,y,-.35),Vector3(1,.06,.06),Color("d1b280"))
        var brace := part(root,"box",Vector3(0,.5,-.35),Vector3(.05,1.1,.05),timber)
        brace.rotation.z = .8
        return root
    match kind:
        "road":
            part(root,"box",Vector3(0,.025,0),Vector3(.95,.05,.95),Color("bfae8e"))
        "bridge":
            for x in range(7): part(root,"box",Vector3(-.45+x*.15,.14,0),Vector3(.13,.12,1.0),Color("b39162"))
            for z in [-.46,.46]:
                part(root,"box",Vector3(0,.42,z),Vector3(1.1,.07,.06),timber)
                for x in [-.45,.45]: part(root,"box",Vector3(x,.26,z),Vector3(.06,.55,.06),timber)
        "farm":
            part(root,"box",Vector3(0,.025,0),Vector3(1,.05,1),Color("806148"))
            for x in [-.32,-.1,.12,.34]:
                for z in [-.35,-.1,.15,.4]: part(root,"cone",Vector3(x,.23,z),Vector3(.14,.45,.14),Color("c6b360"))
        "well":
            part(root,"cylinder",Vector3(0,.23,0),Vector3(.65,.46,.65),stone)
            part(root,"cylinder",Vector3(0,.47,0),Vector3(.4,.03,.4),Color("3e8094"))
            for x in [-.33,.33]: part(root,"box",Vector3(x,.65,0),Vector3(.06,.9,.06),timber)
            roof(root,1.05,.85,.7,Color("af7954"))
        "campfire", "hearth":
            for x in [-.2,.2]: part(root,"box",Vector3(x,.12,0),Vector3(.1,.12,.6),timber)
            for x in [-.3,0,.3]: part(root,"sphere",Vector3(x,.1,.3),Vector3(.2,.15,.17),stone)
        "wall", "gate":
            for x in [-.42,.42]: part(root,"box",Vector3(x,.7,0),Vector3(.18,1.4,.35),stone)
            if kind == "wall":
                part(root,"box",Vector3(0,.6,0),Vector3(.85,1.2,.25),stone)
            else:
                part(root,"box",Vector3(0,1.25,0),Vector3(.9,.25,.35),stone)
                for x in [-.2,0,.2]: part(root,"box",Vector3(x,.55,0),Vector3(.07,1.0,.1),timber)
        "watchtower":
            part(root,"box",Vector3(0,.8,0),Vector3(.6,1.6,.6),stone)
            part(root,"box",Vector3(0,1.6,0),Vector3(.95,.25,.95),Color("d2cbb0"))
            for x in [-.38,.38]:
                for z in [-.38,.38]: part(root,"box",Vector3(x,1.85,z),Vector3(.2,.3,.2),stone)
            part(root,"box",Vector3(0,.75,-.31),Vector3(.15,.3,.02),Color("405347"))
        "market":
            for x in [-.4,.4]:
                for z in [-.35,.35]: part(root,"box",Vector3(x,.5,z),Vector3(.07,1,.07),timber)
            for x in range(5): part(root,"box",Vector3(-.4+x*.2,.95,0),Vector3(.2,.12,.9),faction if x%2 else plaster)
            part(root,"box",Vector3(0,.42,0),Vector3(.95,.12,.7),timber)
            for x in [-.3,0,.3]: part(root,"sphere",Vector3(x,.56,-.1),Vector3(.15,.15,.15),Color("d7ad5b"))
        "mine":
            part(root,"sphere",Vector3(0,.35,.2),Vector3(1.25,.9,1),Color("858a7e"))
            part(root,"box",Vector3(0,.3,-.32),Vector3(.55,.6,.08),Color("34483e"))
            for x in [-.3,.3]: part(root,"box",Vector3(x,.35,-.4),Vector3(.08,.7,.1),timber)
            part(root,"box",Vector3(0,.68,-.4),Vector3(.7,.08,.1),timber)
            for x in [-.2,.2]: part(root,"box",Vector3(x,.02,-.8),Vector3(.05,.04,1.1),stone)
        "furnace":
            part(root,"cylinder",Vector3(0,.5,0),Vector3(.7,1,.7),Color("a37a5c"))
            part(root,"cylinder",Vector3(0,1.1,0),Vector3(.35,.4,.35),stone)
            part(root,"box",Vector3(0,.3,-.36),Vector3(.3,.3,.03),Color("dc9e4b"))
        "rain_collector":
            part(root,"cylinder",Vector3(0,.3,0),Vector3(.75,.6,.75),timber)
            part(root,"cylinder",Vector3(0,.61,0),Vector3(.65,.02,.65),Color("6fa9ae"))
        _:
            var wide := 1.2 if kind in ["hall","barn","warehouse"] else .95
            part(root,"box",Vector3(0,.4,0),Vector3(wide,.8,.85),plaster if kind not in ["storage","barn","warehouse"] else Color("ab8a61"))
            for x in [-wide*.45,wide*.45]: part(root,"box",Vector3(x,.4,-.43),Vector3(.06,.85,.04),timber)
            part(root,"box",Vector3(0,.24,-.44),Vector3(.24,.48,.03),timber)
            var roof_color := Color("a3644d")
            if kind in ["workshop","blacksmith","carpenter"]: roof_color = Color("587b76")
            if kind == "hall": roof_color = Color("647e9b")
            roof(root,.95,wide+ .22,1.05,roof_color)
            for x in [-.3,.3]: part(root,"box",Vector3(x,.5,-.45),Vector3(.16,.18,.025),Color("e7bd72"))
            if kind in ["workshop","blacksmith"]:
                part(root,"box",Vector3(.3,1.1,.18),Vector3(.2,.8,.22),stone)
                part(root,"box",Vector3(.6,.2,-.35),Vector3(.4,.15,.25),Color("4d5a59"))
            if kind in ["storage","warehouse","carpenter","barn"]:
                for x in [-.5,-.2]: part(root,"box",Vector3(x,.15,-.65),Vector3(.25,.3,.25),Color("c79f69"))
            if kind == "hall": part(root,"box",Vector3(.4,.7,-.46),Vector3(.16,.6,.04),faction)
    return root

static func human(faction: Color, occupation: String, player: bool, appearance: Dictionary = {}, life_stage := "adult", equipment: Array = []) -> Node3D:
    var root := Node3D.new()
    var color := Color("e9c67c") if player else faction
    part(root,"cone",Vector3(0,.48,0),Vector3(.38,.55,.3),color)
    var skin := Color("ebc9a3").lerp(Color("77513e"),float(appearance.get("skin",.35)))
    var head := part(root,"sphere",Vector3(0,.86,0),Vector3(.24,.26,.24),skin)
    var hair := Color(str(appearance.get("hair","#68503d")))
    if life_stage=="elder":hair=hair.lerp(Color("c5c7bf"),.7)
    part(root,"sphere",Vector3(0,.94,.02),Vector3(.26,.13,.25),hair)
    for x in [-.06,.06]:part(root,"sphere",Vector3(x,.87,-.12),Vector3(.025,.025,.02),Color(str(appearance.get("eyes","#574337"))))
    if appearance.get("texture","")=="curly":
        for x in [-.1,0.,.1]:part(root,"sphere",Vector3(x,.98,0),Vector3(.13,.13,.15),hair)
    if appearance.get("face","")=="angular":head.scale.x*=.9
    root.scale=Vector3.ONE*float({"infant":.45,"child":.65,"adolescent":.85,"elder":.97}.get(life_stage,1.))
    for x in [-.095,.095]:
        var leg := part(root,"box",Vector3(x,.13,0),Vector3(.10,.28,.12),Color("3e4a43"))
        leg.name = "LegL" if x < 0 else "LegR"
        var arm := part(root,"box",Vector3(x*2.3,.5,0),Vector3(.10,.35,.1),color.darkened(.12))
        arm.name = "ArmL" if x < 0 else "ArmR"
    match occupation:
        "guard":
            part(root,"box",Vector3(.3,.55,0),Vector3(.04,.9,.04),Color("a8b5ab"))
            part(root,"sphere",Vector3(-.3,.48,-.04),Vector3(.1,.32,.26),Color("b3c0b4"))
        "farmer", "gatherer":
            part(root,"cylinder",Vector3(0,.97,0),Vector3(.4,.05,.38),Color("c2aa73"))
        "builder", "carpenter":
            part(root,"box",Vector3(.3,.48,-.1),Vector3(.1,.25,.1),Color("ba9671"))
            part(root,"box",Vector3(.3,.62,-.1),Vector3(.25,.1,.12),Color("929e9a"))
        "miner":
            part(root,"sphere",head.position+Vector3(0,.08,0),Vector3(.29,.15,.29),Color("858e91"))
            part(root,"box",Vector3(.32,.5,0),Vector3(.03,.6,.03),Color("9e7a50"))
            part(root,"box",Vector3(.32,.77,0),Vector3(.38,.04,.04),Color("acb8b1"))
        "trader":
            part(root,"box",Vector3(0,.48,.2),Vector3(.32,.4,.15),Color("aa8359"))
        "craftsperson":
            part(root,"box",Vector3(0,.45,-.17),Vector3(.25,.4,.04),Color("806954"))
    var cargo:=part(root,"box",Vector3(0,.48,.22),Vector3(.28,.28,.20),Color("ad895a"))
    cargo.name="Cargo"
    cargo.visible=false
    if occupation!="guard" and "shield" in equipment:part(root,"sphere",Vector3(-.3,.48,-.04),Vector3(.1,.32,.26),Color("b3c0b4"))
    if occupation!="guard" and "staff" in equipment:part(root,"box",Vector3(.3,.55,0),Vector3(.04,.9,.04),Color("a8b5ab"))
    return root

static func zombie() -> Node3D:
    # Original low-poly fantasy wanderer: no wounds or graphic imagery.
    var root := human(Color("596a63"),"",false)
    part(root,"box",Vector3(.13,.57,-.15),Vector3(.14,.20,.025),Color("a19876"))
    part(root,"box",Vector3(-.12,.36,-.16),Vector3(.12,.11,.025),Color("788775"))
    part(root,"box",Vector3(0,.96,-.16),Vector3(.30,.08,.06),Color("798d7b"))
    for x in [-.065,.065]:
        part(root,"sphere",Vector3(x,.96,-.20),Vector3(.035,.035,.025),Color("d6e5ba"))
    root.get_node("ArmL").rotation.x=-1.1
    root.get_node("ArmR").rotation.x=-1.3
    return root

static func animal(species: String) -> Node3D:
    var root := Node3D.new()
    var fur := Color("b69772") if species == "deer" else Color("858b81") if species == "wolf" else Color("836e57")
    part(root,"sphere",Vector3(0,.4,0),Vector3(.4,.4,.8),fur)
    part(root,"sphere",Vector3(0,.57,-.38),Vector3(.24,.28,.3),fur.lightened(.1))
    for x in [-.13,.13]:
        for z in [-.23,.23]:
            var leg := part(root,"box",Vector3(x,.17,z),Vector3(.06,.34,.08),Color("615444"))
            leg.name="Leg%s%s" % ["L" if x<0 else "R","F" if z<0 else "B"]
    if species == "deer":
        for x in [-.09,.09]:
            var antler := part(root,"box",Vector3(x,.85,-.4),Vector3(.03,.4,.03),Color("d1c19e"))
            antler.rotation.z = x*3
    if species == "wolf":
        for x in [-.09,.09]: part(root,"cone",Vector3(x,.77,-.35),Vector3(.1,.2,.1),fur)
        part(root,"box",Vector3(0,.54,-.59),Vector3(.17,.13,.22),fur.lightened(.2))
        part(root,"sphere",Vector3(0,.55,-.72),Vector3(.08,.08,.06),Color("36413b"))
        part(root,"sphere",Vector3(0,.48,.4),Vector3(.14,.15,.5),fur.darkened(.2))
        part(root,"sphere",Vector3(0,.55,-.15),Vector3(.48,.46,.35),fur.darkened(.14))
    return root
