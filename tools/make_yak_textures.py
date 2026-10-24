# -*- coding: utf-8 -*-
"""Yak textures with the mod's names and layout, in AssetSources for import by the editor.

  py tools/make_yak_textures.py

From the baked model textures (assets/yak/textures, written by make_yak.py) three files are made following
the pony pattern (eq_twilight_body_d/_n/_s):
  eq_yak_body_d.png - colour (2048);
  eq_yak_body_n.png - normals (2048);
  eq_yak_body_s.png - gloss: glTF stores roughness in the G channel, gloss = 1 - roughness (2048).
They stay in assets/yak/textures; from there they are imported in the editor (Resource Browser → Import,
package twilight), and the editor itself copies the file to Module/AssetSources/twilight. Putting them there
in advance is wrong: on import the editor copies the file into the same folder and crashes with "Unable to copy ...
to Assets folder". The package itself stores only a reference to the PNG and parameters, the pixels are baked by the editor
into RuntimeDataCache, so the texture cannot be put into the mod by code.
"""
import os

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "assets", "yak", "textures")
OUT = SRC
SIZE = (2048, 2048)


def log(*a):
    print("[yak-tex]", *a, flush=True)


color = Image.open(os.path.join(SRC, "eq_yak_texture_0.png")).convert("RGB").resize(SIZE, Image.LANCZOS)
color.save(os.path.join(OUT, "eq_yak_body_d.png"))
log("цвет ->", "eq_yak_body_d.png")

normal = Image.open(os.path.join(SRC, "eq_yak_normal.png")).convert("RGB").resize(SIZE, Image.LANCZOS)
normal.save(os.path.join(OUT, "eq_yak_body_n.png"))
log("нормали ->", "eq_yak_body_n.png")

mr = Image.open(os.path.join(SRC, "eq_yak_texture_0_metallic_roughness.png")).convert("RGB").resize(SIZE, Image.LANCZOS)
roughness = mr.split()[1]
spec = ImageOps.invert(roughness)
Image.merge("RGB", (spec, spec, spec)).save(os.path.join(OUT, "eq_yak_body_s.png"))
log("блеск ->", "eq_yak_body_s.png")
