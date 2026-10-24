"""Убирает с модели пони мелкие звёзды кьютимарки.

Кьютимарка (tools/convert_twilight.py, build_cutiemarks) — геометрия в меше хвоста: большая звезда
на бедре и три маленьких вокруг. Вся она жёстко привязана к тазу, поэтому маленькие звёзды, которые
ложатся уже на ногу, при шаге отрываются от кожи и «летают». Большая сидит на бедре у самого таза
и держится, её оставляем.

Маленькие звёзды отличаются развёрткой: их грани лежат в столбце атласа u≈0.44 (белый цвет),
большая звезда — в u≈0.31. Исходные координаты из convert_twilight.py (0.75 и 0.25) в атлас не
годятся: при упаковке текстур UV сдвигаются, и по ним режется сам хвост (он занимает u≈0.77…0.98).

Запуск (файл перезаписывается, рядом кладётся копия .before_cutiemark):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python trim_cutiemark.py
"""
import os
import shutil

import bmesh
import bpy

TAIL = "eq_twilight_tail"
SMALL_U = 0.44   # столбец атласа, которым покрыты маленькие звёзды
TOL = 0.03
EXPECT = 72      # 6 звёзд (по три с каждого бока) по 12 треугольников


def log(*a):
    print("[cutiemark]", *a, flush=True)


blend = bpy.data.filepath
ob = bpy.data.objects[TAIL]
me = ob.data

before = len(me.polygons)
bm = bmesh.new()
bm.from_mesh(me)
uv = bm.loops.layers.uv.active
doomed = [f for f in bm.faces
          if all(abs(loop[uv].uv.x - SMALL_U) < TOL for loop in f.loops)]
bmesh.ops.delete(bm, geom=doomed, context="FACES")
bm.to_mesh(me)
bm.free()
me.update()
cut = before - len(me.polygons)
log(f"убрано граней: {cut} из {before}, осталось {len(me.polygons)}")

if cut != EXPECT:
    # лучше ничего не трогать, чем срезать кусок хвоста: проверьте столбец атласа
    log(f"ожидалось {EXPECT} граней — модель не трогаем")
else:
    for name, ext in (("eq_twilight.fbx", ".before_cutiemark.fbx"),):
        path = os.path.join(os.path.dirname(blend), name)
        if os.path.exists(path):
            shutil.copyfile(path, path.replace(".fbx", ext))

    # экспорт как в convert_twilight.py
    skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    items = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("eq_twilight_")]
    bpy.ops.object.select_all(action="DESELECT")
    for o in [skel, *items]:
        o.select_set(True)
    bpy.context.view_layer.objects.active = skel
    fbx = os.path.join(os.path.dirname(blend), "eq_twilight.fbx")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False, bake_anim=False,
                             primary_bone_axis="X", secondary_bone_axis="-Y")
    log("экспортирован", fbx, [o.name for o in items])
    shutil.copyfile(blend, blend.replace(".blend", ".before_cutiemark.blend"))
    bpy.ops.wm.save_mainfile()
    log("сохранён", blend)
