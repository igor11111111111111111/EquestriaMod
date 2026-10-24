# Overview of the vanilla skins.xml structure: races, skin attributes, child elements and sample entries.
import sys
import xml.etree.ElementTree as ET

path = sys.argv[1]
root = ET.parse(path).getroot()
print("root:", root.tag, root.attrib)
for race in root:
    print("RACE", race.tag, race.attrib, "skins:", len(race))
    for skin in race:
        print("  SKIN", {k: v for k, v in skin.attrib.items()})
        for child in skin:
            items = list(child)
            sample = [ET.tostring(i, encoding="unicode").strip()[:220] for i in items[:2]]
            print(f"    <{child.tag}> attrs={child.attrib} children={len(items)}")
            for s in sample:
                print("       ", s.replace("\n", " "))
        break  # only the first skin in detail; for the rest, attributes
    for skin in list(race)[1:]:
        print("  SKIN", skin.attrib.get("name"), {k: skin.attrib[k] for k in ("gender", "mesh_maturity_type", "skeleton", "body_meta_mesh", "face_meta_mesh", "min_scale") if k in skin.attrib})
