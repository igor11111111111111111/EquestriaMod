# Compare the lengths of the appearance lists of the pony race and the human (they must match for the face editor).
# py tools/compare_race_lists.py <Native skins.xml> <pony_skins.xml>
import sys
import xml.etree.ElementTree as ET

native, pony_path = sys.argv[1], sys.argv[2]
human = next(r for r in ET.parse(native).getroot() if r.get("id") == "human")
pony = ET.parse(pony_path).getroot()[0]
LISTS = ("hair_meshes", "beard_meshes", "tattoo_materials", "eyebrow_meshes", "face_textures", "mouth_textures")
for ps, hs in zip(pony, human):
    cells = []
    for tag in LISTS:
        pe, he = ps.find(tag), hs.find(tag)
        mark = "" if len(pe) == len(he) else " !"
        named = sum(1 for c in pe if c.get("name")) if tag in LISTS[:3] else 0
        cells.append(f"{tag.split('_')[0]} {len(pe)}/{len(he)}{mark}" + (f" named={named}" if named else ""))
    print(f"{ps.get('name'):15} " + " | ".join(cells))
