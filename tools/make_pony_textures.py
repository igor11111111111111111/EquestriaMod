# -*- coding: utf-8 -*-
"""Текстуры новой пони в именах и раскладке мода — для импорта редактором.

  py tools/make_pony_textures.py

Из текстур модели (assets/pony/textures, их кладёт make_pony_model.py) делаются три файла
по образцу остальных рас (eq_twilight_body_d/_n/_s):
  eq_pony_body_d.png — цвет (2048);
  eq_pony_body_n.png — нормали (2048);
  eq_pony_body_s.png — блеск: у Meshy шероховатость отдельной картинкой, блеск = 1 - шероховатость.
Металличность игровой шейдер кожи не читает, её пропускаем.
Остаются в assets/pony/textures — оттуда их импортируют в редакторе (Resource Browser -> Import,
пакет twilight); класть их в Module/AssetSources заранее нельзя (см. tools/make_deer_textures.py).
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
