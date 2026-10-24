# -*- coding: utf-8 -*-
"""Doe textures with the mod's names and layout - into AssetSources for import by the editor.

  py tools/make_deer_textures.py

From the model's baked textures (assets/deer/textures, written by make_deer_model.py) three
files are made following the pony pattern (eq_twilight_body_d/_n/_s):
  eq_deer_body_d.png - colour (2048);
  eq_deer_body_n.png - normals (2048);
  eq_deer_body_s.png - specular: glTF keeps roughness in the G channel, specular = 1 - roughness.
They stay in assets/deer/textures - they are imported from there in the editor (Resource Browser → Import,
package twilight), and the editor copies the file into Module/AssetSources/twilight itself. Putting them
there beforehand is not allowed: on import the editor copies the file into the same folder and crashes with
"Unable to copy ... to Assets folder". The package itself stores only a reference to the PNG and parameters;
the pixels are baked by the editor into RuntimeDataCache - so a texture cannot be put into the mod by code.
"""
import os

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "assets", "deer", "textures")
OUT = SRC
SIZE = (2048, 2048)


def log(*a):
    print("[deer-tex]", *a, flush=True)


color = Image.open(os.path.join(SRC, "eq_deer_color.png")).convert("RGB").resize(SIZE, Image.LANCZOS)
color.save(os.path.join(OUT, "eq_deer_body_d.png"))
log("цвет ->", "eq_deer_body_d.png")

normal = Image.open(os.path.join(SRC, "eq_deer_normal.png")).convert("RGB").resize(SIZE, Image.LANCZOS)
normal.save(os.path.join(OUT, "eq_deer_body_n.png"))
log("нормали ->", "eq_deer_body_n.png")

mr = Image.open(os.path.join(SRC, "eq_deer_mr.png")).convert("RGB").resize(SIZE, Image.LANCZOS)
roughness = mr.split()[1]
spec = ImageOps.invert(roughness)
Image.merge("RGB", (spec, spec, spec)).save(os.path.join(OUT, "eq_deer_body_s.png"))
log("блеск ->", "eq_deer_body_s.png")
