# -*- coding: utf-8 -*-
"""Пробная полосатая текстура для гривы/хвоста пони — проверить, как ляжет цвет из редактора
поверх диагональных полос (шейдер волос только умножает выбранный цвет на текстуру, отдельной
маски под два цвета у него нет, см. tools/tpac_export mat-info hair_shader_aniso — один слот
диффуза, полосы дают контраст светлого/тёмного в ОДНОМ выбранном цвете, а не два разных цвета).

  py tools/make_pony_hair_stripe_texture.py

Результат — assets/pony/textures/eq_pony_hair_stripe_d.png, оттуда импортировать в редакторе
(Resource Browser -> Import, пакет twilight), как обычную текстуру пони.
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "pony", "textures", "eq_pony_hair_stripe_d.png")
SIZE = 1024
STRIPE_WIDTH = 48       # пикселей на полосу — при 1024 даёт полос десяток по диагонали
LIGHT = 255              # светлая полоса — полный выбранный цвет
DARK = 120               # тёмная полоса — тот же цвет, но заметно притушенный

img = Image.new("RGB", (SIZE, SIZE))
px = img.load()
for y in range(SIZE):
    for x in range(SIZE):
        # диагональ: складываем координаты, а не берём одну — полосы идут под 45°,
        # вдоль пряди, а не поперёк
        band = ((x + y) // STRIPE_WIDTH) % 2
        v = LIGHT if band == 0 else DARK
        px[x, y] = (v, v, v)
img.save(OUT)
print("[hair-stripe] записано:", OUT)
