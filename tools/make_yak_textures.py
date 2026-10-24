# -*- coding: utf-8 -*-
"""Текстуры яка в именах и раскладке мода — в AssetSources для импорта редактором.

  py tools/make_yak_textures.py

Из запечённых текстур модели (assets/yak/textures, их пишет make_yak.py) делаются три файла по
образцу пони (eq_twilight_body_d/_n/_s):
  eq_yak_body_d.png — цвет (2048);
  eq_yak_body_n.png — нормали (2048);
  eq_yak_body_s.png — блеск: у glTF в канале G лежит шероховатость, блеск = 1 - шероховатость (2048).
Остаются в assets/yak/textures — оттуда их импортируют в редакторе (Resource Browser → Import,
пакет twilight), и редактор сам копирует файл в Module/AssetSources/twilight. Класть их туда
заранее нельзя: при импорте редактор копирует файл в ту же папку и падает с «Unable to copy ...
to Assets folder». Сам пакет хранит только ссылку на PNG и параметры, пиксели печёт редактор
в RuntimeDataCache — поэтому кодом текстуру в мод не положить.
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
