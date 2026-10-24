# -*- coding: utf-8 -*-
"""Textures of the new pony with the mod's names and layout — for import by the editor.

  py tools/make_pony_textures.py

From the model's textures (assets/pony/textures, put there by make_pony_model.py) three files are made
following the other races' pattern (eq_twilight_body_d/_n/_s):
  eq_pony_body_d.png — color (2048);
  eq_pony_body_n.png — normals (2048);
  eq_pony_body_s.png — gloss: Meshy gives roughness as a separate image, gloss = 1 - roughness.
The game's skin shader does not read metalness, so it is skipped.
They stay in assets/pony/textures — from there they are imported in the editor (Resource Browser -> Import,
package twilight); putting them into Module/AssetSources in advance is not allowed (see tools/make_deer_textures.py).
"""
import os

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "assets", "pony", "textures")
SIZE = (2048, 2048)


def log(*a):
    print("[pony-tex]", *a, flush=True)


def load(name):
    return Image.open(os.path.join(SRC, name)).convert("RGB").resize(SIZE, Image.LANCZOS)


load("eq_pony_color.png").save(os.path.join(SRC, "eq_pony_body_d.png"))
log("цвет -> eq_pony_body_d.png")

load("eq_pony_normal.png").save(os.path.join(SRC, "eq_pony_body_n.png"))
log("нормали -> eq_pony_body_n.png")

rough = load("eq_pony_roughness.png").split()[0]
spec = ImageOps.invert(rough)
Image.merge("RGB", (spec, spec, spec)).save(os.path.join(SRC, "eq_pony_body_s.png"))
log("блеск -> eq_pony_body_s.png")
