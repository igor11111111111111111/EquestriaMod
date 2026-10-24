# -*- coding: utf-8 -*-
"""Flattens the heightmap under settlements: a pad of known size under a town/castle/village,
smoothly blended into the surrounding terrain — otherwise the walls stand on a slope or a mound,
as Canterlot used to.

  py -3 tools\\flatten_settlements.py

Edits assets/map/eq_map_heightmap.png (the source for tools/write_terrain_heights.py — run it
next so the change gets into terrain.bin). The old file is backed up alongside with the suffix
.before_flatten (once; repeated runs do not touch it — so the script can be run again after an
edit without losing the original terrain).

Change of 03.10.2026 (from a live in-game screenshot): the first version was a perfectly smooth
pancake with a cliff at the edge — it did not look like a real pad. Now there are three additions:
  - the shape is not a circle but a slightly "breathing" blob (angular noise on the border);
  - light bumps inside (the same smoothed-noise trick as in make_equus_map.py: a small random
    grid stretched bicubically), not perfectly flat, but without pits under the walls;
  - the descent into the terrain has no fixed width but follows the slope: we measure the real
    height difference at the pad edge and choose the distance so the slope is not steeper than
    MAX_SLOPE — on a steep slope (Canterlot) the descent is wider, on flat ground narrower, and the
    circular cliff is no longer visible.
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

# Flat radius (m) = the real size of the settlement model on the map, not eyeballed. The vanilla
# donor models have their own decal circle (tools/settlement_visuals.py copies it together with the
# other parts) — an entity with tag "map_settlement_circle" (town_circle_decal); its transform.scale
# is the radius of the circle the game itself highlights on hover (checked 03.10.2026: the user saw
# in game that the first version — with radius 13/10/8 m from map_props.SETTLEMENT_CLEAR — was
# noticeably larger than this circle). Measured over all donors in the scene
# (tools/settlement_visuals.load_donors): median scale.x for a town 7.55, for a castle 3.12 (vanilla
# villages have no such decal at all — those were chosen by eye, they are the smallest anyway).
# Multiplied by our settlement SCALE (1.5x, tools/settlement_visuals.SCALE) — it also scales the model.
_DONOR_SCALE = 1.5  # tools/settlement_visuals.SCALE — not imported, a dependency on the external module is unneeded
FLAT_RADIUS = {"town": 7.55 * _DONOR_SCALE, "castle": 3.12 * _DONOR_SCALE, "village": 5.0, "hideout": 4.0}
# Descent — minimum width (on flat ground, where there is little to smooth anyway) and the limiting
# slope (height difference / distance): we give exactly as many metres outward as needed so the
# slope is not steeper than MAX_SLOPE. 0.6 is roughly 31°, noticeably gentler than a bare cliff,
# but still reads as a slope rather than a second flat pad.
MIN_BLEND = {"town": 6.0, "castle": 3.0, "village": 3.0, "hideout": 3.0}
MAX_BLEND = 24.0
MAX_SLOPE = 0.6

# Shape irregularity: the pad border "breathes" with angle — a sum of 2-3 low-frequency sines with
# random phase (one per settlement, deterministic by id). AMOUNT — by what fraction of the radius
# the border may shrink/stretch.
BLOB_AMOUNT = 0.22

# Bumps inside the pad: amplitude (m) and wavelength (m) — the same smoothed-noise trick as in
# make_equus_map.py (wave()). Making them weaker towards the centre is pointless — even right under
# walls real ground is not perfectly flat, and the engine places the model by the point's overall
# height, not by each vertex.
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
    """Radius multiplier by angle (around 1.0) — 2-3 random harmonics, a phase per settlement."""
    rng = np.random.default_rng(seed)
    mod = np.ones_like(theta)
    for freq in (2, 3, 5):
        amp = rng.uniform(0.3, 1.0)
        phase = rng.uniform(0.0, 2 * math.pi)
        mod = mod + amp * np.sin(freq * theta + phase)
    # normalise the range to BLOB_AMOUNT (a sum of three sines can exceed ±1)
    mod = mod - 1.0  # centre it; the sum of harmonics averages ~0 by itself
    peak = max(float(np.max(np.abs(mod))), 1e-6)
    return 1.0 + (mod / peak) * BLOB_AMOUNT


def bump_noise(h, w, seed, wavelength, scale):
    """Smoothed noise of the given size (a small random grid stretched bicubically)."""
    side_h = max(2, int(round(h / wavelength)))
    side_w = max(2, int(round(w / wavelength)))
    rng = np.random.default_rng(seed)
    small = rng.normal(0.0, 1.0, (side_h, side_w)).astype(np.float32)
    img = Image.fromarray(small, mode="F").resize((w, h), Image.BICUBIC)
    field = np.asarray(img, dtype=np.float32)
    return field / max(float(field.std()), 1e-6) * scale


def edge_height_diff(original, scale, px, py, target, radius):
    """Mean height difference (original terrain minus target) over a ring of the given radius — how
    much actually needs smoothing at the pad border, to choose the descent width."""
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

    heights = equus_map.heights().copy()  # (S, S), row 0 is south; metres
    original = heights.copy()
    size = heights.shape[0]
    scale = (size - 1) / equus_map.MAP_SIZE  # pixels per metre (ours is 1025/1024 ~= 1.0)

    # Do not touch water at all (03.10.2026, in-game screenshot: at Mount Aris — it is on the shore —
    # the descent reached the sea and raised the water above sea level; the terrain classification
    # (water/land) the engine uses to draw waves is not recomputed from height — it stayed "water",
    # and there were waves on what is now land). The mask uses the CURRENT (original, pre-edit)
    # terrain classification.
    water_mask = np.isin(equus_map.terrain_map(), (equus_map.WATER, equus_map.LAKE, equus_map.RIVER))
    if water_mask.shape != heights.shape:
        raise SystemExit("eq_map_terrain.png %s не совпадает по размеру с картой высот %s"
                         % (water_mask.shape, heights.shape))

    best_w = np.zeros_like(heights)

    for i, (sid, kind, x, y) in enumerate(settlements):
        rf = FLAT_RADIUS[kind]
        px, py = x * scale, y * scale
        # pad centre — the settlement pixel in the ORIGINAL (unmodified) terrain: the pad does not
        # invent a new height but removes bumps/slope around the already chosen point
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
        dist_eff = dist / np.clip(mod, 0.5, 1.5)  # "breathing" border, without self-intersections

        t = (dist_eff - rf) / max(rb, 1e-6)
        w = 1.0 - smoothstep(t)  # 1 inside the pad, 0 beyond the descent
        w[dist_eff <= rf] = 1.0
        w[dist_eff >= reach] = 0.0
        w[water_mask[y0:y1, x0:x1]] = 0.0  # sea/lake/river — do not raise and do not add bumps

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

    # writing — the same flip equus_map does on reading ([::-1]), so that the file again has
    # row 0 = north, as in the original eq_map_heightmap.png; mode is not set — as in
    # make_equus_map.py, PIL infers it from the uint16 dtype (the same encoding as the original).
    Image.fromarray(raw[::-1]).save(HEIGHTMAP)
    log("записан", HEIGHTMAP)
    log("дальше: py -3 tools\\write_terrain_heights.py Module  (запечь в terrain.bin)")


if __name__ == "__main__":
    main()
