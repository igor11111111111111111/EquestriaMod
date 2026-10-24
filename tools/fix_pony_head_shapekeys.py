# -*- coding: utf-8 -*-
"""Zeroes Value on all eq_pony_head shape keys except Basis: they were all at 1.000 at once,
Object Mode computed Basis + the sum of all ~100 facial morphs and the head blew apart (see
diag_pony_head_shapekeys.py). Saves the file.

Run:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\fix_pony_head_shapekeys.py
"""
import bpy

col = bpy.data.collections.get("Пони - цельная")
ob = col.objects.get("eq_pony_head") if col else bpy.data.objects.get("eq_pony_head")
if ob is None:
    raise SystemExit("eq_pony_head не найден")

keys = ob.data.shape_keys
if keys is None:
    raise SystemExit("шейп-ключей нет")

changed = 0
for kb in keys.key_blocks:
    if kb.name == "Basis":
        continue
    if kb.value != 0.0:
        kb.value = 0.0
        changed += 1

print(f"[fix] обнулено ключей: {changed}")

bpy.ops.wm.save_mainfile()
print("[fix] файл сохранён")
