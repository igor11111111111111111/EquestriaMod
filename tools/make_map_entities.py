# Вписывает в сцену карты мира сущности поселений.
#
# В Bannerlord у каждого поселения на карте есть своя сущность в scene.xscene с именем, равным
# идентификатору поселения (у ванили это, например, <game_entity name="town_ES1">). Без неё игра
# падает при создании карты: ей нечего показать для поселения из settlements.xml.
#
# blender --background --factory-startup --python make_map_entities.py -- <папка Module мода> [размер карты]
#
# Скрипт делает резервную копию scene.xscene и переписывает список сущностей: свои добавляет,
# старые с теми же именами убирает. Редактор в это время должен быть закрыт.
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
# --bare: сущности поселений без моделей. Нужно только на время построения сетки проходимости:
# выбор граней в редакторе («Terrain height») упирается в модели городов, и грани под ними
# не размечаются. После сохранения сетки скрипт запускается снова, без ключа.
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

# Вода на карте мира должна быть выключена. У ванильной Main_map water_exists="false", а море
# нарисовано самим рельефом: включённая вода тянет за собой water_prefabs и водяной зонд, на чём
# игра падает при создании карты (в редакторе сцена при этом открывается нормально).
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

# ВАЖНО: terrain_render_version="1" (как в ванильной Main_map) руками не проставляем и стираем,
# если осталось от прошлых попыток. Пробовали — игра стала падать ещё раньше, прямо на
# rglTerrain_shader_generator::clear. Версия отрисовщика должна совпадать с тем, как редактор
# собрал terrain.bin и ShaderCache; поменять её в одном лишь XML нельзя, данные рельефа
# останутся от версии 0.
if "terrain_render_version" in terrain.attrib:
    del terrain.attrib["terrain_render_version"]
    terrain.set("use_dynamic_weather_effects", "false")
    terrain.set("dynamic_flowmap_texture_name", "")
    log("снята неудачная правка версии отрисовщика рельефа")

# Дальность отрисовки рельефа. Редактор создаёт рельеф со своими значениями по умолчанию, а на
# карте мира камера отъезжает далеко, и с ними вылезали две болячки:
#   lod_multiplier = 1 — соседние узлы рельефа уходили на разные уровни детализации, и по их
#       границе появлялась складка («линия холмиком» вдоль чанков) при отдалении камеры;
#   vista_layer_detail_distance = 35 м — дальше 35 м с узла снимались детальные текстуры слоёв,
#       из-за чего узлы отличались по яркости и карта шла квадратами.
# Ставим ванильные значения карты мира (lod_multiplier 3, дальность 10000 м).
TERRAIN_VIEW = {"lod_multiplier": "3.000", "vista_layer_detail_distance": "10000.000"}
for prop, value in TERRAIN_VIEW.items():
    if terrain.get(prop) != value:
        terrain.set(prop, value)
log("дальность отрисовки рельефа: " + ", ".join("%s=%s" % kv for kv in TERRAIN_VIEW.items()))

# Слои рельефа: чем покрашена земля. Редактор создаёт слой-заглушку с сеткой (editor_grid_8_s) —
# из-за неё карта выглядит однообразным песком. Сами веса слоёв (что где покрашено) лежат в
# двоичном terrain.bin и из XML недоступны, но НАБОР слоёв задаётся здесь. Берём его целиком с
# ванильной карты мира: слой 0 становится травой (им у нас залито всё), а остальные — лес, скалы,
# снег и прочее — остаются наготове, чтобы рисовать ими в редакторе.
VANILLA_SCENE = os.path.join(
    ARGS[2] if len(ARGS) > 2 else
    r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord",
    "Modules", "SandBox", "SceneObj", "Main_map", "scene.xscene")


def copy_vanilla_layers():
    if not os.path.exists(VANILLA_SCENE):
        log("ванильная сцена не найдена, слои рельефа оставлены как есть")
        return
    # Ванильная сцена — 19 МБ, разбирать её целиком незачем: вырезаем нужный кусок по тексту.
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

# Глубокая вода — девятый слой: копия речного с тёмно-синим оттенком (режим 2 — умножение
# цвета, так в ванили затемнены леса). paint_terrain.py смешивает его со светлой водой по глубине.
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

# Цветные текстуры вместо картографических. Текстуры *_mainmap у ванильной карты окрашивает
# подложка виртуальной текстуры (TileSets), которой у нашей карты нет, — без неё земля выходит
# почти белой. Берём обычные текстуры земли из боевых сцен (empire_village_g, battania_village),
# а растительность слоёв — мелкие картографические деревья — оставляем.
# слой -> (диффуз, нормали, блеск)
LAYER_TEXTURES = {
    "default": ("grass_a_d", "grass_a_n", "grass_a_s"),
    "flora_forest": ("forest_a_d", "forest_a_n", "forest_a_s"),
    "rock": ("rock_cliff_b_d", "rock_cliff_b_n", "rock_cliff_b_s"),
    # Ниже — перекрашенные слои под типы местности карты Эквуса (см. paint_terrain.py)
    "grass": ("snow_a_d", "snow_a_n", "snow_a_s"),                           # север, вершины
    "dirt": ("ground_earth", "ground_earth_bump", "ground_earth_s"),         # холмы, степь
    "dirt2": ("desert_floor_a", "desert_floor_c_n", "desert_floor_c_s"),     # пустоши
    "forest2": ("ground_mud_b_d", "ground_mud_b_n", "ground_mud_b_s"),       # болота
    "river": ("water_ground", "none", "gloss_s"),                            # море, озёра, реки
    "deep_water": ("water_ground", "none", "gloss_s"),                       # глубокое море
}

# Текстура слоя повторяется каждые 5 м (scale в слое), и на ровных местах этот повтор виден
# сеткой: карта нормалей даёт у каждой плитки свой бугорок с тенью, а при отдалении камеры
# бугорки складываются в светлые и тёмные квадраты. У ванильной карты мира повтор такой же,
# но его перекрывает виртуальная текстура (TileSets "WorldMap"), которой у нас нет. Поэтому
# у больших ровных слоёв карту нормалей снимаем — рельеф на карте мира и так даёт сам ландшафт.
FLAT_LAYERS = ("default", "grass", "dirt", "dirt2", "forest2")


def recolor_layers():
    layers = terrain.find("layers")
    changed = 0
    for layer in layers.findall("layer"):
        textures = LAYER_TEXTURES.get(layer.get("name"))
        for season in layer:
            # «Смешивание с мешами» — режим картографического отрисовщика; у обычных сцен выключен.
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

# references.txt рядом со сценой — список ресурсов, которые игра подгружает для неё: первая строка
# число записей, дальше "mesh имя" / "texture имя". Редактор пишет его сам; мы меняем слои из кода,
# поэтому дописываем туда их текстуры и растительность, иначе они могут не загрузиться.
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
    # Модели сущностей (дома, стены, башни поселений). Без этого списка сцена не подгружает их
    # ресурсы: у поселений на карте видны только названия и декали.
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


# Логова разбойников остаются ванильными: их описание берём из игры, а координаты — из нашего
# файла, где они переставлены на нашу карту.
VANILLA_SETTLEMENTS = os.path.join(
    ARGS[2] if len(ARGS) > 2 else
    r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord",
    "Modules", "SandBox", "ModuleData", "settlements.xml")
if os.path.exists(VANILLA_SETTLEMENTS):
    collect(ET.parse(VANILLA_SETTLEMENTS).getroot(), only_hideouts=True)

ours = ET.parse(SETTLEMENTS).getroot()
collect(ours)
# Переопределения координат (у них нет Components) — накладываем поверх.
for s in ours:
    if s.get("id") in wanted and s.get("posX") is not None and s.find("Components") is None:
        kind, _x, _y = wanted[s.get("id")]
        wanted[s.get("id")] = (kind, float(s.get("posX")), float(s.get("posY")))

# Убираем ВСЕ прежние сущности поселений, а не только совпавшие по имени: после перекройки мира
# старые идентификаторы исчезают, и оставшиеся сущности ссылались бы в пустоту.
removed = 0
for e in list(entities):
    scripts = e.find("scripts")
    is_settlement = scripts is not None and any(
        s.get("name") == "Town Entity Manager" for s in scripts.findall("script"))
    if is_settlement or e.get("name") in wanted:
        entities.remove(e)
        removed += 1

# Плоскость-подложка, которую редактор кладёт в каждую новую сцену (editor_plane_low, 20x20 м,
# растянута в 20 раз, на высоте 1 м). На карте она лежала выше морского дна и закрывала море
# ровной «плитой» с прямыми краями. У ванильной карты её нет.
for e in list(entities):
    if e.get("name") == "ground_plane":
        entities.remove(e)
        removed += 1
        log("убрана подложка редактора ground_plane")

# Границы карты. SandBox.MapScene.Load() берёт их без всякой проверки:
#   GameEntity a = _scene.GetFirstEntityWithName("border_min");
#   MatrixFrame f = a.GetGlobalFrame();      <- если сущности нет, тут NullReferenceException
# Именно на этом падала карта. Высота border_max задаёт верхний предел камеры.
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

# Служебные скрипты карты мира. Это обычные сущности сцены, но без них кампания не работает:
# SettlementPositionScript при запуске регистрирует кэш расстояний между поселениями, и пока его
# нет, DefaultMapDistanceModel.GetDistance падает на пустой ссылке (проверки там нет). Остальные
# отвечают за цветокоррекцию карты, оптимизацию памяти городов и осадные машины на карте.
# Имена и переменные взяты один в один из ванильной Main_map.
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

# Погода на карте. Этот готовый объект из модуля SandBox несёт скрипт SnowAndRainTextureDefiner,
# который задаёт размер погодной сетки (32x32). Без него размер остаётся нулевым, массив погоды
# получается пустым, и игра валится на выходе за границы массива, едва начав расставлять отряды
# лордов. В ванильной сцене он вставлен ровно так же — ссылкой на готовый объект.
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

# Модели поселений — у ванильных поселений того же вида и культуры (см. settlement_visuals.py).
DONORS = settlement_visuals.load_donors(ARGS[2] if len(ARGS) > 2 else None)
# Логова разбойников берут модель своего ванильного логова с тем же id (settlement_visuals)
HIDEOUTS = settlement_visuals.load_hideouts(ARGS[2] if len(ARGS) > 2 else None)

# Уровни сцены. Модели поселений разложены по уровням: level_1..level_3 — стадии развития,
# looted — разорённая деревня, siege — осада. Уровни должны быть объявлены в сцене так же, как у
# ванильной карты: иначе SettlementVisual.OnStartup получает неизвестный номер уровня и падает
# (KeyNotFoundException) при открытии карты.
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

# Точка появления игрока (sp_player). Нужна и игре, и генератору сетки проходимости в редакторе:
# сетка строится от неё по всей связной суше. Ставим у ворот столицы Эквестрии.
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

# Предметы окружения: валуны, скалы, рощицы, коряги (см. map_props.py). С ключом --bare их нет:
# при построении сетки проходимости в редакторе лишние модели мешают выбирать грани.
if BARE:
    log("предметы окружения пропущены (--bare)")
else:
    map_props.place(entities, wanted, log)
    # Мосты на пересечениях дорог с реками — той же связкой, что у ванили (см. map_bridges.py).
    map_bridges.place(entities, log, MOD)

update_references()

backup = SCENE + ".bak"
if not os.path.exists(backup):
    shutil.copy2(SCENE, backup)
    log("резервная копия", backup)
ET.indent(scene_root, space="\t")
scene_tree.write(SCENE, encoding="utf-8", xml_declaration=True)
log("written", SCENE)
