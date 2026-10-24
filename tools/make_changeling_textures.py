# -*- coding: utf-8 -*-
"""Текстуры чейнджлинга в именах и раскладке мода — для импорта редактором.

  py -3 tools/make_changeling_textures.py

Из текстур модели (assets/changeling/textures, их выгружает make_changeling.py) делаются три файла по
образцу пони и яка (eq_twilight_body_d/_n/_s):
  eq_changeling_body_d.png — цвет (2048);
  eq_changeling_body_n.png — нормали (2048);
  eq_changeling_body_s.png — блеск: у модели отдельная карта шероховатости, блеск = 1 - шероховатость.
Файлы остаются в assets/changeling/textures — оттуда их импортируют в редакторе (Resource Browser →
Import, пакет twilight), и редактор сам копирует их в Module/AssetSources. Класть их туда заранее
нельзя: при импорте редактор копирует файл в ту же папку и падает с «Unable to copy … to Assets
folder». Пакет хранит только ссылку на PNG, пиксели печёт редактор в RuntimeDataCache — поэтому
кодом текстуру в мод не положить.
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
