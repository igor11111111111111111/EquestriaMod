# -*- coding: utf-8 -*-
"""Dragon textures with the mod's names and layout, for import by the editor.

  py -3 tools/make_dragon_textures.py

From the model textures (assets/dragon/textures, exported by make_dragon.py) three files are made following
the pony and yak pattern (eq_twilight_body_d/_n/_s):
  eq_dragon_body_d.png - colour (2048);
  eq_dragon_body_n.png - normals (2048);
  eq_dragon_body_s.png - gloss: the model has a separate roughness map, gloss = 1 - roughness.
The files stay in assets/dragon/textures; from there they are imported in the editor (Resource Browser →
Import, package twilight), and the editor itself copies them to Module/AssetSources. Putting them there in advance
is wrong: on import the editor copies the file into the same folder and crashes with "Unable to copy … to Assets
folder". The package stores only a reference to the PNG, the pixels are baked by the editor into RuntimeDataCache, so
the texture cannot be put into the mod by code.
"""
import os

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "assets", "dragon", "textures")
SIZE = (2048, 2048)


def log(*a):
    print("[dragon-tex]", *a, flush=True)


def take(name):
    path = os.path.join(SRC, name)
    if not os.path.exists(path):
        raise SystemExit("нет файла %s — сначала прогоните make_dragon.py" % path)
    return Image.open(path)


color = take("eq_dragon_texture_0.png").convert("RGB").resize(SIZE, Image.LANCZOS)
color.save(os.path.join(SRC, "eq_dragon_body_d.png"))
log("цвет -> eq_dragon_body_d.png")

normal = take("eq_dragon_normal.png").convert("RGB").resize(SIZE, Image.LANCZOS)
normal.save(os.path.join(SRC, "eq_dragon_body_n.png"))
log("нормали -> eq_dragon_body_n.png")

rough = take("eq_dragon_texture_0_roughness_png.png").convert("L").resize(SIZE, Image.LANCZOS)
spec = ImageOps.invert(rough)
Image.merge("RGB", (spec, spec, spec)).save(os.path.join(SRC, "eq_dragon_body_s.png"))
log("блеск -> eq_dragon_body_s.png")
log("готово: импортируйте три файла в редакторе, затем tools\\dragon_material.ps1")
