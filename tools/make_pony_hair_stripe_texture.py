# -*- coding: utf-8 -*-
"""Trial striped texture for the pony mane/tail - to check how the color from the editor lies
over diagonal stripes (the hair shader only multiplies the chosen color by the texture, it has no separate
mask for two colors, see tools/tpac_export mat-info hair_shader_aniso - one diffuse slot,
the stripes give a light/dark contrast in ONE chosen color, not two different colors).

  py tools/make_pony_hair_stripe_texture.py

Result - assets/pony/textures/eq_pony_hair_stripe_d.png, import it from there in the editor
(Resource Browser -> Import, package twilight), like a regular pony texture.
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "pony", "textures", "eq_pony_hair_stripe_d.png")
SIZE = 1024
STRIPE_WIDTH = 48       # pixels per stripe - at 1024 gives about a dozen stripes along the diagonal
LIGHT = 255              # light stripe - the full chosen color
DARK = 120               # dark stripe - the same color, but noticeably dimmed

img = Image.new("RGB", (SIZE, SIZE))
px = img.load()
for y in range(SIZE):
    for x in range(SIZE):
        # diagonal: we add the coordinates instead of taking one - the stripes run at 45°,
        # along the strand, not across it
        band = ((x + y) // STRIPE_WIDTH) % 2
        v = LIGHT if band == 0 else DARK
        px[x, y] = (v, v, v)
img.save(OUT)
print("[hair-stripe] записано:", OUT)
