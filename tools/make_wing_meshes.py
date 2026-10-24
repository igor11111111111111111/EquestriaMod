# -*- coding: utf-8 -*-
"""Жёсткие меши крыльев для машущих крыльев (10.10.2026): eq_<раса>_wing_l / eq_<раса>_wing_r.

Меш крыльев расы делится по знаку X, каждая половина переносится так, что НАЧАЛО КООРДИНАТ —
корень крыла (центр вершин у позвоночника). Взмах делает код (EquestriaWingsTest): поворот
сущности вокруг корня по синусу. Скелет птицы и скиннинг не используются — их привязку в игре
измерить нельзя, перебор не сошёлся.

Запуск: blender --background <blend расы> --python tools/make_wing_meshes.py -- <раса>
    пони:   assets/pony/eq_pony_edit.blend   -- pony
    дракон: assets/dragon/eq_dragon.blend    -- dragon
    грифон: assets/griffon/eq_griffon.blend  -- griffon
    гиппогриф: assets/hippogriff/hippogriff.blend -- hippogriff
    чейнджлинг: assets/changeling/eq_changeling.blend -- changeling
Выход: assets/wings/eq_<раса>_wing_lr.fbx (+ печать корней в координатах модели для кода:
RootLeft/RootRight в EquestriaWingsTest.Races).
"""
import os

import bpy
from mathutils import Matrix, Vector

import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RACE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "pony"
# раса → (коллекция или None, объект крыльев в blend)
SOURCES = {
    "pony": ("Пони - цельная", "eq_pony_wings"),
    "dragon": (None, "eq_wings"),
    "griffon": (None, "eq_griffon_wings"),
    "hippogriff": (None, "eq_hippogriff_wings"),
    "changeling": (None, "eq_changeling_wings"),
}
# Материал меша в FBX должен называться как материал расы в модуле (pony_skins.xml: eq_<раса>_body),
# иначе редактор при каждом запуске показывает "Unable to find material" (замечено 10.10.2026 у дракона:
# в blend материал звался Material.001).
MATERIALS = {"pony": "eq_pony_body", "dragon": "eq_dragon_body", "griffon": "eq_griffon_body", "hippogriff": "eq_hippogriff_body", "changeling": "eq_changeling_body"}
OUT_FBX = os.path.join(ROOT, "assets", "wings", "eq_%s_wing_lr.fbx" % RACE)
ROOT_BAND = 0.03  # м: вершины ближе этого к плоскости симметрии считаем корнем

collection, obj_name = SOURCES[RACE]
wings = (bpy.data.collections[collection].objects if collection else bpy.data.objects)[obj_name]
W = wings.matrix_world
exported = []
for name, sign in (("eq_%s_wing_l" % RACE, 1), ("eq_%s_wing_r" % RACE, -1)):
    mesh = wings.data.copy()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    mesh.transform(W)
    for vg in list(ob.vertex_groups):
        ob.vertex_groups.remove(vg)
    ob.modifiers.clear()
    mat_name = MATERIALS[RACE]
    mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(mat_name)
    mesh.materials.clear()
    mesh.materials.append(mat)
    # оставить половину
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for v in mesh.vertices:
        v.select = (v.co.x * sign) < 0
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="VERT")
    bpy.ops.object.mode_set(mode="OBJECT")
    xs = [abs(v.co.x) for v in mesh.vertices]
    near = [v.co for v in mesh.vertices if abs(v.co.x) < min(xs) + ROOT_BAND]
    root = sum(near, Vector()) / len(near)
    mesh.transform(Matrix.Translation(-root))
    ob.matrix_world = Matrix.Identity(4)
    tip = max(abs(v.co.x) for v in mesh.vertices)
    print(f"[wing] {name}: корень в координатах модели {tuple(round(c, 4) for c in root)}, вершин {len(mesh.vertices)}, размах от корня {tip:.3f}")
    exported.append(ob)

os.makedirs(os.path.dirname(OUT_FBX), exist_ok=True)
bpy.ops.object.select_all(action="DESELECT")
for ob in exported:
    ob.select_set(True)
bpy.context.view_layer.objects.active = exported[0]
bpy.ops.export_scene.fbx(filepath=OUT_FBX, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         path_mode="STRIP", axis_forward="Y", axis_up="Z")
print(f"[wing] записан {OUT_FBX}")
