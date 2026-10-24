# Рисует кьютимарку в развёртке нашей модели: накладки (tattoo_materials) движок кладёт по UV тела,
# а ванильные татуировки нарисованы под человеческую развёртку и ложатся криво.
#
# blender --background <eq_twilight.blend> --python make_cutiemark.py -- <out_dir>
#
# Результат: <out_dir>\textures\eq_cutiemark_star.png — прозрачная текстура с меткой на боку.
# Дальше в редакторе: импортировать текстуру и создать материал eq_cutiemark_star (шейдер pbr_shading,
# текстура в слот DiffuseMap), затем вписать его имя в TATTOO_MATERIALS (tools\make_pony_race.py).
import os
import sys

import bpy
import numpy as np

OUT = sys.argv[sys.argv.index("--") + 1]
TEX_DIR = os.path.join(OUT, "textures")
os.makedirs(TEX_DIR, exist_ok=True)
SIZE = 4096  # как атлас модели: бок занимает малую часть развёртки, иначе метка мыльная
NAME = "eq_cutiemark_star"


def log(*a):
    print("[cutiemark]", *a, flush=True)


body = bpy.data.objects["eq_twilight_body"]
uv = body.data.uv_layers.active.data
pts = np.array([tuple(body.matrix_world @ v.co) for v in body.data.vertices])

# бок и бедро: сторона +X, высота чуть ниже таза, середина по глубине
z_lo, z_hi = np.percentile(pts[:, 2], [12, 32])
flank = []
for poly in body.data.polygons:
    for li in poly.loop_indices:
        i = body.data.loops[li].vertex_index
        p = pts[i]
        if p[0] > 0.08 and z_lo < p[2] < z_hi and abs(p[1]) < 0.16:
            flank.append(tuple(uv[li].uv))
flank = np.array(flank)
if len(flank) < 10:
    raise SystemExit("не нашёл бок пони — поправьте границы области")
lo, hi = np.percentile(flank, 5, axis=0), np.percentile(flank, 95, axis=0)
center, half = (lo + hi) / 2, (hi - lo) / 2
log(f"flank uv {np.round(lo, 3)}..{np.round(hi, 3)} ({len(flank)} loops)")

# Фон белый, а не прозрачный: ванильные накладки идут в режиме modulate (умножение), и чёрный фон
# закрасил бы всё тело. Белый = «не меняем», альфа остаётся на случай, если движок смешивает по ней.
img = np.zeros((SIZE, SIZE, 4), dtype=np.float32)
img[..., :3] = 1.0
yy, xx = np.mgrid[0:SIZE, 0:SIZE]
u, v = xx / SIZE, yy / SIZE

# шестиконечная звезда Twilight: две наложенные звезды по углу вокруг центра метки
radius = float(min(half) * 0.5)


def star(cu, cv, r, points, color, sharp=2.8):
    du, dv = (u - cu), (v - cv)
    dist = np.sqrt(du * du + dv * dv) + 1e-9
    ang = np.arctan2(dv, du)
    lobes = np.abs(np.cos(points / 2 * ang)) ** sharp
    mask = dist < r * (0.30 + 0.70 * lobes)
    for c in range(3):
        img[..., c][mask] = color[c]
    img[..., 3][mask] = 1.0


star(center[0], center[1], radius, 6, (0.85, 0.25, 0.75))
for du, dv, k in ((-0.85, 0.75, 0.22), (0.85, 0.7, 0.18), (-0.75, -0.85, 0.18)):
    star(center[0] + du * radius, center[1] + dv * radius, radius * k, 6, (1.0, 1.0, 1.0))

out_img = bpy.data.images.new(NAME, SIZE, SIZE, alpha=True)
out_img.pixels.foreach_set(img.ravel())
out_img.filepath_raw = os.path.join(TEX_DIR, f"{NAME}.png")
out_img.file_format = "PNG"
out_img.save()
log(f"written {out_img.filepath_raw} (метка радиусом {radius:.3f} UV в центре {np.round(center, 3)})")

# превью: кладём метку поверх атласа и рендерим бок пони — видно, куда попала кьютимарка
atlas = bpy.data.images.get("eq_twilight_body_d")
if atlas is not None:
    px = np.empty(len(atlas.pixels), dtype=np.float32)
    atlas.pixels.foreach_get(px)
    px = px.reshape(atlas.size[1], atlas.size[0], 4)
    mark = np.array(img)
    if mark.shape[0] != px.shape[0]:
        step = mark.shape[0] // px.shape[0]
        mark = mark[::step, ::step]
    a = mark[..., 3:4]
    px[..., :3] = px[..., :3] * (1 - a) + mark[..., :3] * a
    atlas.pixels.foreach_set(px.ravel())
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x, scene.render.resolution_y = 600, 800
    cam = bpy.data.objects.new("mark_cam", bpy.data.cameras.new("mark_cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 1.4
    scene.collection.objects.link(cam)
    scene.camera = cam
    for o in scene.objects:
        if o.type == "MESH":
            o.hide_render = o.name != "eq_twilight_body"
    from mathutils import Vector
    d = Vector((1, 0, 0))
    cam.location = Vector((0, 0, 0.95)) + d * 5
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, "preview", "cutiemark.png")
    bpy.ops.render.render(write_still=True)
    log("preview", scene.render.filepath)
