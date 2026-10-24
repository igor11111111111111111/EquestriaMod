# Геометрия мира: как поделить сушу между державами и где стоять городам, замкам и деревням.
#
# Модуль ничего не знает про имена, кланы и XML — только точки на карте. Имена и владельцев
# раздаёт make_world.py, сюда приходят города Equestria at War (assets/map/eq_map.json) и
# список держав, обратно — раскладка: что где стоит и какая деревня к какой крепости приписана.
#
# Ориентир — оригинальная кампания Bannerlord (замерено по SandBox/ModuleData/settlements.xml):
#   крепость до крепости      минимум 16.9 м, медиана 30.9;
#   деревня до деревни        минимум  8.6 м, медиана 19.0;
#   деревня до крепости       минимум  8.3 м, медиана 19.6;
#   деревень у крепости       1..4, медиана 2, без деревень нет ни одной;
#   деревня до своей крепости медиана 21.7 м;
#   на поселение приходится   ~875 м² суши (у нас выходит ~950).
#
# Две задачи, которые решает модуль:
#   1) земли держав примерно равны (сильные чуть больше, слабые чуть меньше) — аддитивно
#      взвешенный Вороной от столиц: каждой клетке суши ищем ближайшую столицу с поправкой,
#      поправки подгоняются, пока площади не сойдутся с целевыми долями;
#   2) поселения не кучкуются и не оставляют пустот — крепости и деревни выбираются жадно
#      «подальше от уже поставленных», а города EaW берутся как готовые точки, пока они этому
#      не мешают; не хватило — придумываем новые, слишком много — лишние отбрасываются.
import math

import numpy as np

import equus_map

GRID = 4.0                  # шаг сетки клеток суши, м
MIN_HEIGHT = 0.5            # ниже — пляж, поселение туда не ставим

# Минимальные зазоры между поселениями (как в ванили, с небольшим запасом)
GAP = {("fort", "fort"): 17.0, ("fort", "village"): 8.5, ("village", "village"): 8.0}
FORT_SPREAD = 26.0          # желаемый разбег крепостей; если не выходит, опускаемся до GAP
MAJOR_VALUE = 30.0          # крупный город (в том числе канонный) ставится крепостью и впритык
FILL_REACH = 45.0           # дальше этого от поселения земля считается пустой
VILLAGE_SLACK = 1.35        # насколько можно превысить норму деревень ради заполнения пустот
MIN_VILLAGES = {"town": 2, "castle": 1}
MAX_VILLAGES = 4            # как в ванили
VILLAGE_REACH = 26.0        # дальше этого «своей» деревню крепости уже не считаем
BIND_REACH = 45.0           # на таком расстоянии деревню ещё можно приписать к крепости
BORDER = 16.0               # отступ от края карты


def land_grid(step=GRID):
    """Маска суши на сетке с шагом step: (маска, номера строк, номера столбцов)."""
    land = equus_map.land_map() & (equus_map.heights() > MIN_HEIGHT)
    n = land.shape[0]
    sub = max(1, int(round(step / (equus_map.MAP_SIZE / (n - 1)))))
    land = land[::sub, ::sub].copy()
    h, w = land.shape
    edge = int(round(BORDER / step))
    land[:edge], land[h - edge:], land[:, :edge], land[:, w - edge:] = False, False, False, False
    return land


MIN_ISLAND = 250            # клеток; островки мельче в расселении не участвуют
OFFSHORE = 45.0             # дальше этого от заселяемой суши город считается островным


def land_cells(step=GRID):
    """Клетки суши, куда можно ставить поселение. Мелкие острова выброшены: сухопутной дороги
    туда нет, лорды и караваны до такого поселения не доберутся."""
    land = land_grid(step)
    big = np.zeros_like(land)
    for _kid, cells in _components(np.zeros(land.shape, np.int32), land):
        if len(cells) >= MIN_ISLAND:
            for j, i in cells:
                big[j, i] = True
    ys, xs = np.nonzero(big)
    return xs * step, ys * step


def _components(owner2d, land):
    """Связные куски земли одного владельца: [(владелец, [(строка, столбец), ...]), ...]."""
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


# Клочок земли меньше этого (и меньше доли SMALL_SHARE от владений державы) считается
# анклавом и отходит соседям.
SMALL_PATCH = 150
SMALL_SHARE = 0.15


def _stitch(owner2d, land, capital_cells):
    """Сшивка анклавов: небольшой кусок земли, оторванный от остальных владений державы и
    окружённый чужой землёй, отходит соседу с самой длинной общей границей. Большие куски
    (целые области за чужой землёй) и клетку столицы не трогаем, острова тоже: сухопутных
    соседей у них нет, а морская держава как раз из островов и состоит."""
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
            continue                     # остров — оставляем как есть
        new_kid = max(neighbours, key=neighbours.get)
        for cj, ci in cells:
            owner2d[cj, ci] = new_kid
        moved += len(cells)
    return moved


def partition(anchors, weights, cells, log=print):
    """Делит клетки суши между державами так, чтобы площади относились как weights.

    Аддитивно взвешенный Вороной: клетка отходит той державе, до чьих опорных городов ближе
    (с поправкой); поправки подбираются итерациями, пока площади не сойдутся с целевыми.
    Опорных городов у державы несколько — это канонные города её земель, и они держат границы
    там, где им положено по лору, а не там, где вышло по циркулю от столицы.

    После каждого подгона анклавы сшиваются (см. _stitch), и подгон продолжается уже с ними:
    так державы получают и свою долю земли, и целые владения без клочков за морем."""
    x, y = cells
    w = np.asarray(weights, float)
    target = w / w.sum() * len(x)
    d = np.empty((len(x), len(anchors)), np.float32)
    for i, points in enumerate(anchors):
        P = np.asarray(points, float).reshape(-1, 2)
        d[:, i] = np.hypot(x[:, None] - P[None, :, 0], y[:, None] - P[None, :, 1]).min(1)

    # сетка ровно из тех клеток, что нам дали (без выброшенных островков)
    ys_idx = np.rint(y / GRID).astype(int)
    xs_idx = np.rint(x / GRID).astype(int)
    land = np.zeros((ys_idx.max() + 2, xs_idx.max() + 2), bool)
    land[ys_idx, xs_idx] = True
    # клетка столицы: кусок земли, где стоит столица, — коренные владения державы, их не
    # отбирают. Всё остальное, что оказалось отрезанным, отходит соседям, чтобы держава
    # не владела клочками за чужими землями (лорды до них просто не доберутся).
    keep_cells = {}
    for i, points in enumerate(anchors):
        ax, ay = np.asarray(points, float).reshape(-1, 2)[0]
        j = int(np.argmin((x - ax) ** 2 + (y - ay) ** 2))
        keep_cells[i] = {(int(ys_idx[j]), int(xs_idx[j]))}

    bias = np.zeros(len(anchors))
    owner = d.argmin(1)
    err = np.ones(len(anchors))
    for _step in range(200):            # грубый подгон без сшивки — он дешёвый
        owner = (d - bias).argmin(1)
        area = np.bincount(owner, minlength=len(anchors)).astype(float)
        err = (target - area) / target
        if np.abs(err).max() < 0.015:
            break
        bias += err * 5.0
    moved = 0
    for _round in range(12):            # подгон вместе со сшивкой анклавов
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
    """Сколько городов/замков/деревень полагается каждой державе (по её силе)."""
    w = np.asarray(weights, float)
    share = w / w.mean()
    out = []
    for s in share:
        out.append({kind: max(1, int(round(n * s))) for kind, n in base.items()})
    return out


class _Board:
    """Уже поставленные поселения: проверка зазоров и расстояний до клеток суши."""

    def __init__(self, cells):
        self.x, self.y = cells
        self.dist = np.full(len(self.x), np.inf)   # до ближайшего поселения любой державы
        self.points = []                           # (x, y, группа)

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
        """Годится ли точка: твёрдая суша, внутри карты, зазоры соблюдены."""
        if not (BORDER < x < equus_map.MAP_SIZE - BORDER and BORDER < y < equus_map.MAP_SIZE - BORDER):
            return False
        if not self.free(x, y, group):
            return False
        if extra and any((x - px) ** 2 + (y - py) ** 2 < extra * extra
                         for px, py, pg in self.points if pg == group):
            return False
        return equus_map.solid_ground(x, y)

    def settle(self, x, y, group, limit=24.0):
        """Ближайшая к (x, y) годная точка (по спирали), либо None."""
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
    """Раскладка мира.

    kingdoms — [{"kingdom": id, "capital_xy": (x, y)}], weights — сила держав,
    cities — города EaW (name, x, y, value, owner), base — норма поселений средней державы.

    Возвращает {id державы: {"town": [...], "castle": [...], "village": [...]}}, где запись —
    {"x", "y", "city": исходный город EaW или None, "bound": (вид, номер) у деревни}."""
    cells = land_cells()
    cx, cy = cells
    owner = partition([k.get("anchors") or [k["capital_xy"]] for k in kingdoms], weights, cells, log)
    want = targets(weights, base)
    board = _Board(cells)
    result = {k["kingdom"]: {"town": [], "castle": [], "village": []} for k in kingdoms}

    # Города Equestria at War стоят там, где их поставила та карта, а рельеф с тех пор
    # переделан: часть точек оказалась под водой или на отмели. Такой город сдвигаем на
    # ближайшую годную клетку суши. Если до неё далеко (город на островке, куда нет
    # сухопутной дороги) — город в расселении не участвует, а его имя достанется новому
    # поселению на большой земле.
    moved = off = 0
    fixed = []
    for c in cities:
        if c["name"] in pinned:      # город переставлен руками — его точку не трогаем
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

    # какой державе достался каждый город EaW — по владельцу ближайшей клетки суши
    city_owner = {}
    for c in cities:
        j = int(np.argmin((cx - c["x"]) ** 2 + (cy - c["y"]) ** 2))
        city_owner[c["name"]] = int(owner[j])
    # опорные города остаются за своей державой, даже если граница прошла рядом иначе:
    # Кантерлот не может оказаться драконьим, а Кристальный Пик — эквестрийским
    for i, k in enumerate(kingdoms):
        for name in k.get("anchor_names", ()):
            if name in city_owner:
                city_owner[name] = i

    # столицы ставим первыми, чтобы они не сдвинулись из-за чужих зазоров
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
        """Самая пустая точка области i, годная под поселение."""
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

    # ---------------------------------------------------------------- крепости
    for i, k in enumerate(kingdoms):
        kid = k["kingdom"]
        spots = result[kid]
        need_forts = want[i]["town"] + want[i]["castle"]
        mine = sorted((c for c in cities if city_owner.get(c["name"]) == i
                       and not any(e["city"] is c for e in spots["town"])),
                      key=lambda c: -c["value"])
        forts = list(spots["town"])   # столица уже стоит
        for spread in (FORT_SPREAD, GAP[("fort", "fort")]):
            for c in mine:
                if len(forts) >= need_forts:
                    break
                if any(e["city"] is c for e in forts):
                    continue
                # крупному городу разбег не помеха: Клаудсдейл стоит в 21 м от Понивилля,
                # и это по лору правильно — оба города настоящие
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
        # столица — всегда первый город, дальше по значимости
        rest = sorted(forts[1:], key=lambda e: -(e["city"]["value"] if e["city"] else 0))
        ordered = forts[:1] + rest
        spots["town"] = ordered[:want[i]["town"]]
        spots["castle"] = ordered[want[i]["town"]:]
        k["_invented_forts"] = invented

    # ---------------------------------------------------------------- деревни
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

        # У каждой крепости должна быть своя деревня, и непременно рядом: берём ближайший
        # подходящий город, но не дальше VILLAGE_REACH, иначе ставим новую деревню в кольце
        # вокруг крепости. Иначе у переставленного города «его» деревни остаются за сто метров.
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
                    # начальный угол свой у каждой крепости, иначе все деревни выстраиваются
                    # с одной и той же стороны
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

        # остальные деревни — жадно «подальше от уже поставленных», предпочитая города EaW
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

        # заполнение пустот: пока в области есть земля дальше FILL_REACH от всего живого
        while len(placed) < limit_v:
            m = owner == i
            if not m.any() or board.dist[m].max() <= FILL_REACH:
                break
            spot = emptiest(i, "village", need=FILL_REACH)
            if spot is None:
                break
            put(spot[0], spot[1], None)

        # приписка к крепостям: ближайшая своя, но не больше MAX_VILLAGES на одну
        counts = {(kind, n): 0 for kind, n, _e in forts}
        for entry in sorted(placed, key=lambda e: min(
                (e["x"] - f["x"]) ** 2 + (e["y"] - f["y"]) ** 2 for _k, _n, f in forts)):
            order = sorted(forts, key=lambda f: (f[2]["x"] - entry["x"]) ** 2 + (f[2]["y"] - entry["y"]) ** 2)
            # ближайшая крепость с местом, но только из ближних: лучше пятая деревня у соседа,
            # чем деревня, приписанная к крепости за сто метров
            close = [f for f in order
                     if math.hypot(f[2]["x"] - entry["x"], f[2]["y"] - entry["y"]) <= BIND_REACH]
            pick = next((f for f in close if counts[(f[0], f[1])] < MAX_VILLAGES), order[0])
            entry["bound"] = (pick[0], pick[1])
            counts[(pick[0], pick[1])] += 1
        # крепость без деревень в игре живёт впроголодь (в ванили таких нет), поэтому у соседа
        # с запасом забираем ближайшую к ней деревню
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
