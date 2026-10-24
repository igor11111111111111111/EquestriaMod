# Writes the settlement entities into the world map scene.
#
# In Bannerlord every settlement on the map has its own entity in scene.xscene named after the
# settlement id (in vanilla, for example, <game_entity name="town_ES1">). Without it the game
# crashes when creating the map: it has nothing to show for a settlement from settlements.xml.
#
# blender --background --factory-startup --python make_map_entities.py -- <mod Module folder> [map size]
#
# The script backs up scene.xscene and rewrites the entity list: adds ours and removes old ones
# with the same names. The editor must be closed at that time.
import os
import shutil
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402
import map_bridges  # noqa: E402
import map_props  # noqa: E402
import settlement_visuals  # noqa: E402

ARGS = [a for a in sys.argv[sys.argv.index("--") + 1:] if not a.startswith("--")]
# --bare: settlement entities without models. Needed only while building the navmesh:
# face selection in the editor ("Terrain height") hits the town models, and the faces under them
# do not get marked. After saving the navmesh the script is run again, without the flag.
BARE = "--bare" in sys.argv
MOD = ARGS[0]
MAP_SIZE = float(ARGS[1]) if len(ARGS) > 1 else equus_map.MAP_SIZE

SCENE = os.path.join(MOD, "SceneObj", "Main_map", "scene.xscene")
SETTLEMENTS = os.path.join(MOD, "ModuleData", "equestria_settlements.xml")

TAGS = {"town": "town", "castle": "castle", "village": "village", "hideout": "hideout"}


def log(*a):
    print("[entities]", *a, flush=True)


def kind_of(settlement):
    comp = settlement.find("Components")
    if comp is None:
        return "other"
    if comp.find("Village") is not None:
        return "village"
    if comp.find("Hideout") is not None:
        return "hideout"
    town = comp.find("Town")
    if town is not None:
        return "castle" if town.get("is_castle") == "true" else "town"
    return "other"


scene_tree = ET.parse(SCENE)
scene_root = scene_tree.getroot()
terrain = scene_root.find(".//terrain")
min_h, max_h = float(terrain.get("min_height")), float(terrain.get("max_height"))
log(f"рельеф: {terrain.get('node_dimension_x')}x{terrain.get('node_dimension_y')} узлов, "
    f"высоты {min_h:.2f}..{max_h:.2f}")

# Water on the world map must be off. The vanilla Main_map has water_exists="false", and the sea is
# drawn by the terrain itself: enabled water pulls in water_prefabs and a water probe, on which the
# game crashes when creating the map (while the scene opens fine in the editor).
WATER = {
    "water_exists": "false",
    "water_level": "-100.000",
    "water_material": "wat_main_map_ocean_g",
}
water = scene_root.find(".//water_properties")
if water is not None:
    for prop in water.findall("property"):
        if prop.get("name") in WATER:
            prop.set("value", WATER[prop.get("name")])
    log("вода выключена (как на ванильной карте мира)")

# IMPORTANT: terrain_render_version="1" (as in the vanilla Main_map) is not set by hand, and is erased
# if left over from earlier attempts. We tried — the game started crashing even earlier, right at
# rglTerrain_shader_generator::clear. The renderer version must match how the editor built
# terrain.bin and ShaderCache; it cannot be changed in the XML alone, the terrain data would
# remain from version 0.
if "terrain_render_version" in terrain.attrib:
    del terrain.attrib["terrain_render_version"]
    terrain.set("use_dynamic_weather_effects", "false")
    terrain.set("dynamic_flowmap_texture_name", "")
    log("снята неудачная правка версии отрисовщика рельефа")

# Terrain draw distance. The editor creates terrain with its own defaults, but on the world map
# the camera pulls far back, and with those defaults two problems showed up:
#   lod_multiplier = 1 — neighbouring terrain nodes went to different detail levels, and a crease
#       appeared along their border ("a ridge line" along the chunks) when the camera zoomed out;
#   vista_layer_detail_distance = 35 m — beyond 35 m the detail layer textures were dropped from a
#       node, so nodes differed in brightness and the map looked checkered.
# We set the vanilla world map values (lod_multiplier 3, distance 10000 m).
TERRAIN_VIEW = {"lod_multiplier": "3.000", "vista_layer_detail_distance": "10000.000"}
for prop, value in TERRAIN_VIEW.items():
    if terrain.get(prop) != value:
        terrain.set(prop, value)
log("дальность отрисовки рельефа: " + ", ".join("%s=%s" % kv for kv in TERRAIN_VIEW.items()))

# Terrain layers: what the ground is painted with. The editor creates a placeholder layer with a grid
# (editor_grid_8_s) — because of it the map looks like uniform sand. The layer weights themselves
# (what is painted where) are in the binary terrain.bin and not reachable from XML, but the SET of
# layers is defined here. We take it whole from the vanilla world map: layer 0 becomes grass (we fill
# everything with it), and the rest — forest, rocks, snow and so on — stay ready for painting in the editor.
VANILLA_SCENE = os.path.join(
    ARGS[2] if len(ARGS) > 2 else
    r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord",
    "Modules", "SandBox", "SceneObj", "Main_map", "scene.xscene")


def copy_vanilla_layers():
    if not os.path.exists(VANILLA_SCENE):
        log("ванильная сцена не найдена, слои рельефа оставлены как есть")
        return
    # The vanilla scene is 19 MB, no need to parse it whole: cut out the needed piece by text.
    with open(VANILLA_SCENE, encoding="utf-8") as f:
        text = f.read()
    start = text.find("<layers", text.find("<terrain "))
    end = text.find("</layers>", start)
    if start < 0 or end < 0:
        log("в ванильной сцене не нашлось слоёв рельефа")
        return
    block = ET.fromstring(text[start:end + len("</layers>")])
    ours = terrain.find("layers")
    if ours is not None:
        terrain.remove(ours)
    terrain.insert(1, block)
    names = [layer.get("name") or "?" for layer in block.findall("layer")]
    log("слои рельефа взяты с ванильной карты: %d (%s)"
        % (len(names), ", ".join(names[:6]) + (" …" if len(names) > 6 else "")))


copy_vanilla_layers()

# Deep water is the ninth layer: a copy of the river layer with a dark blue tint (mode 2 — color
# multiply, that is how vanilla darkens forests). paint_terrain.py blends it with light water by depth.
DEEP_WATER = "deep_water"
DEEP_TINT = os.environ.get("EQ_DEEP_TINT", "0.140, 0.300, 0.600")
DEEP_MODE = os.environ.get("EQ_DEEP_MODE", "2")


def add_deep_water_layer():
    layers = terrain.find("layers")
    for layer in layers.findall("layer"):
        if layer.get("name") == DEEP_WATER:
            layers.remove(layer)
    river = next(layer for layer in layers.findall("layer") if layer.get("name") == "river")
    import copy
    deep = copy.deepcopy(river)
    deep.set("name", DEEP_WATER)
    for season in deep:
        season.set("name", DEEP_WATER)
    layers.append(deep)
    log("добавлен слой глубокой воды: номер %d" % (len(layers.findall("layer")) - 1))


add_deep_water_layer()

# Color textures instead of the map-style ones. The vanilla map's *_mainmap textures are tinted by
# the virtual texture underlay (TileSets), which our map does not have — without it the ground comes
# out almost white. We take regular ground textures from battle scenes (empire_village_g,
# battania_village), and keep the layers' vegetation — the small map-style trees.
# layer -> (diffuse, normals, gloss)
LAYER_TEXTURES = {
    "default": ("grass_a_d", "grass_a_n", "grass_a_s"),
    "flora_forest": ("forest_a_d", "forest_a_n", "forest_a_s"),
    "rock": ("rock_cliff_b_d", "rock_cliff_b_n", "rock_cliff_b_s"),
    # Below — layers repainted for the Equus map terrain types (see paint_terrain.py)
    "grass": ("snow_a_d", "snow_a_n", "snow_a_s"),                           # north, peaks
    "dirt": ("ground_earth", "ground_earth_bump", "ground_earth_s"),         # hills, steppe
    "dirt2": ("desert_floor_a", "desert_floor_c_n", "desert_floor_c_s"),     # wastelands
    "forest2": ("ground_mud_b_d", "ground_mud_b_n", "ground_mud_b_s"),       # swamps
    "river": ("water_ground", "none", "gloss_s"),                            # sea, lakes, rivers
    "deep_water": ("water_ground", "none", "gloss_s"),                       # deep sea
}

# The layer texture repeats every 5 m (scale in the layer), and on flat areas this repeat shows as a
# grid: the normal map gives each tile its own bump with a shadow, and when the camera zooms out the
# bumps add up to light and dark squares. The vanilla world map has the same repeat, but it is covered
# by the virtual texture (TileSets "WorldMap"), which we do not have. So for the large flat layers we
# drop the normal map — on the world map the landscape itself provides the relief anyway.
FLAT_LAYERS = ("default", "grass", "dirt", "dirt2", "forest2")


def recolor_layers():
    layers = terrain.find("layers")
    changed = 0
    for layer in layers.findall("layer"):
        textures = LAYER_TEXTURES.get(layer.get("name"))
        for season in layer:
            # "Mesh blending" is a mode of the map renderer; it is off in regular scenes.
            season.set("is_mesh_blend_layer", "false")
            if season.tag != "summer" or textures is None:
                continue
            season.set("albedo_factor_color", "1.000, 1.000, 1.000")
            season.set("albedo_factor_mode", "0")
            normal = "none" if layer.get("name") in FLAT_LAYERS else textures[1]
            wanted = {"diffusemap": textures[0], "normalmap": normal, "specularmap": textures[2],
                      "areamap": "none", "displacementmap": "none"}
            for texture in season.find("textures").findall("texture"):
                if texture.get("type") in wanted:
                    texture.set("name", wanted[texture.get("type")])
            changed += 1
    log("слоям рельефа даны цветные текстуры обычных сцен: %d" % changed)


recolor_layers()
for _layer in terrain.find("layers").findall("layer"):
    if _layer.get("name") == DEEP_WATER:
        for _season in _layer:
            _season.set("albedo_factor_color", DEEP_TINT)
            _season.set("albedo_factor_mode", DEEP_MODE)

# references.txt next to the scene is the list of resources the game loads for it: the first line is
# the number of entries, then "mesh name" / "texture name". The editor writes it itself; we change the
# layers from code, so we add their textures and vegetation there, otherwise they may not load.
REFERENCES = os.path.join(os.path.dirname(SCENE), "references.txt")


def update_references():
    entries = set()
    if os.path.exists(REFERENCES):
        with open(REFERENCES, encoding="utf-8") as f:
            for line in f.read().splitlines()[1:]:
                if line.strip():
                    entries.add(line.strip())
    for texture in terrain.find("layers").iter("texture"):
        name = texture.get("name")
        if name and name != "none":
            entries.add("texture " + name)
    for mesh in terrain.find("layers").iter("mesh"):
        if mesh.get("name"):
            entries.add("mesh " + mesh.get("name"))
    # Entity models (settlement houses, walls, towers). Without this list the scene does not load their
    # resources: only names and decals are visible for settlements on the map.
    for component in scene_root.iter("meta_mesh_component"):
        if component.get("name"):
            entries.add("mesh " + component.get("name"))
    ordered = sorted(entries)
    with open(REFERENCES, "w", encoding="utf-8", newline="\n") as f:
        f.write("%d\n%s\n" % (len(ordered), "\n".join(ordered)))
    log("references.txt: %d записей" % len(ordered))


entities = scene_root.find(".//entities")
if entities is None:
    raise SystemExit("в сцене нет раздела entities")

wanted = {}


def collect(root, only_hideouts=False):
    for s in root:
        kind = kind_of(s)
        if kind not in TAGS:
            continue
        if only_hideouts and kind != "hideout":
            continue
        x, y = s.get("posX"), s.get("posY")
        if x is None or y is None:
            continue
        wanted[s.get("id")] = (kind, float(x), float(y))


# Bandit hideouts stay vanilla: their description is taken from the game, and the coordinates from
# our file, where they are moved onto our map.
VANILLA_SETTLEMENTS = os.path.join(
    ARGS[2] if len(ARGS) > 2 else
    r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord",
    "Modules", "SandBox", "ModuleData", "settlements.xml")
if os.path.exists(VANILLA_SETTLEMENTS):
    collect(ET.parse(VANILLA_SETTLEMENTS).getroot(), only_hideouts=True)

ours = ET.parse(SETTLEMENTS).getroot()
collect(ours)
# Coordinate overrides (they have no Components) — applied on top.
for s in ours:
    if s.get("id") in wanted and s.get("posX") is not None and s.find("Components") is None:
        kind, _x, _y = wanted[s.get("id")]
        wanted[s.get("id")] = (kind, float(s.get("posX")), float(s.get("posY")))

# Remove ALL previous settlement entities, not only those matching by name: after the world is
# reshaped the old ids disappear, and leftover entities would point to nothing.
removed = 0
for e in list(entities):
    scripts = e.find("scripts")
    is_settlement = scripts is not None and any(
        s.get("name") == "Town Entity Manager" for s in scripts.findall("script"))
    if is_settlement or e.get("name") in wanted:
        entities.remove(e)
        removed += 1

# The ground plane the editor puts into every new scene (editor_plane_low, 20x20 m, scaled 20 times,
# at a height of 1 m). On the map it lay above the sea floor and covered the sea with a flat "slab"
# with straight edges. The vanilla map does not have it.
for e in list(entities):
    if e.get("name") == "ground_plane":
        entities.remove(e)
        removed += 1
        log("убрана подложка редактора ground_plane")

# Map borders. SandBox.MapScene.Load() takes them without any check:
#   GameEntity a = _scene.GetFirstEntityWithName("border_min");
#   MatrixFrame f = a.GetGlobalFrame();      <- if the entity is missing, NullReferenceException here
# That is exactly where the map crashed. The height of border_max sets the camera's upper limit.
BORDERS = {
    "border_min": (0.0, 0.0, 0.0),
    "border_max": (MAP_SIZE, MAP_SIZE, 300.0),
}
for e in list(entities):
    if e.get("name") in BORDERS:
        entities.remove(e)
for bname, (bx, by, bz) in BORDERS.items():
    e = ET.SubElement(entities, "game_entity", {"name": bname, "old_prefab_name": ""})
    ET.SubElement(e, "transform", {
        "position": f"{bx:.3f}, {by:.3f}, {bz:.3f}",
        "rotation_euler": "0.000, 0.000, 0.000",
    })
log(f"границы карты: border_min 0,0 — border_max {MAP_SIZE:.0f},{MAP_SIZE:.0f}")

# Service scripts of the world map. These are ordinary scene entities, but the campaign does not work
# without them: SettlementPositionScript registers the settlement distance cache at startup, and while
# it is missing DefaultMapDistanceModel.GetDistance fails on a null reference (there is no check). The
# others handle map color grading, town memory optimisation and siege engines on the map.
# Names and variables are copied one to one from the vanilla Main_map.
SCRIPTS = [
    ("settlements_scripts", "SettlementPositionScript", {
        "_partyNavigationModelOverriddenClassName": "DefaultPartyNavigationModel",
        "_distanceModelOverridenClassName": "DefaultMapDistanceModel",
    }),
    ("map_town_scene_manager", "Town Scene Manager", {}),
    ("color_grade_manager", "MapColorGradeManager", {
        "ColorGradeEnabled": "true",
        "AtmosphereSimulationEnabled": "false",
        "TimeOfDay": "22.000",
        "SeasonTimeFactor": "0.000",
    }),
    ("map_siege_prefab_cache", "CampaignMapSiegePrefabEntityCache", {
        "_attackerBallistaPrefab": "ballista_a_mapicon",
        "_defenderBallistaPrefab": "ballista_b_mapicon",
        "_attackerFireBallistaPrefab": "ballista_a_fire_mapicon",
        "_defenderFireBallistaPrefab": "ballista_b_fire_mapicon",
        "_attackerMangonelPrefab": "mangonel_a_mapicon",
        "_defenderMangonelPrefab": "mangonel_b_mapicon",
        "_attackerFireMangonelPrefab": "mangonel_a_fire_mapicon",
        "_defenderFireMangonelPrefab": "mangonel_b_fire_mapicon",
        "_attackerTrebuchetPrefab": "trebuchet_a_mapicon",
        "_defenderTrebuchetPrefab": "trebuchet_b_mapicon",
    }),
]

script_names = {name for name, _script, _vars in SCRIPTS}
for e in list(entities):
    if e.get("name") in script_names:
        entities.remove(e)

center = MAP_SIZE * 0.5
center_z = equus_map.height(center, center)
for index, (ename, script_name, variables) in enumerate(SCRIPTS):
    e = ET.SubElement(entities, "game_entity", {
        "name": ename, "old_prefab_name": "__empty_object", "mobility": "1",
    })
    ET.SubElement(e, "transform", {
        "position": f"{center + index * 2.0:.3f}, {center:.3f}, {center_z:.3f}",
        "rotation_euler": "0.000, 0.000, 0.000",
    })
    script = ET.SubElement(ET.SubElement(e, "scripts"), "script", {"name": script_name})
    if variables:
        holder = ET.SubElement(script, "variables")
        for vname, value in variables.items():
            ET.SubElement(holder, "variable", {"name": vname, "value": value})
log(f"служебные скрипты карты: {len(SCRIPTS)} шт. "
    f"({', '.join(s for _n, s, _v in SCRIPTS)})")

# Weather on the map. This prefab from the SandBox module carries the SnowAndRainTextureDefiner script,
# which sets the weather grid size (32x32). Without it the size stays zero, the weather array is empty,
# and the game crashes with an out-of-bounds index as soon as it starts placing lord parties. In the
# vanilla scene it is inserted exactly the same way — as a reference to the prefab.
WEATHER_PREFAB = "MapSnowAndRainDefiner"
for e in list(entities):
    if e.get("prefab") == WEATHER_PREFAB:
        entities.remove(e)
e = ET.SubElement(entities, "game_entity", {"prefab": WEATHER_PREFAB})
ET.SubElement(e, "transform", {
    "position": f"{center:.3f}, {center:.3f}, {center_z:.3f}",
    "rotation_euler": "0.000, 0.000, 0.000",
})
log("погодный объект " + WEATHER_PREFAB + " добавлен (сетка погоды 32x32)")

# Settlement models — from vanilla settlements of the same kind and culture (see settlement_visuals.py).
DONORS = settlement_visuals.load_donors(ARGS[2] if len(ARGS) > 2 else None)
# Bandit hideouts take the model of their vanilla hideout with the same id (settlement_visuals)
HIDEOUTS = settlement_visuals.load_hideouts(ARGS[2] if len(ARGS) > 2 else None)

# Scene levels. Settlement models are split into levels: level_1..level_3 are development stages,
# looted is a raided village, siege is a siege. The levels must be declared in the scene the same way
# as on the vanilla map: otherwise SettlementVisual.OnStartup gets an unknown level number and crashes
# (KeyNotFoundException) when the map opens.
VANILLA_LEVELS = [("base", 1), ("level_1", 2), ("level_2", 4), ("level_3", 8),
                  ("civilian", 16), ("siege", 32), ("looted", 64)]
levels = scene_root.find("levels")
if levels is None:
    levels = ET.Element("levels")
    scene_root.insert(1, levels)
for level in list(levels):
    levels.remove(level)
for lname, mask in VANILLA_LEVELS:
    ET.SubElement(levels, "level", {"name": lname, "mask": str(mask)})
log("уровни сцены: " + ", ".join(n for n, _m in VANILLA_LEVELS))
dressed = 0
for sid, (kind, x, y) in wanted.items():
    z = equus_map.height(x, y)
    e = ET.SubElement(entities, "game_entity", {"name": sid, "old_prefab_name": "", "mobility": "1"})
    tags = ET.SubElement(e, "tags")
    ET.SubElement(tags, "tag", {"name": TAGS[kind]})
    ET.SubElement(e, "transform", {
        "position": f"{x:.3f}, {y:.3f}, {z:.3f}",
        "rotation_euler": "0.000, 0.000, 0.000",
    })
    scripts = ET.SubElement(e, "scripts")
    script = ET.SubElement(scripts, "script", {"name": "Town Entity Manager"})
    variables = ET.SubElement(script, "variables")
    ET.SubElement(variables, "variable", {"name": "Override Factor Color", "value": "true"})
    ET.SubElement(variables, "variable", {"name": "Factor Color", "value": "1.000, 1.000, 1.000, 1.000"})
    if BARE:
        continue
    if kind == "hideout":
        if settlement_visuals.dress_hideout(e, HIDEOUTS.get(sid)):
            dressed += 1
    elif settlement_visuals.dress(e, settlement_visuals.pick(*DONORS, sid)):
        dressed += 1

log(f"сущностей: удалено старых {removed}, добавлено {len(wanted)}, с моделями {dressed}")

# Player spawn point (sp_player). Needed both by the game and by the navmesh generator in the editor:
# the navmesh is built from it over all connected land. Placed at the gates of Equestria's capital.
capital = wanted.get("town_empire_0")
if capital:
    px, py = equus_map.nearest_ground(capital[1] + 6.0, capital[2] - 6.0) or (capital[1], capital[2])
    for e in list(entities):
        if e.get("prefab") == "sp_player":
            entities.remove(e)
    e = ET.SubElement(entities, "game_entity", {"prefab": "sp_player"})
    ET.SubElement(e, "transform", {
        "position": f"{px:.3f}, {py:.3f}, {equus_map.height(px, py):.3f}",
        "rotation_euler": "0.000, 0.000, 0.000",
    })
    log(f"точка игрока у столицы: {px:.0f}, {py:.0f}")

# Environment props: boulders, rocks, groves, snags (see map_props.py). With --bare there are none:
# when building the navmesh in the editor extra models get in the way of selecting faces.
if BARE:
    log("предметы окружения пропущены (--bare)")
else:
    map_props.place(entities, wanted, log)
    # Bridges where roads cross rivers — with the same setup as vanilla (see map_bridges.py).
    map_bridges.place(entities, log, MOD)

update_references()

backup = SCENE + ".bak"
if not os.path.exists(backup):
    shutil.copy2(SCENE, backup)
    log("резервная копия", backup)
ET.indent(scene_root, space="\t")
scene_tree.write(SCENE, encoding="utf-8", xml_declaration=True)
log("written", SCENE)
