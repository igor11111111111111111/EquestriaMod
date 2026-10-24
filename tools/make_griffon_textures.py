# -*- coding: utf-8 -*-
"""Griffon textures with the mod's names and layout — for import by the editor.

  py -3 tools/make_griffon_textures.py

From the model's textures (assets/griffon/textures, exported by make_griffon.py) three files are made
following the pony and yak pattern (eq_twilight_body_d/_n/_s):
  eq_griffon_body_d.png — color (2048);
  eq_griffon_body_n.png — normals (2048);
  eq_griffon_body_s.png — gloss: the model has a separate roughness map, gloss = 1 - roughness.
The files stay in assets/griffon/textures — from there they are imported in the editor (Resource
Browser → Import, package twilight), and the editor copies them to Module/AssetSources by itself. Putting
them there in advance is not allowed: on import the editor copies the file into the same folder and fails
with "Unable to copy … to Assets folder". The package stores only a link to the PNG, the editor bakes the
pixels into RuntimeDataCache — so the texture cannot be put into the mod by code.
"""
import os

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "assets", "griffon", "textures")
SIZE = (2048, 2048)


def log(*a):
    print("[griffon-tex]", *a, flush=True)


def take(name):
    path = os.path.join(SRC, name)
    if not os.path.exists(path):
        raise SystemExit("нет файла %s — сначала прогоните make_griffon.py" % path)
    return Image.open(path)


color = take("eq_griffon_texture_0.png").convert("RGB").resize(SIZE, Image.LANCZOS)
color.save(os.path.join(SRC, "eq_griffon_body_d.png"))
log("цвет -> eq_griffon_body_d.png")

normal = take("eq_griffon_normal.png").convert("RGB").resize(SIZE, Image.LANCZOS)
normal.save(os.path.join(SRC, "eq_griffon_body_n.png"))
log("нормали -> eq_griffon_body_n.png")

rough = take("eq_griffon_texture_0_roughness_png.png").convert("L").resize(SIZE, Image.LANCZOS)
spec = ImageOps.invert(rough)
Image.merge("RGB", (spec, spec, spec)).save(os.path.join(SRC, "eq_griffon_body_s.png"))
log("блеск -> eq_griffon_body_s.png")
log("готово: импортируйте три файла в редакторе, затем tools\\griffon_material.ps1")
