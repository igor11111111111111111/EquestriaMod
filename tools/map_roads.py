# -*- coding: utf-8 -*-
"""Дороги между поселениями на карте мира.

  Модуль вызывается из paint_terrain.py: mask(size, log) -> карта дорог 0..1 того же размера,
  что и карта местности. Дороги вписываются в покраску рельефа сухой землёй (слой 4).

В ванильной игре дороги НЕ рисуются ни сущностями, ни слоями: вся земля карты мира запечена в
виртуальную текстуру (Main_map/TileSets/WorldMap.gts, 2.1 ГБ), и дороги нарисованы прямо в ней
художником. Декали decal_path_a/b, которые встречаются в сцене, — это дорожки ВНУТРИ моделей
поселений, а не пути между ними. Повторить запекание нечем: его делает редактор для рельефа
версии 1, а у нас версия 0. Поэтому дороги прокладываем сами и вписываем в слои.

Как считается путь: карта разбивается на клетки по ROUTE_STEP метров, каждой клетке даётся цена
(вода непроходима, горы и крутизна дороги, равнина дёшево), и между поселениями ищется самый
дешёвый путь по Дейкстре. Деревня соединяется со своим городом или замком, города и замки — в
общую сеть: сначала остов по кратчайшим расстояниям, чтобы всё было связано, потом к каждому
добавляются ближайшие соседи, иначе сеть выглядит деревом, а не дорогами.
"""
import heapq
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402

ROUTE_STEP = 4.0        # сторона клетки при поиске пути, м
ROAD_WIDTH = 2.5        # ширина дороги, м (обзор камеры на карте ~70 м, шире смотрится трактом)
EDGE_SOFT = 1.0         # насколько мягко дорога сходит на нет по краям, м
SLOPE_COST = 26.0       # во сколько раз дороже подъём: цена = 1 + SLOPE_COST * уклон
KIND_COST = {equus_map.PLAIN: 1.0, equus_map.STEPPE: 1.05, equus_map.DESERT: 1.2,
             equus_map.FOREST: 1.6, equus_map.SWAMP: 2.6, equus_map.SNOW: 1.8,
             equus_map.MOUNTAIN: 3.2}
WATER_KINDS = (equus_map.WATER, equus_map.LAKE, equus_map.RIVER)
RIVER_COST = 9.0        # реку перейти можно, но дорого — дорога ищет брод, а не идёт вдоль
NEIGHBOURS = 1          # сколько ближайших соседей соединять сверх остова
MAX_HUB_LINK = 260.0    # длиннее этого города напрямую не соединяем, м
SMOOTH_ROUNDS = 2       # сглаживание ломаной


def log_nothing(*a):
    pass


def settlements(mod):
    """Поселения из equestria_settlements.xml: (id, x, y, вид, к кому привязано)."""
    path = os.path.join(mod, "ModuleData", "equestria_settlements.xml")
    out = {}
    for node in ET.parse(path).getroot():
        if node.tag != "Settlement":
            continue
        sid = node.get("id")
        x, y = float(node.get("posX")), float(node.get("posY"))
        gate = (float(node.get("gate_posX")), float(node.get("gate_posY"))) \
            if node.get("gate_posX") else (x, y)
        kind, bound = "hideout", None
        town = node.find(".//Town")
        village = node.find(".//Village")
        if town is not None:
            kind = "castle" if (town.get("is_castle") or "false").lower() == "true" else "town"
        elif village is not None:
            kind = "village"
            bound = (village.get("bound") or "").replace("Settlement.", "") or None
        out[sid] = dict(id=sid, x=x, y=y, gate=gate, kind=kind, bound=bound)
    return out


def cost_grid(size):
    """Цена прохода по клетке. Вода непроходима (кроме рек — их можно перейти вброд)."""
    terrain = equus_map.terrain_map()
    heights = equus_map.heights()
    step = equus_map.MAP_SIZE / (size - 1)
    # усредняем исходные карты до сетки поиска
    src = terrain.shape[0]
    take = np.clip((np.arange(size) * (src - 1) / (size - 1)).round().astype(int), 0, src - 1)
    kind = terrain[np.ix_(take, take)]
    high = heights[np.ix_(take, take)].astype(np.float32)

    cost = np.full(kind.shape, 1.0, dtype=np.float32)
    for k, value in KIND_COST.items():
        cost[kind == k] = value
    cost[kind == equus_map.RIVER] = RIVER_COST
    blocked = np.isin(kind, (equus_map.WATER, equus_map.LAKE)) | (high < 0.4)
    # уклон между соседними клетками — по нему дорога обходит горы
    gy, gx = np.gradient(high, step)
    slope = np.sqrt(gx ** 2 + gy ** 2)
    cost = cost * (1.0 + SLOPE_COST * slope)
    cost[blocked] = np.inf
    return cost


def _dijkstra(cost, start, targets):
    """Пути от одной клетки до нужных: обычная Дейкстра с ранним выходом."""
    size = cost.shape[0]
    best = np.full(cost.shape, np.inf, dtype=np.float32)
    came = np.full(cost.shape, -1, dtype=np.int32)
    sy, sx = start
    if not np.isfinite(cost[sy, sx]):
        return {}
    best[sy, sx] = 0.0
    todo = [(0.0, sy * size + sx)]
    left = set(targets)
    done = {}
    while todo and left:
        value, node = heapq.heappop(todo)
        y, x = divmod(node, size)
        if value > best[y, x]:
            continue
        if (y, x) in left:
            left.discard((y, x))
            done[(y, x)] = True
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if not (0 <= ny < size and 0 <= nx < size):
                    continue
                price = cost[ny, nx]
                if not np.isfinite(price):
                    continue
                step = price * (1.41421356 if dy and dx else 1.0)
                new = value + float(step)
                if new < best[ny, nx]:
                    best[ny, nx] = new
                    came[ny, nx] = node
                    heapq.heappush(todo, (new, ny * size + nx))
    paths = {}
    for target in targets:
        if target not in done:
            continue
        chain = []
        y, x = target
        while True:
            chain.append((y, x))
            previous = came[y, x]
            if previous < 0:
                break
            y, x = divmod(int(previous), size)
        chain.reverse()
        paths[target] = chain
    return paths


def _smooth(points):
    """Скругление ломаной по Чайкину: дорога перестаёт ходить ступеньками."""
    for _ in range(SMOOTH_ROUNDS):
        if len(points) < 3:
            break
        out = [points[0]]
        for a, b in zip(points, points[1:]):
            out.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            out.append((0.25 * a[0] + 0.75 * b[0], 0.25 * b[1] + 0.75 * b[1]))
        out.append(points[-1])
        points = out
    return points


def _links(places, log):
    """Какие поселения соединяем: деревня — со своим городом, города и замки — в общую сеть."""
    hubs = [p for p in places.values() if p["kind"] in ("town", "castle")]
    edges = set()
    for place in places.values():
        if place["kind"] == "village" and place["bound"] in places:
            edges.add((place["id"], place["bound"]))
    # остов по расстоянию, чтобы сеть была связной
    if hubs:
        inside = {hubs[0]["id"]}
        rest = {h["id"] for h in hubs[1:]}
        by_id = {h["id"]: h for h in hubs}
        while rest:
            best = None
            for a in inside:
                pa = by_id[a]
                for b in rest:
                    pb = by_id[b]
                    d = math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])
                    if best is None or d < best[0]:
                        best = (d, a, b)
            _, a, b = best
            edges.add((a, b))
            inside.add(b)
            rest.discard(b)
        # плюс ближайшие соседи — иначе сеть выглядит деревом, а не дорогами
        for h in hubs:
            near = sorted((math.hypot(h["x"] - o["x"], h["y"] - o["y"]), o["id"])
                          for o in hubs if o["id"] != h["id"])
            for d, other in near[:NEIGHBOURS]:
                if d <= MAX_HUB_LINK:
                    edges.add(tuple(sorted((h["id"], other))))
    log("дорожная сеть: узлов %d, связей %d" % (len(hubs), len(edges)))
    return edges


def routes(mod, log=log_nothing):
    """Ломаные дорог в метрах карты."""
    places = settlements(mod)
    edges = _links(places, log)
    size = int(round(equus_map.MAP_SIZE / ROUTE_STEP)) + 1
    cost = cost_grid(size)
    step = equus_map.MAP_SIZE / (size - 1)

    def cell(place):
        """Клетка поселения. Ворота часто стоят у самой воды и попадают на непроходимую клетку —
        тогда берём ближайшую проходимую, иначе дорога к этому поселению не строится вовсе."""
        gx, gy = place["gate"]
        cy, cx = int(round(gy / step)), int(round(gx / step))
        cy = min(max(cy, 0), size - 1)
        cx = min(max(cx, 0), size - 1)
        if np.isfinite(cost[cy, cx]):
            return (cy, cx)
        for radius in range(1, 8):
            best = None
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < size and 0 <= nx < size and np.isfinite(cost[ny, nx]):
                        d = dy * dy + dx * dx
                        if best is None or d < best[0]:
                            best = (d, ny, nx)
            if best:
                return (best[1], best[2])
        return (cy, cx)

    # группируем по источнику: одна Дейкстра на источник со всеми его целями
    by_source = {}
    for a, b in edges:
        by_source.setdefault(a, []).append(b)
    lines = []
    missed = 0
    for source, targets in sorted(by_source.items()):
        start = cell(places[source])
        wanted = {cell(places[t]): t for t in targets}
        paths = _dijkstra(cost, start, list(wanted))
        for target_cell, name in wanted.items():
            chain = paths.get(target_cell)
            if not chain or len(chain) < 2:
                missed += 1
                continue
            lines.append(_smooth([(x * step, y * step) for y, x in chain]))
    log("дорог проложено: %d, не удалось: %d" % (len(lines), missed))
    return lines


def mask(size, mod, log=log_nothing):
    """Карта дорог 0..1: 1 по оси дороги, к краям сходит на нет."""
    out = np.zeros((size, size), dtype=np.float32)
    step = equus_map.MAP_SIZE / (size - 1)
    half = ROAD_WIDTH / 2.0
    reach = half + EDGE_SOFT
    span = int(math.ceil(reach / step)) + 1
    for line in routes(mod, log):
        for (x0, y0), (x1, y1) in zip(line, line[1:]):
            length = math.hypot(x1 - x0, y1 - y0)
            if length < 1e-6:
                continue
            # штампуем отрезок: для каждой клетки вокруг считаем расстояние до него
            cx0, cy0 = int(round(x0 / step)), int(round(y0 / step))
            cx1, cy1 = int(round(x1 / step)), int(round(y1 / step))
            lo_x, hi_x = min(cx0, cx1) - span, max(cx0, cx1) + span
            lo_y, hi_y = min(cy0, cy1) - span, max(cy0, cy1) + span
            lo_x, hi_x = max(lo_x, 0), min(hi_x, size - 1)
            lo_y, hi_y = max(lo_y, 0), min(hi_y, size - 1)
            if hi_x < lo_x or hi_y < lo_y:
                continue
            ys, xs = np.mgrid[lo_y:hi_y + 1, lo_x:hi_x + 1]
            px, py = xs * step - x0, ys * step - y0
            dx, dy = x1 - x0, y1 - y0
            t = np.clip((px * dx + py * dy) / (length * length), 0.0, 1.0)
            dist = np.sqrt((px - t * dx) ** 2 + (py - t * dy) ** 2)
            value = np.clip((reach - dist) / max(EDGE_SOFT, 1e-6), 0.0, 1.0)
            patch = out[lo_y:hi_y + 1, lo_x:hi_x + 1]
            np.maximum(patch, value.astype(np.float32), out=patch)
    return out


if __name__ == "__main__":
    def show(*a):
        print("[roads]", *a, flush=True)

    where = sys.argv[1] if len(sys.argv) > 1 else "Module"
    m = mask(equus_map.heights().shape[0], where, show)
    show("занято дорогами: %.2f%% карты" % (100.0 * float((m > 0.5).mean())))
