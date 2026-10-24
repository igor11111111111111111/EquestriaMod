# -*- coding: utf-8 -*-
r"""Hive armour: recolouring vanilla Aserai armour into chitin with glowing veins.

  py -3 tools/hive_armor.py

Where things come from:
  - meshes and textures of the Aserai tree are exported to assets/reference/vanilla_armor/<mesh>/
    (with the tpac_export utility, see tools/armor_catalog.py — the list of items is there too);
  - vanilla armour has four textures: colour (_d), clan colour mask (_c), normals (_n) and
    specular (_s). Normals and specular stay vanilla, there is nothing to recolour in them.

What the script does: writes eq_ch_<name>_d.png — the hive armour colour. It contains everything:
  - almost black chitin with a cold turquoise sheen in the highlights;
  - dark turquoise on cloth and trims (areas from the _c mask);
  - BRIGHT turquoise pattern lines: veins in the gaps between plates and mail rings, the cloth
    edge and a honeycomb on top of it.

Why the pattern is baked in rather than glowing. The armour shader pbr_shading has a
self_illumination flag, and it takes the glow map from slot 1 — the same slot where vanilla keeps
the clan colour mask. It can be done, and we did it, but we measured the cost: ONE mesh with this
flag combination makes the engine build 1332 shaders (about six per second — four minutes), and
the result is not saved anywhere: the game only reads Shaders\D3D11\compressed_shader_cache.sack.
That is four minutes on EVERY launch (measured 24.09.2026). So the glow is baked into the colour:
in daylight the difference is barely visible, while the flags stay vanilla and everything is
prebuilt.

Next: import the resulting PNGs in the editor, then materials and mesh binding by code
(tools/hive_material.ps1 -NoGlow).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import armor_catalog  # noqa: E402

PACK = "changeling"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "reference", "vanilla_armor")
OUT = os.path.join(ROOT, "assets", "hive_armor", "textures")
PREFIX = "eq_ch_"      # our textures and materials: eq_ch_<vanilla name>

# Chitin: from almost black to a cold turquoise sheen (same palette as the changeling body,
# tools/make_changeling_model.py).
CHITIN = [
    (0.00, (0.012, 0.014, 0.018)),
    (0.35, (0.045, 0.060, 0.075)),
    (0.70, (0.090, 0.200, 0.215)),
    (1.00, (0.330, 0.720, 0.700)),
]
# Cloth and trims (areas from the _c mask): almost black with a greenish tint. It must not be
# lighter — the glow is laid on top, and the cloth turned into a solid turquoise sheet.
TRIM = [
    (0.00, (0.008, 0.020, 0.020)),
    (0.40, (0.014, 0.055, 0.052)),
    (0.75, (0.030, 0.120, 0.110)),
    (1.00, (0.080, 0.260, 0.210)),
]

GLOW_COLOUR = (0.35, 1.00, 0.88)   # line colour: light hive turquoise
GLOW_MIX = 0.95        # how much the lines cover the chitin under them (1 — fully)
# LINES must glow, not areas: filling by the mask turned the robe into a turquoise lantern
# (seen in the preview 24.09.2026). Hence three sources — gaps between plates, the cloth edge
# and the honeycomb over the cloth; all three are thin.
VEIN_BLUR = 9         # blur radius used to find gaps (the larger, the wider the veins)
VEIN_LOW = 0.05       # this much darker than the surroundings — the vein starts to light up
VEIN_HIGH = 0.30      # and this much — it glows at full strength
VEIN_POWER = 0.85     # vein brightness
EDGE_BLUR = 4         # how many pixels the mask is blurred by to find its edge
EDGE_GLOW = 0.80      # cloth edge brightness
CELL = 110            # honeycomb cell side in pixels (pattern over the cloth)
CELL_LINE = 0.055     # honeycomb line thickness, fraction of the side
CELL_GLOW = 0.70      # honeycomb brightness


def log(*a):
    print("[hive]", *a, flush=True)


def ramp(t, stops):
    out = np.zeros(t.shape + (3,), np.float32)
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (t >= p0) & (t <= p1)
        k = ((t[m] - p0) / max(p1 - p0, 1e-6))[..., None]
        out[m] = np.array(c0, np.float32) * (1 - k) + np.array(c1, np.float32) * k
    out[t < stops[0][0]] = stops[0][1]
    out[t > stops[-1][0]] = stops[-1][1]
    return out


def smoothstep(x, low, high):
    t = np.clip((x - low) / max(high - low, 1e-6), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def find_textures():
    """{set name: (diffuse path, mask path or None)} — over all items of the pack."""
    found = {}
    for row in armor_catalog.pieces(PACK):
        folder = os.path.join(SRC, row["mesh"])
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if not name.endswith("_d.dds"):
                continue
            base = name[:-6]
            if base in found:
                continue
            mask = os.path.join(folder, base + "_c.dds")
            found[base] = (os.path.join(folder, name), mask if os.path.exists(mask) else None)
    return found


def read(path, size=None):
    img = Image.open(path).convert("RGB")
    if size and img.size != size:
        img = img.resize(size, Image.BILINEAR)
    return np.asarray(img, np.float32) / 255.0


_cells = {}


def honeycomb(shape):
    """Honeycomb: a grid of HEXagons, one is a line, zero is empty.

    Three sets of slanted lines give a triangular lattice, not a honeycomb (checked in the
    preview 24.09.2026). Real hexagons are the Voronoi cell borders of a hexagonal lattice:
    we compute distances to the two nearest centres, the line is where they are nearly equal.
    """
    if shape in _cells:
        return _cells[shape]
    h, w = shape
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    step_x = CELL * 0.866                      # horizontal lattice step
    col = np.floor(x / step_x)
    row = np.floor((y - np.where(col % 2 == 0, 0.0, CELL / 2)) / CELL)
    best = np.full(shape, 1e9, np.float32)
    second = np.full(shape, 1e9, np.float32)
    for dc in (-1, 0, 1):
        for dr in (-1, 0, 1, 2):
            c = col + dc
            r = row + dr
            cx = (c + 0.5) * step_x
            cy = (r + 0.5) * CELL + np.where(c % 2 == 0, 0.0, CELL / 2)
            d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            closer = d < best
            second = np.where(closer, best, np.minimum(second, d))
            best = np.where(closer, d, best)
    lines = 1.0 - smoothstep(second - best, 0.0, CELL * CELL_LINE)
    _cells[shape] = lines
    return lines


def make(diffuse_path, mask_path):
    img = read(diffuse_path)
    size = (img.shape[1], img.shape[0])
    luma = img @ np.array([0.299, 0.587, 0.114], np.float32)
    mask = read(mask_path, size)[..., :2].max(-1) if mask_path else np.zeros(luma.shape, np.float32)

    # ---- colour
    colour = ramp(luma, CHITIN) * (1 - mask[..., None]) + ramp(luma, TRIM) * mask[..., None]

    # ---- glow: gaps between plates (where darker than the surroundings), cloth edge and honeycomb
    blurred = np.asarray(Image.fromarray((luma * 255).astype(np.uint8))
                         .filter(ImageFilter.GaussianBlur(VEIN_BLUR)), np.float32) / 255.0
    veins = smoothstep(blurred - luma, VEIN_LOW, VEIN_HIGH) * VEIN_POWER
    # edge: where the blurred mask differs from the sharp one, i.e. along its border
    soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(EDGE_BLUR)), np.float32) / 255.0
    edge = smoothstep(np.abs(soft - mask), 0.05, 0.25) * EDGE_GLOW
    cells = honeycomb(luma.shape) * (mask > 0.5) * CELL_GLOW
    glow = np.clip(np.maximum(np.maximum(veins, edge), cells), 0.0, 1.0)

    # ---- bake the lines into the colour: bright turquoise over chitin, keeping its shading
    # The lines keep the source shading, but are not allowed to darken along with the mail:
    # without glow a too-dark pattern simply disappears.
    line = np.array(GLOW_COLOUR, np.float32)[None, None, :] * (0.78 + 0.22 * luma[..., None])
    weight = (glow * GLOW_MIX)[..., None]
    colour = colour * (1.0 - weight) + line * weight

    return Image.fromarray(np.clip(colour * 255.0, 0, 255).astype(np.uint8)), float(glow.mean())


def main():
    os.makedirs(OUT, exist_ok=True)
    textures = find_textures()
    log("наборов текстур в асерайском дереве:", len(textures))
    for base, (diffuse, mask) in sorted(textures.items()):
        colour, share = make(diffuse, mask)
        colour.save(os.path.join(OUT, PREFIX + base + "_d.png"))
        log("  %-34s маска %s, узор на %.0f%% площади"
            % (base, "есть" if mask else "нет", 100 * share))
    log("готово:", OUT)


main()
