# -*- coding: utf-8 -*-
"""Changeling textures with the mod's names and layout, for import by the editor.

  py -3 tools/make_changeling_textures.py

From the model's textures (assets/changeling/textures, exported by make_changeling.py) three files are made
following the pony and yak pattern (eq_twilight_body_d/_n/_s):
  eq_changeling_body_d.png — colour (2048);
  eq_changeling_body_n.png — normals (2048);
  eq_changeling_body_s.png — gloss: the model has a separate roughness map, gloss = 1 - roughness.
The files stay in assets/changeling/textures; from there they are imported in the editor (Resource Browser →
Import, twilight package), and the editor itself copies them to Module/AssetSources. Putting them there in advance
is not allowed: on import the editor copies the file into the same folder and fails with «Unable to copy … to Assets
folder». The package stores only a link to the PNG, the pixels are baked by the editor into RuntimeDataCache, so
a texture cannot be put into the mod by code.
"""
import os

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "assets", "changeling3d", "textures")
SIZE = (2048, 2048)


def log(*a):
    print("[changeling-tex]", *a, flush=True)


def take(name):
    path = os.path.join(SRC, name)
    if not os.path.exists(path):
        raise SystemExit("нет файла %s — сначала прогоните make_changeling.py" % path)
    return Image.open(path)


color = take("eq_changeling_texture_0.png").convert("RGB").resize(SIZE, Image.LANCZOS)
color.save(os.path.join(SRC, "eq_changeling_body_d.png"))
log("цвет -> eq_changeling_body_d.png")

normal = take("eq_changeling_normal.png").convert("RGB").resize(SIZE, Image.LANCZOS)
normal.save(os.path.join(SRC, "eq_changeling_body_n.png"))
log("нормали -> eq_changeling_body_n.png")

rough = take("eq_changeling_texture_0_roughness_png.png").convert("L").resize(SIZE, Image.LANCZOS)
spec = ImageOps.invert(rough)
Image.merge("RGB", (spec, spec, spec)).save(os.path.join(SRC, "eq_changeling_body_s.png"))
log("блеск -> eq_changeling_body_s.png")
log("готово: импортируйте три файла в редакторе, затем tools\\changeling_material.ps1")
