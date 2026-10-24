# Reset the terrain layer masks in the scene: the whole terrain again counts as filled with layer 0 only.
#
#   python reset_terrain_masks.py <the mod's Module folder>
#
# Used together with restoring terrain.bin from the backup (terrain.bin.bak): there every node has
# one mask, and the scene must tell the game the same, otherwise the masks and layers will not match.
import os
import sys
import xml.etree.ElementTree as ET

scene = os.path.join(sys.argv[1], "SceneObj", "Main_map", "scene.xscene")
tree = ET.parse(scene)
root = tree.getroot()
for node in root.find(".//terrain").find("nodes").findall("node"):
    for season in ("summer", "fall", "winter", "spring"):
        node.set("layer_is_used_mask_%s" % season, "1")
    levels = node.find(".//variable[@name='weightmap_levels']")
    for variable in levels.findall("variable"):
        variable.set("value", "6" if variable.get("layer") == "0" else "0")
ET.indent(root, space="\t")
tree.write(scene, encoding="utf-8", xml_declaration=True)
print("[terrain] маски слоёв сброшены: везде только слой 0")
