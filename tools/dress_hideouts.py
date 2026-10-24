# -*- coding: utf-8 -*-
"""Bandit hideout models on the world map: edits the finished scene without a full regeneration.

The full scene build (make_map_entities.py) now itself gives hideouts the models of their vanilla
counterparts (settlement_visuals.dress_hideout). This script does the same to an already built
Module/SceneObj/Main_map/scene.xscene, so the whole map need not be regenerated, and appends the
hideout meshes to references.txt (without an entry there the scene does not load the model).

Run: py tools/dress_hideouts.py [the mod's Module folder] [the game folder]
The editor must be closed while it runs.
"""
import os
import shutil
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settlement_visuals  # noqa: E402

MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
GAME = sys.argv[2] if len(sys.argv) > 2 else None
SCENE = os.path.join(MOD, "SceneObj", "Main_map", "scene.xscene")
REFERENCES = os.path.join(MOD, "SceneObj", "Main_map", "references.txt")


def log(*a):
    print("[hideouts]", *a, flush=True)


hideouts = settlement_visuals.load_hideouts(GAME)
log("ванильных логов:", len(hideouts))
tree = ET.parse(SCENE)
root = tree.getroot()
entities = root.find(".//entities")
dressed, missing, meshes = 0, [], set()
for entity in list(entities):
    name = entity.get("name") or ""
    if not name.startswith("hideout_"):
        continue
    if settlement_visuals.dress_hideout(entity, hideouts.get(name)):
        dressed += 1
    else:
        missing.append(name)
    for component in entity.iter("meta_mesh_component"):
        if component.get("name"):
            meshes.add("mesh " + component.get("name"))
log("логов с моделью: %d, без модели: %d %s" % (dressed, len(missing), ", ".join(missing[:10])))

backup = SCENE + ".before_hideouts"
if not os.path.exists(backup):
    shutil.copy2(SCENE, backup)
    log("резервная копия", backup)
ET.indent(root, space="\t")
tree.write(SCENE, encoding="utf-8", xml_declaration=True)
log("записано", SCENE)

entries = set()
if os.path.exists(REFERENCES):
    with open(REFERENCES, encoding="utf-8") as f:
        entries = {line.strip() for line in f.read().splitlines()[1:] if line.strip()}
added = meshes - entries
entries |= meshes
ordered = sorted(entries)
with open(REFERENCES, "w", encoding="utf-8", newline="\n") as f:
    f.write("%d\n%s\n" % (len(ordered), "\n".join(ordered)))
log("references.txt: добавлено %d (%s), всего %d" % (len(added), ", ".join(sorted(added)), len(ordered)))
