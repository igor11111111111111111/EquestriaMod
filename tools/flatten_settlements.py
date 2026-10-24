# -*- coding: utf-8 -*-
"""Выравнивает карту высот под поселениями: площадка известного размера под городом/замком/
деревней, плавно сведённая в окружающий рельеф — иначе стены стоят на склоне или насыпи, как
Кантерлот раньше.

  py -3 tools\\flatten_settlements.py

Правит assets/map/eq_map_heightmap.png (источник для tools/write_terrain_heights.py — запустите
его следом, чтобы попало в terrain.bin). Старый файл бэкапится рядом с суффиксом .before_flatten
(один раз, повторные запуски его не трогают — так можно звать скрипт заново после правки без
потери исходного рельефа).

Правка 03.10.2026 (по живому скрину в игре): первая версия была идеальным гладким блином с
обрывом по краю — непохоже на настоящую площадку. Теперь три добавки:
  - форма не круг, а чуть «дышащая» клякса (угловой шум на границе);
  - внутри лёгкие бугорки (тот же приём со сглаженным шумом, что в make_equus_map.py: мелкая
    случайная сетка, растянутая бикубически), не совсем ровно, но без ям под стенами;
  - спуск в рельеф не фиксированной ширины, а по уклону: меряем реальный перепад высоты у края
    площадки и подбираем расстояние так, чтобы уклон не был круче MAX_SLOPE — на крутом склоне
    (Кантерлот) спуск шире, на ровном месте — у́же, и обрыва по кругу больше не видно.
"""
import math
import os
import sys
import xml.etree.ElementTree as ET
import zlib

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTLEMENTS = os.path.join(ROOT, "Module", "ModuleData", "equestria_settlements.xml")
HEIGHTMAP = os.path.join(ROOT, "assets", "map", "eq_map_heightmap.png")

# Плоский радиус (м) = настоящий размер модели поселения на карте, не на глаз. У ванильных
# донорских моделей есть собственный декаль-круг (tools/settlement_visuals.py копирует его вместе
# с остальными частями) — сущность с tag "map_settlement_circle" (town_circle_decal), её
# transform.scale и есть радиус круга, который подсвечивает сама игра при наведении (проверено
# 03.10.2026: пользователь увидел в игре, что первая версия — с радиусом 13/10/8 м из
# map_props.SETTLEMENT_CLEAR — заметно больше этого круга). Замерено по всем донорам в сцене
# (tools/settlement_visuals.load_donors): медиана scale.x у города 7.55, у замка 3.12 (у деревни
# в ванили такого декаля вообще нет — там решили на глаз, они и так самые мелкие). Умножено на наш
# SCALE поселений (1.5×, tools/settlement_visuals.SCALE) — он же тянет саму модель.
_DONOR_SCALE = 1.5  # tools/settlement_visuals.SCALE — повторять импортом не стали, завязка на внешний модуль лишняя
FLAT_RADIUS = {"town": 7.55 * _DONOR_SCALE, "castle": 3.12 * _DONOR_SCALE, "village": 5.0, "hideout": 4.0}
# Спуск — минимальная ширина (на ровном месте, где и так почти нечего сглаживать) и предельный
# уклон (перепад высоты / расстояние): даём ровно столько метров вовне, сколько нужно, чтобы
# склон не был круче MAX_SLOPE. 0.6 — это примерно 31°, заметно положе голого обрыва, но всё ещё
# читается как склон, а не как вторая плоская площадка.
MIN_BLEND = {"town": 6.0, "castle": 3.0, "village": 3.0, "hideout": 3.0}
MAX_BLEND = 24.0
MAX_SLOPE = 0.6

# Неровность формы: граница площадки «дышит» по углу — сумма 2-3 низкочастотных синусоид со
# случайной фазой (своя на каждое поселение, детерминирована по id). AMOUNT — на какую долю
# радиуса может сжаться/растянуться граница.
BLOB_AMOUNT = 0.22

# Бугорки внутри площадки: амплитуда (м) и длина волны (м) — тот же приём co сглаженным шумом,
# что в make_equus_map.py (wave()). Слабее к центру нет смысла — даже прямо под стенами в
# реальности грунт не идеально ровный, движок сам сажает модель по общей высоте точки, а не по
# каждой вершине.
BUMP_AMPLITUDE = 0.4
BUMP_WAVELENGTH = 7.0


def log(*a):
    print("[flatten]", *a, flush=True)


def kind_of(settlement_id):
    for kind in FLAT_RADIUS:
        if settlement_id.startswith(kind + "_"):
            return kind
    return None


def load_settlements():
    root = ET.parse(SETTLEMENTS).getroot()
    out = []
    for s in root.findall("Settlement"):
        sid = s.get("id", "")
        kind = kind_of(sid)
        if kind is None:
            continue
        out.append((sid, kind, float(s.get("posX")), float(s.get("posY"))))
    return out


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def blob_shape(theta, seed):
    """Множитель радиуса по углу (около 1.0) — 2-3 случайные гармоники, своя фаза на поселение."""
    rng = np.random.default_rng(seed)
    mod = np.ones_like(theta)
    for freq in (2, 3, 5):
        amp = rng.uniform(0.3, 1.0)
        phase = rng.uniform(0.0, 2 * math.pi)
        mod = mod + amp * np.sin(freq * theta + phase)
    # нормируем размах под BLOB_AMOUNT (сумма трёх синусоид может дать больше ±1)
    mod = mod - 1.0  # центрируем, сумма гармоник сама по себе ~0 в среднем
    peak = max(float(np.max(np.abs(mod))), 1e-6)
    return 1.0 + (mod / peak) * BLOB_AMOUNT


def bump_noise(h, w, seed, wavelength, scale):
    """Сглаженный шум нужного размера (мелкая случайная сетка, растянутая бикубически)."""
    side_h = max(2, int(round(h / wavelength)))
    side_w = max(2, int(round(w / wavelength)))
    rng = np.random.default_rng(seed)
    small = rng.normal(0.0, 1.0, (side_h, side_w)).astype(np.float32)
    img = Image.fromarray(small, mode="F").resize((w, h), Image.BICUBIC)
    field = np.asarray(img, dtype=np.float32)
    return field / max(float(field.std()), 1e-6) * scale


def edge_height_diff(original, scale, px, py, target, radius):
    """Средний перепад высоты (исходный рельеф минус цель) по кольцу радиуса radius — сколько
    реально нужно сгладить на границе площадки, чтобы подобрать ширину спуска."""
    size = original.shape[0]
    samples = []
    for k in range(12):
        a = 2 * math.pi * k / 12
        sx = px + radius * math.cos(a) * scale
        sy = py + radius * math.sin(a) * scale
        ix, iy = int(round(sx)), int(round(sy))
        if 0 <= ix < size and 0 <= iy < size:
            samples.append(float(original[iy, ix]))
    if not samples:
        return 0.0
    return abs(float(np.mean(samples)) - target)


def main():
    settlements = load_settlements()
    log("поселений для выравнивания: %d" % len(settlements))

    heights = equus_map.heights().copy()  # (S, S), строка 0 — юг; метры
    original = heights.copy()
    size = heights.shape[0]
    scale = (size - 1) / equus_map.MAP_SIZE  # пикселей на метр (у нас 1025/1024 ~= 1.0)

    # Воду не трогаем вообще (03.10.2026, скрин в игре: у Горы Арис — она на берегу — спуск
    # дотянулся до моря и поднял воду выше уровня моря; классификация местности (вода/суша),
    # по которой движок красит волны, не пересчитывается от высоты — осталась "вода", и получились
    # волны на теперь-уже-суше). Маска по ТЕКУЩЕЙ (исходной, до правок) классификации местности.
    water_mask = np.isin(equus_map.terrain_map(), (equus_map.WATER, equus_map.LAKE, equus_map.RIVER))
    if water_mask.shape != heights.shape:
        raise SystemExit("eq_map_terrain.png %s не совпадает по размеру с картой высот %s"
                         % (water_mask.shape, heights.shape))

    best_w = np.zeros_like(heights)

    for i, (sid, kind, x, y) in enumerate(settlements):
        rf = FLAT_RADIUS[kind]
        px, py = x * scale, y * scale
        # центр площадки — пиксель поселения в ИСХОДНОМ (не изменённом) рельефе: площадка не
        # придумывает новую высоту, а убирает бугры/уклон вокруг уже выбранной точки
        target = float(original[int(round(py)), int(round(px))])

        diff = edge_height_diff(original, scale, px, py, target, rf)
        rb = float(np.clip(diff / MAX_SLOPE, MIN_BLEND[kind], MAX_BLEND))
        reach = rf + rb

        x0 = max(0, int(np.floor(px - reach * scale)))
        x1 = min(size, int(np.ceil(px + reach * scale)) + 1)
        y0 = max(0, int(np.floor(py - reach * scale)))
        y1 = min(size, int(np.ceil(py + reach * scale)) + 1)
        if x0 >= x1 or y0 >= y1:
            continue

        yy, xx = np.mgrid[y0:y1, x0:x1]
        dx, dy = (xx - px) / scale, (yy - py) / scale
        dist = np.sqrt(dx ** 2 + dy ** 2)
        theta = np.arctan2(dy, dx)
        mod = blob_shape(theta, seed=zlib.crc32(sid.encode()))
        dist_eff = dist / np.clip(mod, 0.5, 1.5)  # «дышащая» граница, без самопересечений

        t = (dist_eff - rf) / max(rb, 1e-6)
        w = 1.0 - smoothstep(t)  # 1 внутри площадки, 0 за пределами спуска
        w[dist_eff <= rf] = 1.0
        w[dist_eff >= reach] = 0.0
        w[water_mask[y0:y1, x0:x1]] = 0.0  # море/озеро/река — не поднимаем и не красим бугорками

        bumps = bump_noise(y1 - y0, x1 - x0, seed=zlib.crc32((sid + "_b").encode()),
                            wavelength=BUMP_WAVELENGTH, scale=BUMP_AMPLITUDE)

        region_best = best_w[y0:y1, x0:x1]
        mask = w > region_best
        region_h = heights[y0:y1, x0:x1]
        blended = original[y0:y1, x0:x1] * (1.0 - w) + target * w + bumps * w
        region_h[mask] = blended[mask]
        region_best[mask] = w[mask]

        if (i + 1) % 100 == 0:
            log("обработано %d/%d" % (i + 1, len(settlements)))

    changed = np.abs(heights - original)
    log("изменено пикселей: %d, максимум сдвига %.2f м" % (int((changed > 1e-6).sum()), float(changed.max())))

    lo, hi = equus_map.info()["min_height"], equus_map.info()["max_height"]
    raw = np.clip(np.rint((heights - lo) / (hi - lo) * 65535), 0, 65535).astype(np.uint16)

    backup = HEIGHTMAP + ".before_flatten"
    if not os.path.exists(backup):
        import shutil
        shutil.copy2(HEIGHTMAP, backup)
        log("резервная копия", backup)

    # запись — тот же разворот, что equus_map делает при чтении ([::-1]), чтобы в файле снова была
    # строка 0 = север, как в исходном eq_map_heightmap.png; mode не задаём — как в
    # make_equus_map.py, PIL сам определяет его по dtype uint16 (та же кодировка, что у оригинала).
    Image.fromarray(raw[::-1]).save(HEIGHTMAP)
    log("записан", HEIGHTMAP)
    log("дальше: py -3 tools\\write_terrain_heights.py Module  (запечь в terrain.bin)")


if __name__ == "__main__":
    main()
