# Overview of the whole Equestria at War map: whose states are where. Needed to pick a part of the
# continent for our world map.
#
#   py -3 tools\eaw_overview.py [output folder]
#
# Writes docs/reference/eaw_owners.png (state owners over the terrain, large countries
# labelled) and docs/reference/eaw_owners.json (country -> frame and number of states).
import collections
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eaw_reference as ref  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else ref.OUT
SCALE = 0.5


def country_names():
    names = ref.read_localisation()
    return lambda tag: names.get(tag, names.get(tag + "_DEF", tag))


def main():
    os.makedirs(OUT, exist_ok=True)
    states = ref.read_states()
    ids, _kinds = ref.province_map()
    owner_of = {}
    for s in states:
        for p in s["provinces"]:
            owner_of[p] = s["owner"]
    tags = sorted({s["owner"] for s in states})
    index = {t: i + 1 for i, t in enumerate(tags)}
    lut = np.zeros(ids.max() + 1, dtype=np.int32)
    for p, t in owner_of.items():
        if p < len(lut):
            lut[p] = index[t]
    own = lut[ids]

    rng = np.random.default_rng(7)
    palette = np.vstack([[20, 30, 60], rng.integers(60, 255, size=(len(tags), 3))]).astype(np.uint8)
    height = np.asarray(Image.open(os.path.join(ref.EAW, "map", "heightmap.bmp")), dtype=np.float32) / 255
    img = palette[own].astype(np.float32) * (0.55 + 0.6 * height[..., None])
    land = own > 0
    img[~land] = (15, 25, 55)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    im = im.resize((int(im.width * SCALE), int(im.height * SCALE)), Image.NEAREST)
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype("arial.ttf", 12)
    name = country_names()

    counts = collections.Counter(s["owner"] for s in states)
    info = {}
    for tag in tags:
        ys, xs = np.nonzero(own == index[tag])
        info[tag] = {"name": name(tag), "states": counts[tag],
                     "frame": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                     "centre": [float(xs.mean()), float(ys.mean())]}
        if counts[tag] >= 6:
            cx, cy = xs.mean() * SCALE, ys.mean() * SCALE
            draw.text((cx, cy), f"{tag} {name(tag)}", fill=(255, 255, 255), font=font,
                      stroke_width=2, stroke_fill=(0, 0, 0), anchor="mm")
    # HOI4 256-pixel grid, for choosing the frame
    for x in range(0, ids.shape[1], 256):
        draw.line([(x * SCALE, 0), (x * SCALE, im.height)], fill=(90, 90, 90))
        draw.text((x * SCALE + 2, 2), str(x), fill=(200, 200, 200), font=font)
    for y in range(0, ids.shape[0], 256):
        draw.line([(0, y * SCALE), (im.width, y * SCALE)], fill=(90, 90, 90))
        draw.text((2, y * SCALE + 2), str(y), fill=(200, 200, 200), font=font)
    im.save(os.path.join(OUT, "eaw_owners.png"))
    with open(os.path.join(OUT, "eaw_owners.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    ref.log(f"стран: {len(tags)}; обзор {im.size} -> {OUT}")


if __name__ == "__main__":
    main()
