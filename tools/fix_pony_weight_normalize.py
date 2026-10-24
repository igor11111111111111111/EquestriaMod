# -*- coding: utf-8 -*-
"""Нормализует веса костей по вершинам eq_pony_head и eq_pony_body — сумма весов вершины
приводится к 1.0, пропорции между костями сохраняются (не перекраска руками, чисто
математическая правка). Чинит "разлёт" вершин у шеи/плеч в бою: у части вершин было по 1.0 сразу
у двух костей (сумма 2.0) — движок в позе, где кости расходятся, тянул вершину в обе стороны
сразу (см. diag_pony_neck_weights.py, 30.09.2026). Сохраняет файл.

Запуск:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\fix_pony_weight_normalize.py
"""
import bpy

col = bpy.data.collections.get("Пони - цельная")
NAMES = ("eq_pony_head", "eq_pony_body")


def normalize(name):
    ob = col.objects.get(name) if col else bpy.data.objects.get(name)
    if ob is None:
        print(f"[fix] {name}: НЕ НАЙДЕН")
        return

    for o in bpy.data.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

    if bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    fixed = 0
    for v in ob.data.vertices:
        total = sum(g.weight for g in v.groups)
        if len(v.groups) > 0 and (total < 0.98 or total > 1.02):
            for g in v.groups:
                g.weight = g.weight / total
            fixed += 1

    print(f"[fix] {name}: нормализовано вершин {fixed}")


for n in NAMES:
    normalize(n)

bpy.ops.wm.save_mainfile()
print("[fix] файл сохранён")
