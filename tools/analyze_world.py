# Разбор текущего расклада мира: сколько у кого поселений, как они разбросаны и где пусто.
#
#   py tools/analyze_world.py [папка Module мода]
#
# Считает по сгенерированным XML (equestria_settlements.xml + equestria_clans.xml):
#   - города/замки/деревни каждой державы и её «вес» (город 3, замок 2, деревня 1);
#   - расстояния до ближайшего соседа (кучкование) и до ближайшего поселения из случайных точек
#     суши (пустые места);
#   - то же самое по ванильной карте Bannerlord — для сравнения «как в оригинальной игре».
import collections
import math
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402

MOD = sys.argv[1] if len(sys.argv) > 1 else "Module"
GAME = r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
WEIGHT = {"town": 3.0, "castle": 2.0, "village": 1.0}


def kind_of(s):
    comp = s.find("Components")
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


def read(path, kingdom_of_clan=None):
    """[(вид, x, y, держава)] из settlements.xml. У деревни владелец — крепость, к которой она
    приписана (bound), поэтому владельцев разбираем в два прохода."""
    raw, bound = [], {}
    for s in ET.parse(path).getroot():
        kind = kind_of(s)
        if kind is None or kind == "hideout" or s.get("posX") is None:
            continue
        owner = (s.get("owner") or "").replace("Faction.", "")
        village = s.find("Components/Village")
        if village is not None:
            bound[s.get("id")] = (village.get("bound") or "").replace("Settlement.", "")
        raw.append((s.get("id"), kind, float(s.get("posX")), float(s.get("posY")), owner))
    owners = {sid: owner for sid, _k, _x, _y, owner in raw}
    out = []
    for sid, kind, x, y, owner in raw:
        if not owner and sid in bound:
            owner = owners.get(bound[sid], "")
        kingdom = kingdom_of_clan.get(owner, owner) if kingdom_of_clan else owner
        out.append((kind, x, y, kingdom))
    return out


def clan_to_kingdom(path):
    out = {}
    for clan in ET.parse(path).getroot().iter("Faction"):
        kid = (clan.get("super_faction") or clan.get("kingdom") or "").replace("Kingdom.", "").replace("Faction.", "")
        out[clan.get("id")] = kid or clan.get("id")
    return out


def spacing(points):
    p = np.array([[x, y] for _k, x, y, _o in points], float)
    d = np.hypot(p[:, None, 0] - p[None, :, 0], p[:, None, 1] - p[None, :, 1])
    np.fill_diagonal(d, np.inf)
    near = d.min(1)
    return near


def emptiness(points, land_mask, map_size, step=8.0):
    """Распределение расстояния «от случайной точки суши до ближайшего поселения»."""
    p = np.array([[x, y] for _k, x, y, _o in points], float)
    n = land_mask.shape[0]
    ys, xs = np.nonzero(land_mask[::max(1, int(n * step / map_size)), ::max(1, int(n * step / map_size))])
    scale = map_size / (n - 1) * max(1, int(n * step / map_size))
    pts = np.stack([xs * scale, ys * scale], 1)
    d = np.hypot(pts[:, None, 0] - p[None, :, 0], pts[:, None, 1] - p[None, :, 1]).min(1)
    return d


def report(title, points, land_mask, map_size):
    print("=" * 70)
    print(title)
    kinds = collections.Counter(k for k, _x, _y, _o in points)
    print("  поселений: %s, всего %d" % (dict(kinds), len(points)))
    by_kingdom = collections.defaultdict(collections.Counter)
    for kind, _x, _y, owner in points:
        by_kingdom[owner][kind] += 1
    rows = []
    for owner, c in by_kingdom.items():
        weight = sum(WEIGHT[k] * n for k, n in c.items())
        rows.append((weight, owner, c))
    rows.sort(reverse=True)
    print("  державы (вес = 3*город + 2*замок + деревня):")
    for weight, owner, c in rows:
        print("    %-28s вес %5.1f  город %2d  замок %2d  деревня %2d"
              % (owner, weight, c["town"], c["castle"], c["village"]))
    if rows:
        w = [r[0] for r in rows]
        print("    разброс веса: max/min = %.2f, среднее %.1f" % (max(w) / min(w), sum(w) / len(w)))
    near = spacing(points)
    print("  до ближайшего соседа, м: мин %.1f, 10%% %.1f, медиана %.1f, 90%% %.1f, макс %.1f"
          % (near.min(), np.percentile(near, 10), np.median(near), np.percentile(near, 90), near.max()))
    print("  ближе 8 м: %d пар" % int((near < 8).sum()))
    if land_mask is not None:
        d = emptiness(points, land_mask, map_size)
        print("  от точки суши до ближайшего поселения, м: медиана %.1f, 90%% %.1f, макс %.1f"
              % (np.median(d), np.percentile(d, 90), d.max()))
        print("  доля суши дальше 40 м от любого поселения: %.1f%%" % (100.0 * (d > 40).mean()))


ours = read(os.path.join(MOD, "ModuleData", "equestria_settlements.xml"),
            clan_to_kingdom(os.path.join(MOD, "ModuleData", "equestria_clans.xml")))
# ванильные записи, уведённые в угол, в наш расклад не входят
ours = [p for p in ours if p[3].startswith("kingdom_")]
report("НАШ МИР (Эквус, карта %.0f м)" % equus_map.MAP_SIZE, ours,
       equus_map.land_map() & (equus_map.heights() > 0.4), equus_map.MAP_SIZE)

van = os.path.join(GAME, "Modules", "SandBox", "ModuleData", "settlements.xml")
if os.path.exists(van):
    clans = os.path.join(GAME, "Modules", "SandBox", "ModuleData", "spkingdoms.xml")
    kingdom_of = {}
    cl = os.path.join(GAME, "Modules", "SandBox", "ModuleData", "spclans.xml")
    if os.path.exists(cl):
        kingdom_of = clan_to_kingdom(cl)
    report("ВАНИЛЬНЫЙ КАЛРАДИЙ", read(van, kingdom_of), None, 1000.0)
