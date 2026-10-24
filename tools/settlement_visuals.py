# Внешний вид поселений на карте мира: берём готовые модели у ванильных поселений.
#
# У каждого ванильного города, замка и деревни в Main_map есть сущность с дочерними объектами:
# модели по уровням развития (l1..l3, разорённая деревня), физическое тело (bo_town, bo_castle,
# bo_village), точка ворот (town_gate / gate_position) и осадные места. Скрипт Town Entity
# Manager сам включает нужный уровень.
#
# Нашему поселению подбираем «донора» — ванильное поселение того же вида и той же культуры
# (id культур у нас ванильные: empire = Эквестрия и т.д.) — и копируем его дочерние объекты,
# поворот и масштаб. Ворота ставим так же, как у донора: смещение ворот от центра в ванильном
# settlements.xml записано в мировых координатах и совпадает с моделью при том же повороте.
#
# Выбор донора зависит только от вида, культуры и номера поселения, поэтому make_world.py
# (ворота) и make_map_entities.py (модели) получают одного и того же донора.
import copy
import os
import re
import xml.etree.ElementTree as ET

GAME = r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
KINDS = ("town", "castle", "village")
MAX_ROOT_CHILDREN = 30
# Во сколько раз поселения крупнее ванильных. Модели те же, что на карте Кальрадии, но на нашей
# карте они терялись на фоне леса. Смещение ворот умножается на тот же множитель, иначе отряды
# входили бы в город не через ворота модели. На карте 1024 м города EaW стоят местами в 13-20 м
# друг от друга, поэтому не ×2, как было на маленькой карте, а ×1,5.
SCALE = {"town": 1.5, "castle": 1.5, "village": 1.5}
# Культуры без своих моделей поселений в игре берут их у ванильной
DONOR_CULTURE = {"nord": "sturgia"}
OUR_ID = re.compile(r"^(town|castle|village)_([a-z]+)_(\d+)$")


def _paths(game):
    base = os.path.join(game or GAME, "Modules", "SandBox")
    return (os.path.join(base, "ModuleData", "settlements.xml"),
            os.path.join(base, "SceneObj", "Main_map", "scene.xscene"))


def _kind(settlement):
    comp = settlement.find("Components")
    if comp is None:
        return None
    if comp.find("Village") is not None:
        return "village"
    if comp.find("Hideout") is not None:
        return "hideout"
    town = comp.find("Town")
    if town is not None:
        return "castle" if town.get("is_castle") == "true" else "town"
    return None


class Donor:
    def __init__(self, sid, kind, culture, gate_offset):
        self.id = sid
        self.kind = kind
        self.culture = culture
        self.gate_offset = gate_offset      # (dx, dy) или None, если ворот нет
        self.children = None                # элемент <children> из сцены
        self.rotation = "0.000, 0.000, 0.000"
        self.scale = None


def load_donors(game=None, with_scene=True):
    """Ванильные поселения: {(вид, культура): [Donor, ...]} в порядке id, плюс {id: Donor}."""
    settlements_path, scene_path = _paths(game)
    by_key, by_id = {}, {}
    for s in ET.parse(settlements_path).getroot():
        kind = _kind(s)
        if kind is None:
            continue
        culture = (s.get("culture") or "").replace("Culture.", "")
        gate = None
        if s.get("gate_posX") is not None:
            gate = (float(s.get("gate_posX")) - float(s.get("posX")),
                    float(s.get("gate_posY")) - float(s.get("posY")))
        donor = Donor(s.get("id"), kind, culture, gate)
        by_id[donor.id] = donor
        by_key.setdefault((kind, culture), []).append(donor)
    for donors in by_key.values():
        donors.sort(key=lambda d: d.id)

    # Доноров без годной модели выбрасываем из списков — make_world.py и make_map_entities.py
    # должны видеть одинаковые списки, поэтому сцену читаем в обоих случаях.
    if with_scene:
        for entity in ET.parse(scene_path).getroot().iter("game_entity"):
            donor = by_id.get(entity.get("name"))
            if donor is None or donor.children is not None:
                continue
            children = entity.find("children")
            if children is None or not len(children):
                continue
            # Берём только доноров обычного устройства: у города в корне есть тело bo_town, у
            # замка — bo_castle, а модели собраны в группы по уровням (у town_EN2 в корне девять
            # объектов). Встречаются сборные поселения — у town_EN1 в корне 334 отдельных дома,
            # камня и декали, — у нас такая модель не видна вовсе.
            body = {"town": "bo_town", "castle": "bo_castle"}.get(donor.kind)
            if body and not any(child.get("name") == body for child in children):
                continue
            if len(children) > MAX_ROOT_CHILDREN:
                continue
            donor.children = children
            transform = entity.find("transform")
            if transform is not None:
                donor.rotation = transform.get("rotation_euler") or donor.rotation
                donor.scale = transform.get("scale")
        for key in list(by_key):
            by_key[key] = [d for d in by_key[key] if d.children is not None]
    return by_key, by_id


def pick(by_key, by_id, settlement_id):
    """Донор для нашего поселения или None. Логова разбойников — ванильные, берут свою же сущность."""
    match = OUR_ID.match(settlement_id)
    if match is None:
        return by_id.get(settlement_id)
    kind, culture, index = match.group(1), DONOR_CULTURE.get(match.group(2), match.group(2)), int(match.group(3))
    donors = by_key.get((kind, culture)) or []
    if not donors:
        return None
    return donors[index % len(donors)]


def gate_position(donor, x, y, fallback=(-1.5, -1.5)):
    """Мировые координаты ворот для поселения в (x, y)."""
    if donor is None or not donor.gate_offset:
        return x + fallback[0], y + fallback[1]
    factor = SCALE.get(donor.kind, 1.0)
    return x + donor.gate_offset[0] * factor, y + donor.gate_offset[1] * factor


def dress(entity, donor):
    """Вставляет в нашу сущность модели донора, его поворот и масштаб."""
    if donor is None or donor.children is None:
        return False
    old = entity.find("children")
    if old is not None:
        entity.remove(old)
    entity.append(copy.deepcopy(donor.children))
    transform = entity.find("transform")
    if transform is not None:
        transform.set("rotation_euler", donor.rotation)
        factor = SCALE.get(donor.kind, 1.0)
        base = [float(v) for v in donor.scale.split(",")] if donor.scale else [1.0, 1.0, 1.0]
        if factor != 1.0 or donor.scale:
            transform.set("scale", ", ".join("%.3f" % (v * factor) for v in base))
    return True


# ---------------------------------------------------------------- логова разбойников
# Логова у нас — ванильные (те же id, другие координаты), но на карте их модели не было: доноры
# выше — только города, замки и деревни, а у сущности логова оставались одно имя и надпись
# (замечено пользователем 10.10.2026: «название есть, 3D-модели нет»). У ванили модель логова
# висит прямо на его сущности в Main_map: меш (worldmap_hideout_a/b, map_icon_bandit_hideout_b/d),
# тело для щелчка (bo_hideouts / bo_sphere_collider), масштаб ~0.6–0.8, у трёх — дочерние объекты.
# Переносим всё это на нашу сущность с тем же id; наклон по рельефу Кальрадии не берём, только
# поворот вокруг вертикали.
HIDEOUT_SCALE = 1.5     # как у поселений (SCALE): ванильные логова на нашей карте теряются


def load_hideouts(game=None):
    """{id логова: его game_entity из ванильной Main_map}."""
    _settlements, scene_path = _paths(game)
    result = {}
    for entity in ET.parse(scene_path).getroot().iter("game_entity"):
        name = entity.get("name") or ""
        if name.startswith("hideout_") and name not in result:
            result[name] = entity
    return result


def dress_hideout(entity, source):
    """Модель ванильного логова source на нашу сущность entity. True, если что-то перенесено."""
    if source is None:
        return False
    for tag in ("physics", "components", "children"):
        old = entity.find(tag)
        if old is not None:
            entity.remove(old)
    transform = entity.find("transform")
    # порядок дочерних элементов как у ванили: tags, transform, physics, components, children, scripts
    index = list(entity).index(transform) + 1 if transform is not None else len(entity)
    for tag in ("physics", "components", "children"):
        node = source.find(tag)
        if node is not None:
            entity.insert(index, copy.deepcopy(node))
            index += 1
    tags = entity.find("tags")
    if tags is not None and not any(t.get("name") == "wm_hideout" for t in tags):
        ET.SubElement(tags, "tag", {"name": "wm_hideout"})
    src_t = source.find("transform")
    if transform is not None and src_t is not None:
        rot = [float(v) for v in (src_t.get("rotation_euler") or "0,0,0").split(",")]
        transform.set("rotation_euler", "0.000, 0.000, %.3f" % rot[2])
        base = [float(v) for v in src_t.get("scale").split(",")] if src_t.get("scale") else [1.0, 1.0, 1.0]
        transform.set("scale", ", ".join("%.3f" % (v * HIDEOUT_SCALE) for v in base))
    return entity.find("components") is not None or entity.find("children") is not None
