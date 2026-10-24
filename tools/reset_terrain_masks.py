# Сброс масок слоёв рельефа в сцене: весь рельеф снова считается залитым только слоем 0.
#
#   python reset_terrain_masks.py <папка Module мода>
#
# Нужен в паре с откатом terrain.bin из резервной копии (terrain.bin.bak): там в каждом узле
# одна маска, и сцена должна говорить игре то же самое, иначе маски и слои не совпадут.
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
