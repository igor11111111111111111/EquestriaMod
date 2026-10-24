# World geometry: how to divide the land between the realms and where to put towns, castles and villages.
#
# The module knows nothing about names, clans and XML, only points on the map. Names and owners
# are handed out by make_world.py; in come the Equestria at War cities (assets/map/eq_map.json) and
# the list of realms, out goes the layout: what stands where and which village is bound to which fortress.
#
# Reference: the original Bannerlord campaign (measured from SandBox/ModuleData/settlements.xml):
#   fortress to fortress      minimum 16.9 m, median 30.9;
#   village to village        minimum  8.6 m, median 19.0;
#   village to fortress       minimum  8.3 m, median 19.6;
#   villages per fortress     1..4, median 2, none without villages;
#   village to its fortress   median 21.7 m;
#   per settlement            ~875 m² of land (we get ~950).
#
# Two tasks the module solves:
#   1) the realms' lands are roughly equal (strong ones slightly more, weak ones slightly less): an additively
#      weighted Voronoi from the capitals: for each land cell we find the nearest capital with a correction,
#      the corrections are tuned until the areas match the target shares;
#   2) settlements do not cluster and do not leave gaps: fortresses and villages are picked greedily
#      "farther from the already placed ones", and EaW cities are taken as ready points as long as they do not
#      get in the way of this; if there are too few, we invent new ones, if too many, the extra ones are dropped.
import math

import numpy as np

import equus_map

GRID = 4.0                  # land cell grid step, m
MIN_HEIGHT = 0.5            # below this is beach, no settlement is placed there

# Minimum gaps between settlements (as in vanilla, with a small margin)
GAP = {("fort", "fort"): 17.0, ("fort", "village"): 8.5, ("village", "village"): 8.0}
FORT_SPREAD = 26.0          # desired fortress spacing; if it does not work out, we go down to GAP
MAJOR_VALUE = 30.0          # a major city (including a canon one) is placed as a fortress and at minimum gap
FILL_REACH = 45.0           # land farther than this from a settlement counts as empty
VILLAGE_SLACK = 1.35        # how much the village quota may be exceeded to fill gaps
MIN_VILLAGES = {"town": 2, "castle": 1}
MAX_VILLAGES = 4            # as in vanilla
VILLAGE_REACH = 26.0        # beyond this a village is no longer counted as the fortress's "own"
BIND_REACH = 45.0           # at this distance a village can still be bound to a fortress
BORDER = 16.0               # margin from the map edge


def land_grid(step=GRID):
    """Land mask on a grid with step step: (mask, row numbers, column numbers)."""
    land = equus_map.land_map() & (equus_map.heights() > MIN_HEIGHT)
    n = land.shape[0]
    sub = max(1, int(round(step / (equus_map.MAP_SIZE / (n - 1)))))
    land = land[::sub, ::sub].copy()
    h, w = land.shape
    edge = int(round(BORDER / step))
    land[:edge], land[h - edge:], land[:, :edge], land[:, w - edge:] = False, False, False, False
    return land


MIN_ISLAND = 250            # cells; smaller islets do not take part in the settling
OFFSHORE = 45.0             # farther than this from the settled land a city counts as an island one


def land_cells(step=GRID):
    """Land cells where a settlement can be placed. Small islands are discarded: there is no land road
    there, lords and caravans will not reach such a settlement."""
    land = land_grid(step)
    big = np.zeros_like(land)
    for _kid, cells in _components(np.zeros(land.shape, np.int32), land):
        if len(cells) >= MIN_ISLAND:
            for j, i in cells:
                big[j, i] = True
    ys, xs = np.nonzero(big)
    return xs * step, ys * step


def _components(owner2d, land):
    """Connected pieces of land of one owner: [(owner, [(row, column), ...]), ...]."""
    h, w = owner2d.shape
    seen = np.zeros_like(land)
    parts = []
    for j in range(h):
        for i in range(w):
            if not land[j, i] or seen[j, i]:
                continue
            kid = owner2d[j, i]
            seen[j, i] = True
            stack = [(j, i)]
            cells = []
            while stack:
                cj, ci = stack.pop()
                cells.append((cj, ci))
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        nj, ni = cj + dj, ci + di
                        if 0 <= nj < h and 0 <= ni < w and land[nj, ni] and not seen[nj, ni] \
                                and owner2d[nj, ni] == kid:
                            seen[nj, ni] = True
                            stack.append((nj, ni))
            parts.append((kid, cells))
    return parts


# A scrap of land smaller than this (and smaller than the SMALL_SHARE fraction of the realm's holdings) counts
# as an enclave and goes to the neighbours.
SMALL_PATCH = 150
SMALL_SHARE = 0.15


def _stitch(owner2d, land, capital_cells):
    """Stitching enclaves: a small piece of land cut off from the rest of a realm's holdings and
    surrounded by foreign land goes to the neighbour with the longest common border. Large pieces
    (whole regions beyond foreign land) and the capital cell are not touched, nor are islands: they have no land
    neighbours, and the sea realm consists precisely of islands."""
    h, w = owner2d.shape
    moved = 0
    parts = _components(owner2d, land)
    total = {}
    for kid, cells in parts:
        total[kid] = total.get(kid, 0) + len(cells)
    for kid, cells in parts:
        if any(cell in capital_cells.get(kid, ()) for cell in cells):
            continue
        if len(cells) >= min(SMALL_PATCH, SMALL_SHARE * total.get(kid, 0)):
            continue
        neighbours = {}
        for cj, ci in cells:
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    nj, ni = cj + dj, ci + di
                    if 0 <= nj < h and 0 <= ni < w and land[nj, ni] and owner2d[nj, ni] != kid:
                        neighbours[int(owner2d[nj, ni])] = neighbours.get(int(owner2d[nj, ni]), 0) + 1
        if not neighbours:
            continue                     # an island: leave it as it is
        new_kid = max(neighbours, key=neighbours.get)
        for cj, ci in cells:
            owner2d[cj, ci] = new_kid
        moved += len(cells)
    return moved


def partition(anchors, weights, cells, log=print):
    """Divides the land cells between the realms so that the areas relate as weights.

    Additively weighted Voronoi: a cell goes to the realm whose anchor cities are closer
    (with a correction); the corrections are tuned iteratively until the areas match the targets.
    A realm has several anchor cities: these are the canon cities of its lands, and they hold the borders
    where lore puts them, not where a compass from the capital would.

    After each tuning pass the enclaves are stitched (see _stitch), and the tuning continues with them:
    this way the realms get both their share of land and whole holdings without scraps overseas."""
    x, y = cells
    w = np.asarray(weights, float)
    target = w / w.sum() * len(x)
    d = np.empty((len(x), len(anchors)), np.float32)
    for i, points in enumerate(anchors):
        P = np.asarray(points, float).reshape(-1, 2)
        d[:, i] = np.hypot(x[:, None] - P[None, :, 0], y[:, None] - P[None, :, 1]).min(1)

    # a grid of exactly the cells we were given (without the discarded islets)
    ys_idx = np.rint(y / GRID).astype(int)
    xs_idx = np.rint(x / GRID).astype(int)
    land = np.zeros((ys_idx.max() + 2, xs_idx.max() + 2), bool)
    land[ys_idx, xs_idx] = True
    # the capital cell: the piece of land where the capital stands is the realm's core holdings, they are not
    # taken away. Everything else that turned out cut off goes to the neighbours, so that a realm
    # does not own scraps beyond foreign lands (lords simply will not reach them).
    keep_cells = {}
    for i, points in enumerate(anchors):
        ax, ay = np.asarray(points, float).reshape(-1, 2)[0]
        j = int(np.argmin((x - ax) ** 2 + (y - ay) ** 2))
        keep_cells[i] = {(int(ys_idx[j]), int(xs_idx[j]))}

    bias = np.zeros(len(anchors))
    owner = d.argmin(1)
    err = np.ones(len(anchors))
    for _step in range(200):            # rough tuning without stitching: it is cheap
        owner = (d - bias).argmin(1)
        area = np.bincount(owner, minlength=len(anchors)).astype(float)
        err = (target - area) / target
        if np.abs(err).max() < 0.015:
            break
        bias += err * 5.0
    moved = 0
    for _round in range(12):            # tuning together with enclave stitching
        owner = (d - bias).argmin(1)
        owner2d = np.full(land.shape, -1, np.int32)
        owner2d[ys_idx, xs_idx] = owner
        moved = _stitch(owner2d, land, keep_cells)
        owner = owner2d[ys_idx, xs_idx]
        area = np.bincount(owner, minlength=len(anchors)).astype(float)
        err = (target - area) / target
        if np.abs(err).max() < 0.04:
            break
        bias += err * 4.0
    log("земли держав поделены: отклонение от цели не больше %.1f%%, анклавов сшито %d клеток"
        % (100 * np.abs(err).max(), moved))
    return owner


def targets(weights, base):
    """How many towns/castles/villages each realm is due (by its strength)."""
    w = np.asarray(weights, float)
    share = w / w.mean()
    out = []
    for s in share:
        out.append({kind: max(1, int(round(n * s))) for kind, n in base.items()})
    return out


class _Board:
    """Already placed settlements: checking gaps and distances to land cells."""

    def __init__(self, cells):
        self.x, self.y = cells
        self.dist = np.full(len(self.x), np.inf)   # to the nearest settlement of any realm
        self.points = []                           # (x, y, group)

    def add(self, x, y, group):
        self.points.append((x, y, group))
        np.minimum(self.dist, np.hypot(self.x - x, self.y - y), out=self.dist)

    def free(self, x, y, group):
        for px, py, pg in self.points:
            gap = GAP[tuple(sorted((group, pg)))]
            if (x - px) ** 2 + (y - py) ** 2 < gap * gap:
                return False
        return True

    def ok(self, x, y, group, extra=0.0):
        """Whether a point is suitable: solid land, inside the map, gaps respected."""
        if not (BORDER < x < equus_map.MAP_SIZE - BORDER and BORDER < y < equus_map.MAP_SIZE - BORDER):
            return False
        if not self.free(x, y, group):
            return False
        if extra and any((x - px) ** 2 + (y - py) ** 2 < extra * extra
                         for px, py, pg in self.points if pg == group):
            return False
        return equus_map.solid_ground(x, y)

    def settle(self, x, y, group, limit=24.0):
        """The nearest suitable point to (x, y) (along a spiral), or None."""
        r = 0.0
        while r <= limit:
            steps = 1 if r == 0 else max(8, int(2 * math.pi * r / 1.5))
            for k in range(steps):
                a = 2 * math.pi * k / steps
                nx, ny = x + r * math.cos(a), y + r * math.sin(a)
                if self.ok(nx, ny, group):
                    return round(nx, 1), round(ny, 1)
            r += 1.5
        return None


def plan(kingdoms, cities, weights, base, log=print, pinned=frozenset()):
    """World layout.

    kingdoms: [{"kingdom": id, "capital_xy": (x, y)}], weights: realm strength,
    cities: EaW cities (name, x, y, value, owner), base: the settlement quota of an average realm.

    Returns {realm id: {"town": [...], "castle": [...], "village": [...]}}, where an entry is
    {"x", "y", "city": the source EaW city or None, "bound": (kind, number) for a village}."""
    cells = land_cells()
    cx, cy = cells
    owner = partition([k.get("anchors") or [k["capital_xy"]] for k in kingdoms], weights, cells, log)
    want = targets(weights, base)
    board = _Board(cells)
    result = {k["kingdom"]: {"town": [], "castle": [], "village": []} for k in kingdoms}

    # The Equestria at War cities stand where that map placed them, but the terrain has since
    # been redone: some points ended up under water or on a shoal. Such a city is moved to
    # the nearest suitable land cell. If it is far away (a city on an islet with no
    # land road), the city does not take part in the settling, and its name goes to a new
    # settlement on the mainland.
    moved = off = 0
    fixed = []
    for c in cities:
        if c["name"] in pinned:      # the city was moved by hand: its point is not touched
            fixed.append(c)
            continue
        j = int(np.argmin((cx - c["x"]) ** 2 + (cy - c["y"]) ** 2))
        d = math.hypot(cx[j] - c["x"], cy[j] - c["y"])
        if d > OFFSHORE:
            off += 1
            continue
        if d > GRID:
            c = dict(c, x=float(cx[j]), y=float(cy[j]))
            moved += 1
        fixed.append(c)
    cities = fixed
    log("города карты EaW: %d, из них сдвинуто на сушу %d, отброшено островных %d"
        % (len(cities), moved, off))

    # which realm got each EaW city: by the owner of the nearest land cell
    city_owner = {}
    for c in cities:
        j = int(np.argmin((cx - c["x"]) ** 2 + (cy - c["y"]) ** 2))
        city_owner[c["name"]] = int(owner[j])
    # anchor cities stay with their realm, even if the border passed nearby differently:
    # Canterlot cannot turn out to be a dragon city, nor the Crystal Peak an Equestrian one
    for i, k in enumerate(kingdoms):
        for name in k.get("anchor_names", ()):
            if name in city_owner:
                city_owner[name] = i

    # capitals are placed first, so that they do not shift because of other gaps
    by_name = {c["name"]: c for c in cities}
    capitals = []
    for i, k in enumerate(kingdoms):
        c = by_name.get(k.get("capital"))
        x, y = (c["x"], c["y"]) if c else k["capital_xy"]
        spot = board.settle(x, y, "fort", limit=30.0)
        if spot is None:
            raise SystemExit("столице %s негде встать" % k["kingdom"])
        board.add(spot[0], spot[1], "fort")
        entry = {"x": spot[0], "y": spot[1], "city": c}
        result[k["kingdom"]]["town"].append(entry)
        capitals.append(entry)
        if c:
            city_owner[c["name"]] = i

    def region(i):
        m = owner == i
        return cx[m], cy[m]

    def emptiest(i, group, need=0.0):
        """The emptiest point of region i suitable for a settlement."""
        m = owner == i
        if not m.any():
            return None
        order = np.argsort(-board.dist[m])
        rx, ry = cx[m], cy[m]
        for j in order[:400]:
            if need and board.dist[m][j] < need:
                break
            spot = board.settle(float(rx[j]), float(ry[j]), group, limit=8.0)
            if spot:
                return spot
        return None

    # ---------------------------------------------------------------- fortresses
    for i, k in enumerate(kingdoms):
        kid = k["kingdom"]
        spots = result[kid]
        need_forts = want[i]["town"] + want[i]["castle"]
        mine = sorted((c for c in cities if city_owner.get(c["name"]) == i
                       and not any(e["city"] is c for e in spots["town"])),
                      key=lambda c: -c["value"])
        forts = list(spots["town"])   # the capital is already placed
        for spread in (FORT_SPREAD, GAP[("fort", "fort")]):
            for c in mine:
                if len(forts) >= need_forts:
                    break
                if any(e["city"] is c for e in forts):
                    continue
                # spacing is no obstacle for a major city: Cloudsdale stands 21 m from Ponyville,
                # and by lore that is right: both cities are real
                need = GAP[("fort", "fort")] if c["value"] >= MAJOR_VALUE else spread
                if not board.ok(c["x"], c["y"], "fort", extra=need):
                    continue
                board.add(c["x"], c["y"], "fort")
                entry = {"x": round(c["x"], 1), "y": round(c["y"], 1), "city": c}
                forts.append(entry)
            if len(forts) >= need_forts:
                break
        invented = 0
        while len(forts) < need_forts:
            spot = emptiest(i, "fort")
            if spot is None:
                log("державе %s не хватило места под крепости (%d из %d)"
                    % (kid, len(forts), need_forts))
                break
            board.add(spot[0], spot[1], "fort")
            forts.append({"x": spot[0], "y": spot[1], "city": None})
            invented += 1
        # the capital is always the first town, then by importance
        rest = sorted(forts[1:], key=lambda e: -(e["city"]["value"] if e["city"] else 0))
        ordered = forts[:1] + rest
        spots["town"] = ordered[:want[i]["town"]]
        spots["castle"] = ordered[want[i]["town"]:]
        k["_invented_forts"] = invented

    # ---------------------------------------------------------------- villages
    for i, k in enumerate(kingdoms):
        kid = k["kingdom"]
        spots = result[kid]
        forts = [("town", n, e) for n, e in enumerate(spots["town"])] + \
                [("castle", n, e) for n, e in enumerate(spots["castle"])]
        used_cities = {id(e["city"]) for e in spots["town"] + spots["castle"] if e["city"]}
        pool = [c for c in cities if city_owner.get(c["name"]) == i and id(c) not in used_cities]
        want_v = want[i]["village"]
        limit_v = int(want_v * VILLAGE_SLACK)
        placed = []

        def put(x, y, city):
            board.add(x, y, "village")
            entry = {"x": round(x, 1), "y": round(y, 1), "city": city}
            placed.append(entry)
            return entry

        # Every fortress must have its own village, and definitely nearby: we take the nearest
        # suitable city, but no farther than VILLAGE_REACH, otherwise we place a new village in a ring
        # around the fortress. Otherwise a moved city's "own" villages stay a hundred metres away.
        for kind, _n, fort in forts:
            for _ in range(MIN_VILLAGES[kind]):
                near = sorted(pool, key=lambda c: (c["x"] - fort["x"]) ** 2 + (c["y"] - fort["y"]) ** 2)
                spot, chosen = None, None
                for c in near[:12]:
                    if math.hypot(c["x"] - fort["x"], c["y"] - fort["y"]) > VILLAGE_REACH:
                        break
                    if board.ok(c["x"], c["y"], "village"):
                        spot, chosen = (c["x"], c["y"]), c
                        break
                if spot is None:
                    # each fortress has its own starting angle, otherwise all the villages line up
                    # on one and the same side
                    start = (fort["x"] * 7.3 + fort["y"] * 3.1 + len(placed) * 2.0) % (2 * math.pi)
                    for r in (16.0, 20.0, 24.0):
                        a = 0.0
                        while a < 2 * math.pi and spot is None:
                            nx = fort["x"] + r * math.cos(start + a)
                            ny = fort["y"] + r * math.sin(start + a)
                            spot = board.settle(nx, ny, "village", limit=6.0)
                            a += math.pi / 6
                        if spot:
                            break
                if spot is None:
                    continue
                if chosen is not None:
                    pool.remove(chosen)
                put(spot[0], spot[1], chosen)

        # the remaining villages: greedily "farther from the already placed ones", preferring EaW cities
        while len(placed) < want_v:
            best_city, best_d = None, -1.0
            for c in pool:
                d = min((c["x"] - px) ** 2 + (c["y"] - py) ** 2 for px, py, _g in board.points) ** 0.5
                if d > best_d and board.ok(c["x"], c["y"], "village"):
                    best_city, best_d = c, d
            m = owner == i
            free_d = board.dist[m].max() if m.any() else 0.0
            if best_city is not None and best_d >= 0.75 * free_d:
                pool.remove(best_city)
                put(best_city["x"], best_city["y"], best_city)
                continue
            spot = emptiest(i, "village")
            if spot is None:
                break
            put(spot[0], spot[1], None)

        # filling gaps: while the region has land farther than FILL_REACH from anything alive
        while len(placed) < limit_v:
            m = owner == i
            if not m.any() or board.dist[m].max() <= FILL_REACH:
                break
            spot = emptiest(i, "village", need=FILL_REACH)
            if spot is None:
                break
            put(spot[0], spot[1], None)

        # binding to fortresses: the nearest own one, but no more than MAX_VILLAGES per one
        counts = {(kind, n): 0 for kind, n, _e in forts}
        for entry in sorted(placed, key=lambda e: min(
                (e["x"] - f["x"]) ** 2 + (e["y"] - f["y"]) ** 2 for _k, _n, f in forts)):
            order = sorted(forts, key=lambda f: (f[2]["x"] - entry["x"]) ** 2 + (f[2]["y"] - entry["y"]) ** 2)
            # the nearest fortress with room, but only among close ones: better a fifth village at a neighbour
            # than a village bound to a fortress a hundred metres away
            close = [f for f in order
                     if math.hypot(f[2]["x"] - entry["x"], f[2]["y"] - entry["y"]) <= BIND_REACH]
            pick = next((f for f in close if counts[(f[0], f[1])] < MAX_VILLAGES), order[0])
            entry["bound"] = (pick[0], pick[1])
            counts[(pick[0], pick[1])] += 1
        # a fortress without villages lives half-starved in the game (vanilla has none like that), so from a neighbour
        # with a surplus we take the village nearest to it
        for kind, n, fort in forts:
            if counts[(kind, n)]:
                continue
            donors = [e for e in placed if counts[e["bound"]] > 1
                      and math.hypot(e["x"] - fort["x"], e["y"] - fort["y"]) <= BIND_REACH]
            if not donors:
                continue
            near = min(donors, key=lambda e: (e["x"] - fort["x"]) ** 2 + (e["y"] - fort["y"]) ** 2)
            counts[near["bound"]] -= 1
            near["bound"] = (kind, n)
            counts[(kind, n)] = 1
        spots["village"] = placed
        log("%s: городов %d, замков %d, деревень %d (придумано крепостей %d, деревень %d)"
            % (kid, len(spots["town"]), len(spots["castle"]), len(placed),
               k.pop("_invented_forts", 0), sum(1 for e in placed if e["city"] is None)))

    return result
