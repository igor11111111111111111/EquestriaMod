"""Recolouring vanilla armour into changeling chitin.

  py -3 tools/recolor_armor.py [package]      default package - changeling

Where things come from:
  - the package's meshes and textures were dumped by the tpac_export tool into assets/reference/vanilla_armor/<mesh>/;
  - every vanilla armour has a diffuse (_d) and a clan colour mask (_c): the red channel is the clan's first
    colour, green the second. The engine paints cloth and trims by it, so "black with turquoise and
    green stripes" comes out by itself if the clan colours are set (tools/world_data.py, the hive).

What the script does:
  1. turns the diffuse into chitin: an almost black base, with a cold turquoise sheen toward the highlights;
  2. leaves the masked areas neutral light so the clan colour lies cleanly, not on top of sand;
  3. puts the result into assets/pony_armor_changeling/textures/<name>_d.png - these textures
     are imported in the editor; normals and specular are taken from vanilla (they are not recoloured).
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import armor_catalog  # noqa: E402

PACK = sys.argv[1] if len(sys.argv) > 1 else "changeling"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "reference", "vanilla_armor")
OUT = os.path.join(ROOT, "assets", f"pony_armor_{PACK}", "textures")

# Chitin: from almost black to a turquoise sheen (colours are matched to the changeling model,
# tools/make_changeling.py - the body there has the same palette).
CHITIN = [
    (0.00, (0.012, 0.014, 0.018)),
    (0.35, (0.045, 0.060, 0.075)),
    (0.70, (0.090, 0.200, 0.215)),
    (1.00, (0.330, 0.720, 0.700)),
]
# In our tests the engine never painted the areas from the _c mask with faction colours (neither in a
# conversation nor with garish clan and culture colours), so we bake the hive colour straight into the texture:
# cloth and trims are a dark turquoise with a green glow, not a neutral underlay.
TRIM = [
    (0.00, (0.010, 0.030, 0.030)),
    (0.40, (0.020, 0.110, 0.105)),
    (0.75, (0.045, 0.300, 0.260)),
    (1.00, (0.180, 0.620, 0.420)),
]
PREFIX = "eq_ch_"  # our textures and materials: eq_ch_<vanilla name>


def log(*a):
    print("[recolor]", *a, flush=True)


def ramp(t, stops):
    out = np.zeros(t.shape + (3,), np.float32)
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (t >= p0) & (t <= p1)
        k = ((t[m] - p0) / max(p1 - p0, 1e-6))[..., None]
        out[m] = np.array(c0, np.float32) * (1 - k) + np.array(c1, np.float32) * k
    out[t < stops[0][0]] = stops[0][1]
    out[t > stops[-1][0]] = stops[-1][1]
    return out


def find_textures():
    """{texture name without _d: (path to diffuse, path to mask or None)}"""
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


def recolor(diffuse_path, mask_path):
    img = np.asarray(Image.open(diffuse_path).convert("RGB"), np.float32) / 255.0
    luma = img @ np.array([0.299, 0.587, 0.114], np.float32)
    chitin = ramp(luma, CHITIN)
    if mask_path:
        m = Image.open(mask_path).convert("RGB").resize(
            (img.shape[1], img.shape[0]), Image.BILINEAR)
        mask = np.asarray(m, np.float32)[..., :2].max(-1) / 255.0
    else:
        mask = np.zeros(luma.shape, np.float32)
    trim = ramp(luma, TRIM)
    out = chitin * (1 - mask[..., None]) + trim * mask[..., None]
    return Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8))


def main():
    os.makedirs(OUT, exist_ok=True)
    textures = find_textures()
    log(f"текстур в пакете {PACK}: {len(textures)}")
    for base, (diffuse, mask) in sorted(textures.items()):
        # the prefix is mandatory: otherwise the name matches the vanilla texture and the material picks the wrong one
        out = os.path.join(OUT, PREFIX + base + "_d.png")
        recolor(diffuse, mask).save(out)
        log(f"  {base}: маска {'есть' if mask else 'нет'} -> {os.path.basename(out)}")
    log("готово:", OUT)


main()
