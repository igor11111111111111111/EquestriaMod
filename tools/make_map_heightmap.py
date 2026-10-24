# Heightmap generator for the mod's world map: an image the editor accepts via the
# Import HeightMap button (png, raw, tga formats). The relief is defined by code, nothing has to be sculpted by hand.
#
# blender --background --factory-startup --python make_map_heightmap.py -- <out_dir> [size]
#
# Result: <out_dir>\eq_map_heightmap.png (16 bit, grayscale) and the preview eq_map_preview.png.
#
# How values are read: black is the bottom (sea floor), white is the top. The sea level in the editor is set
# separately, so the shore is defined by where the height crosses SEA_LEVEL.
import os
import sys

import bpy
import numpy as np

ARGS = sys.argv[sys.argv.index("--") + 1:]
OUT = ARGS[0]
SIZE = int(ARGS[1]) if len(ARGS) > 1 else 1024

SEA_LEVEL = 0.35        # fraction of height, below it - water
PLAIN = 0.45            # the plain on which settlements stand
MOUNTAIN = 0.85         # mountain peaks
# Settlement points as fractions of the map size (x, y) and the radius of the flat area as a fraction
SETTLEMENTS = [
    ("Кантерлот", 0.38, 0.42, 0.045),
    ("Понивилль", 0.58, 0.58, 0.035),
]


def log(*a):
    print("[map]", *a, flush=True)


yy, xx = np.mgrid[0:SIZE, 0:SIZE]
u, v = xx / (SIZE - 1), yy / (SIZE - 1)

# 1. Island: a soft dome from the center so that there is sea along the map edges
cx, cy = 0.5, 0.5
r = np.sqrt(((u - cx) * 1.15) ** 2 + ((v - cy) * 1.0) ** 2)
island = np.clip(1.0 - (r / 0.46) ** 2, 0.0, 1.0)

# 2. Hills: several octaves of smooth noise on a grid (without external libraries)
rng = np.random.default_rng(20260916)
noise = np.zeros((SIZE, SIZE), dtype=np.float32)
amp = 1.0
for cells in (4, 8, 16, 32):
    grid = rng.random((cells + 1, cells + 1)).astype(np.float32)
    gy = np.clip((v * cells), 0, cells - 1e-3)
    gx = np.clip((u * cells), 0, cells - 1e-3)
    y0, x0 = gy.astype(int), gx.astype(int)
    ty, tx = gy - y0, gx - x0
    sy, sx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)   # smoothed interpolation
    top = grid[y0, x0] * (1 - sx) + grid[y0, x0 + 1] * sx
    bot = grid[y0 + 1, x0] * (1 - sx) + grid[y0 + 1, x0 + 1] * sx
    noise += (top * (1 - sy) + bot * sy) * amp
    amp *= 0.5
noise = (noise - noise.min()) / (noise.max() - noise.min())

# 3. Assemble the height: sea along the edges, a plain in the center, mountains along the north and east
height = SEA_LEVEL - 0.20 + island * (PLAIN - SEA_LEVEL + 0.22)
# mountain masks are made smooth, otherwise a cliff step appears at the seam
north = np.clip((0.30 - v) / 0.16, 0.0, 1.0)
east = np.clip((u - 0.74) / 0.16, 0.0, 1.0)
ridge = np.clip(north + east, 0.0, 1.0)
ridge = ridge * ridge * (3 - 2 * ridge) * island
height += ridge * (MOUNTAIN - PLAIN) * (0.5 + 0.5 * noise)
height += (noise - 0.5) * 0.06 * island     # slight unevenness of the plain

# 4. Flat areas for settlements: the town on a plateau so it does not stand on a slope
for name, sx_, sy_, rad in SETTLEMENTS:
    d = np.sqrt((u - sx_) ** 2 + (v - sy_) ** 2)
    w = np.clip(1.0 - d / rad, 0.0, 1.0) ** 0.5
    target = PLAIN + 0.02
    height = height * (1 - w) + target * w
    log(f"площадка {name}: центр {sx_:.2f},{sy_:.2f} радиус {rad:.3f}")

height = np.clip(height, 0.0, 1.0)
log(f"размер {SIZE}, суша {(height > SEA_LEVEL).mean() * 100:.1f}% площади, "
    f"высоты {height.min():.2f}..{height.max():.2f}")

os.makedirs(OUT, exist_ok=True)
img = bpy.data.images.new("eq_map_heightmap", SIZE, SIZE, alpha=False, float_buffer=True)
rgba = np.empty((SIZE, SIZE, 4), dtype=np.float32)
rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = height[::-1]   # in the image the origin is at the bottom
rgba[..., 3] = 1.0
img.pixels.foreach_set(rgba.ravel())
img.filepath_raw = os.path.join(OUT, "eq_map_heightmap.png")
img.file_format = "PNG"
scene = bpy.context.scene
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "16"
scene.render.image_settings.color_mode = "BW"
img.save_render(img.filepath_raw, scene=scene)
log("written", img.filepath_raw)

# preview with the coastline and settlement points marked - to check the shape by eye
preview = np.zeros((SIZE, SIZE, 4), dtype=np.float32)
land = height > SEA_LEVEL
preview[..., 0] = np.where(land, 0.35 + height * 0.6, 0.05)
preview[..., 1] = np.where(land, 0.45 + height * 0.5, 0.15)
preview[..., 2] = np.where(land, 0.30 + height * 0.4, 0.45)
for name, sx_, sy_, rad in SETTLEMENTS:
    d = np.sqrt((u - sx_) ** 2 + (v - sy_) ** 2)
    mark = (d < rad * 0.35)
    preview[mark] = (1.0, 0.2, 0.2, 1.0)
preview[..., 3] = 1.0
pv = bpy.data.images.new("eq_map_preview", SIZE, SIZE, alpha=False)
pv.pixels.foreach_set(preview[::-1].ravel())
pv.filepath_raw = os.path.join(OUT, "eq_map_preview.png")
pv.file_format = "PNG"
pv.save()
log("written", pv.filepath_raw)
