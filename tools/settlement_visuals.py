# Appearance of settlements on the world map: we take ready-made models from vanilla settlements.
#
# Every vanilla town, castle and village in Main_map has an entity with child objects:
# models per development level (l1..l3, raided village), a physics body (bo_town, bo_castle,
# bo_village), a gate point (town_gate / gate_position) and siege spots. The Town Entity
# Manager script switches on the right level by itself.
#
# For our settlement we pick a "donor": a vanilla settlement of the same kind and the same culture
# (our culture ids are vanilla: empire = Equestria etc.), and copy its child objects,
# rotation and scale. The gate is placed as at the donor: the gate offset from the centre in the vanilla
# settlements.xml is written in world coordinates and matches the model at the same rotation.
#
# The donor choice depends only on the kind, culture and settlement number, so make_world.py
# (gates) and make_map_entities.py (models) get the same donor.
import copy
import os
import re
import xml.etree.ElementTree as ET

GAME = r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
KINDS = ("town", "castle", "village")
MAX_ROOT_CHILDREN = 30
# How many times larger settlements are than vanilla ones. The models are the same as on the Calradia map, but on
# our map they got lost against the forest. The gate offset is multiplied by the same factor, otherwise parties
# would enter the town not through the model's gate. On the 1024 m map EaW towns are in places 13-20 m
# apart, so not ×2, as on the small map, but ×1.5.
SCALE = {"town": 1.5, "castle": 1.5, "village": 1.5}
# Cultures without their own settlement models in the game take them from a vanilla one
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
        self.gate_offset = gate_offset      # (dx, dy) or None if there is no gate
        self.children = None                # the <children> element from the scene
        self.rotation = "0.000, 0.000, 0.000"
        self.scale = None


def load_donors(game=None, with_scene=True):
    """Vanilla settlements: {(kind, culture): [Donor, ...]} in id order, plus {id: Donor}."""
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

    # Donors without a usable model are dropped from the lists: make_world.py and make_map_entities.py
    # must see identical lists, so the scene is read in both cases.
    if with_scene:
        for entity in ET.parse(scene_path).getroot().iter("game_entity"):
            donor = by_id.get(entity.get("name"))
            if donor is None or donor.children is not None:
                continue
            children = entity.find("children")
            if children is None or not len(children):
                continue
            # Only donors of the usual structure are taken: a town has a bo_town body at the root, a
            # castle bo_castle, and the models are grouped by levels (town_EN2 has nine objects at the
            # root). There are composite settlements: town_EN1 has 334 separate houses, stones and
            # decals at the root; such a model is not visible at all in our game.
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
    """Donor for our settlement or None. Bandit hideouts are vanilla and take their own entity."""
    match = OUR_ID.match(settlement_id)
    if match is None:
        return by_id.get(settlement_id)
    kind, culture, index = match.group(1), DONOR_CULTURE.get(match.group(2), match.group(2)), int(match.group(3))
    donors = by_key.get((kind, culture)) or []
    if not donors:
        return None
    return donors[index % len(donors)]


def gate_position(donor, x, y, fallback=(-1.5, -1.5)):
    """World coordinates of the gate for a settlement at (x, y)."""
    if donor is None or not donor.gate_offset:
        return x + fallback[0], y + fallback[1]
    factor = SCALE.get(donor.kind, 1.0)
    return x + donor.gate_offset[0] * factor, y + donor.gate_offset[1] * factor


def dress(entity, donor):
    """Inserts the donor's models, rotation and scale into our entity."""
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


# ---------------------------------------------------------------- bandit hideouts
# Our hideouts are vanilla ones (the same ids, other coordinates), but their model was missing on the map:
# the donors above are only towns, castles and villages, and the hideout entity was left with only a name
# and a label (noticed by the user 10.10.2026: "the name is there, no 3D
# model"). In vanilla the hideout model hangs right on its entity in Main_map: a mesh (worldmap_hideout_a/b, map_icon_bandit_hideout_b/d),
# a click body (bo_hideouts / bo_sphere_collider), scale ~0.6–0.8, three of them have child objects.
# We move all this onto our entity with the same id; the tilt along the Calradia terrain is not taken, only
# the rotation about the vertical.
HIDEOUT_SCALE = 1.5     # as for settlements (SCALE): vanilla hideouts get lost on our map


def load_hideouts(game=None):
    """{hideout id: its game_entity from the vanilla Main_map}."""
    _settlements, scene_path = _paths(game)
    result = {}
    for entity in ET.parse(scene_path).getroot().iter("game_entity"):
        name = entity.get("name") or ""
        if name.startswith("hideout_") and name not in result:
            result[name] = entity
    return result


def dress_hideout(entity, source):
    """The model of the vanilla hideout source onto our entity. True if something was transferred."""
    if source is None:
        return False
    for tag in ("physics", "components", "children"):
        old = entity.find(tag)
        if old is not None:
            entity.remove(old)
    transform = entity.find("transform")
    # child element order as in vanilla: tags, transform, physics, components, children, scripts
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
