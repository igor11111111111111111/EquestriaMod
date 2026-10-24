# Settlements for our world map.
#
# Vanilla settlements cannot be deleted: they live in the SandBox module, which the campaign depends on.
# But an entry with the same id can be overridden. So we take the vanilla settlements.xml, give our
# settlements Equestrian names, culture and owner, and move the rest into a corner of the map so they
# do not get in the way and, most importantly, do not end up outside the terrain (that crashed the game).
#
# py tools/make_settlements.py <game Modules folder> <mod Module folder> [map size in metres]
import os
import sys
import xml.etree.ElementTree as ET

GAME_MODULES, MOD = sys.argv[1], sys.argv[2]
MAP_SIZE = float(sys.argv[3]) if len(sys.argv) > 3 else 400.0
SRC = os.path.join(GAME_MODULES, "SandBox", "ModuleData", "settlements.xml")
OUT = os.path.join(MOD, "ModuleData", "equestria_settlements.xml")

CULTURE = "Culture.equestria"
OWNER = "Faction.clan_equestria_royal"

# Our settlements: type, name, fraction of the map size (x, y). The fractions are the same as in
# make_map_heightmap.py, so a town lands on a pre-flattened site.
OURS = [
    ("town", "Кантерлот", 0.38, 0.42),
    ("town", "Понивилль", 0.58, 0.58),
    ("castle", "Кантерлотская цитадель", 0.34, 0.36),
    ("village", "Сладкое Яблоко", 0.62, 0.52),
    ("village", "Сахарный Уголок", 0.54, 0.64),
    ("village", "Тихий Дол", 0.44, 0.50),
]
# Where the rest are sent: a dense grid in a corner of the land, 4 metre step
PARK_ORIGIN = (0.44, 0.28)
PARK_STEP = 2.0


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


tree = ET.parse(SRC)
root = tree.getroot()
settlements = list(root)
by_kind = {}
for s in settlements:
    by_kind.setdefault(kind_of(s), []).append(s)
print("ванильных поселений:", {k: len(v) for k, v in by_kind.items()})

used = set()
for kind, name, fx, fy in OURS:
    pool = [s for s in by_kind.get(kind, []) if s.get("id") not in used]
    if not pool:
        print(f"нет свободного поселения типа {kind} для {name}")
        continue
    s = pool[0]
    used.add(s.get("id"))
    x, y = fx * MAP_SIZE, fy * MAP_SIZE
    s.set("name", "{=eq_settlement_%s}%s" % (s.get("id"), name))
    s.set("culture", CULTURE)
    s.set("owner", OWNER)
    s.set("posX", f"{x:.3f}")
    s.set("posY", f"{y:.3f}")
    s.set("gate_posX", f"{x + 1.5:.3f}")
    s.set("gate_posY", f"{y + 1.5:.3f}")
    if "text" in s.attrib:
        del s.attrib["text"]
    print(f"{name}: {s.get('id')} ({kind}) -> {x:.1f}, {y:.1f}")

# the rest go to the corner in a dense grid; all coordinates stay inside the map
ox, oy = PARK_ORIGIN[0] * MAP_SIZE, PARK_ORIGIN[1] * MAP_SIZE
per_row = 25
parked = 0
for s in settlements:
    if s.get("id") in used:
        continue
    x = ox + (parked % per_row) * PARK_STEP
    y = oy + (parked // per_row) * PARK_STEP
    s.set("posX", f"{x:.3f}")
    s.set("posY", f"{y:.3f}")
    s.set("gate_posX", f"{x + 1.0:.3f}")
    s.set("gate_posY", f"{y + 1.0:.3f}")
    parked += 1
print("уведено в угол:", parked)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
ET.indent(root, space="\t")
tree.write(OUT, encoding="utf-8", xml_declaration=True)
print("written", OUT)
