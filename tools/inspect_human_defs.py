# Which Monster and action_set are defined for the human in all game modules.
import glob
import os
import sys
import xml.etree.ElementTree as ET

modules = sys.argv[1]
for path in sorted(glob.glob(os.path.join(modules, "*", "ModuleData", "**", "*.xml"), recursive=True)):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        continue
    rel = os.path.relpath(path, modules)
    monsters = [m for m in root.iter("Monster") if m.get("id", "").startswith("human")]
    for m in monsters:
        print(f"MONSTER {rel}: id={m.get('id')} base={m.get('base_monster')} action_set={m.get('action_set')} "
              f"female={m.get('female_action_set')} usage={m.get('monster_usage')} attrs={len(m.attrib)}")
    sets = [a for a in root.iter("action_set") if a.get("id", "").startswith("as_human")]
    if sets:
        print(f"ACTION_SETS {rel}: {len(sets)}")
        print("  ids:", " ".join(a.get("id") for a in sets))
        print("  skeleton attrs:", sorted({a.get('skeleton') for a in sets}, key=str), "base_set used:", sum(1 for a in sets if a.get('base_set')))
