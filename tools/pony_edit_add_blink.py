# -*- coding: utf-8 -*-
"""Моргание для перекроенной вручную головы в assets/pony/eq_pony_edit.blend.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_add_blink.py

Separate/Join, которыми голову резали и правили руками, ключи мимики не сохраняют (это
подтверждено: у eq_pony_head в «Пони - цельная» 0 шейпкизов). Без 101 ключа (key_000..key_100,
кадры 86/87/88 — левый/правый/оба глаза) движок не может моргать этой головой. Код поиска глаз и
самого моргания — точная копия eye_spots()/add_blink() из tools/make_pony_model.py, только текстуру
и развёртку берёт с уже готового материала объекта, а не из свежего импорта FBX.
"""
import bpy
import numpy as np
from mathutils import Vector

FACE_KEYS = 101
BLINK_FRAMES = {86: "левый", 87: "правый", 88: "оба"}
EYE_DARK = 0.30
EYE_CORE = 0.055
EYE_REACH = 0.090
EYE_SQUASH = 0.92
EYE_OUT = 0.0
EYE_BACK = 0.0
EYE_SIDE = 0.04
EYE_MIN = 5
EYE_BLUE = 0.18
EYE_GROW = 0.09
EYE_HALF = 0.0


def log(*a):
    print("[blink]", *a, flush=True)


def find_diffuse(ob):
    for m in ob.data.materials:
        if not m or not m.use_nodes:
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and "color" in (n.label or n.image.name).lower():
                return n.image
    return None


def eye_spots(ob, diffuse):
    global EYE_HALF
    img = diffuse
    uvs = ob.data.uv_layers.active
    if img is None or uvs is None:
        log("ВНИМАНИЕ: не нашёл текстуру или развёртку — моргания не будет")
        return []
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)
    P = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])
    tone = np.zeros(len(P))
    blue = np.zeros(len(P))
    hits = np.zeros(len(P))
    for poly in ob.data.polygons:
        mid = np.mean([np.array(uvs.data[li].uv) for li in poly.loop_indices], axis=0)
        for li in poly.loop_indices:
            spot = np.array(uvs.data[li].uv) * 0.75 + mid * 0.25
            x = int(min(max(spot[0], 0.0), 0.999) * (w - 1))
            y = int(min(max(spot[1], 0.0), 0.999) * (h - 1))
            tone[ob.data.loops[li].vertex_index] += float(px[y, x, :3].mean())
            blue[ob.data.loops[li].vertex_index] += float(px[y, x, 2] - px[y, x, 0])
            hits[ob.data.loops[li].vertex_index] += 1
    tone /= np.maximum(hits, 1)
    blue /= np.maximum(hits, 1)

    dark = (tone < EYE_DARK) & (hits > 0)
    near = [[] for _ in range(len(P))]
    for e in ob.data.edges:
        near[e.vertices[0]].append(e.vertices[1])
        near[e.vertices[1]].append(e.vertices[0])
    seen = np.zeros(len(P), bool)
    spots = []
    for start in np.flatnonzero(dark):
        if seen[start]:
            continue
        stack, blob = [start], []
        seen[start] = True
        while stack:
            cur = stack.pop()
            blob.append(cur)
            for other in near[cur]:
                if dark[other] and not seen[other]:
                    seen[other] = True
                    stack.append(other)
        spots.append((P[blob].mean(0), len(blob), float(tone[blob].mean()), blob))
    front = float(P[:, 1].min() + P[:, 1].max()) / 2
    upper = float(P[:, 2].min() + 0.35 * (P[:, 2].max() - P[:, 2].min()))
    mine = [s for s in spots
            if abs(s[0][0]) > EYE_SIDE and s[0][1] < front and s[0][2] > upper and s[1] >= EYE_MIN]
    if not mine:
        return []
    best, count, shade, blob = min(mine, key=lambda s: s[2])
    iris = (hits > 0) & (tone < 0.80) & (blue > EYE_BLUE)
    eye = set(blob)
    stack = list(blob)
    while stack:
        cur = stack.pop()
        for other in near[cur]:
            if other not in eye and (dark[other] or iris[other]) and np.linalg.norm(P[other] - best) < EYE_GROW:
                eye.add(other)
                stack.append(other)
    ext = P[sorted(eye)]
    EYE_HALF = float(ext[:, 2].max() - ext[:, 2].min()) / 2
    best = np.array([ext[:, 0].mean(), ext[:, 1].mean(), (ext[:, 2].max() + ext[:, 2].min()) / 2])
    log("  глаз целиком: %d вершин (зрачок %d), высота %.3f" % (len(eye), count, 2 * EYE_HALF))
    right = np.array([abs(best[0]), best[1], best[2]])
    log("  глаз найден на (%.2f,%.2f,%.2f): %d вершин, яркость %.2f; вторая сторона отражена"
        % (*right, count, shade))
    right = right + np.array([EYE_OUT, EYE_BACK, 0.0])
    return [right, np.array([-right[0], right[1], right[2]])]


def add_blink(ob, diffuse):
    if ob.data.shape_keys:
        log("у головы уже есть шейпкизы — пропускаю, чтобы не задвоить")
        return
    spots = eye_spots(ob, diffuse)
    if len(spots) != 2:
        log("ВНИМАНИЕ: глаз на текстуре не видно (%d пятен) — моргания не будет" % len(spots))
        return
    log("глаза найдены: (%.2f,%.2f,%.2f) и (%.2f,%.2f,%.2f)" % (*spots[0], *spots[1]))
    P = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])

    def shut(sides):
        move = np.zeros_like(P)
        for side in sides:
            eye = spots[side]
            gap = np.linalg.norm(P - eye, axis=1)
            core = max(EYE_CORE, EYE_HALF * 1.15)
            reach = core + (EYE_REACH - EYE_CORE)
            close = gap < reach
            fade = np.clip((reach - gap[close]) / max(reach - core, 1e-6), 0.0, 1.0)
            move[close, 2] += (eye[2] - P[close, 2]) * EYE_SQUASH * fade
        return move

    ob.shape_key_add(name="Basis", from_mix=False)
    shifts = {k: shut(s) for k, s in ((86, [0]), (87, [1]), (88, [0, 1]))}
    for k in range(FACE_KEYS):
        key = ob.shape_key_add(name="key_%03d" % k, from_mix=False)
        if k not in shifts:
            continue
        for i, point in enumerate(key.data):
            point.co = point.co + Vector(shifts[k][i])
    log("моргание: %d ключей, кадры %s (сжатие %.2f, радиус %.3f)"
        % (FACE_KEYS, "/".join(str(k) for k in sorted(BLINK_FRAMES)), EYE_SQUASH, EYE_REACH))


head = bpy.data.collections["Пони - цельная"].objects["eq_pony_head"]
diffuse = find_diffuse(head)
log("диффуз-текстура:", diffuse.name if diffuse else None)
if diffuse:
    diffuse.pixels[0]  # заставить Blender подгрузить пиксели с диска
add_blink(head, diffuse)
bpy.ops.wm.save_mainfile()
log("сохранено")
