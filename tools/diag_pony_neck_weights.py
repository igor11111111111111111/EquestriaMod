# -*- coding: utf-8 -*-
"""Только чтение: ищет вершины с "битым" весом костей (сумма далеко от 1.0, или привязка не к
соседним костям шеи/головы/позвоночника) у частей пони, где может быть шов на шее —
eq_pony_head и eq_pony_body. Помогает найти новые полигоны, которым забыли назначить веса при
зашивании дыры на шее.

Запуск:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\diag_pony_neck_weights.py
"""
import bpy

col = bpy.data.collections.get("Пони - цельная")

NAMES = ("eq_pony_head", "eq_pony_body")


def check(name):
    ob = col.objects.get(name) if col else bpy.data.objects.get(name)
    if ob is None:
        print(f"[diag] {name}: НЕ НАЙДЕН")
        return
    mesh = ob.data
    groups = {vg.index: vg.name for vg in ob.vertex_groups}
    bad = []
    for v in mesh.vertices:
        total = sum(g.weight for g in v.groups)
        if total < 0.98 or total > 1.02 or len(v.groups) == 0:
            names = ", ".join(f"{groups.get(g.group,'?')}={g.weight:.2f}" for g in v.groups)
            bad.append((v.index, total, names, tuple(v.co)))
    print(f"[diag] {name}: вершин {len(mesh.vertices)}, с плохой суммой веса {len(bad)}")
    for idx, total, names, co in bad[:40]:
        print(f"[diag]   вершина {idx}: сумма={total:.3f} группы=[{names}] позиция={co}")


for n in NAMES:
    check(n)
