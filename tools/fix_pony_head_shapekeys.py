# -*- coding: utf-8 -*-
"""Обнуляет Value у всех шейп-ключей eq_pony_head кроме Basis — были все разом на 1.000,
Object Mode считал Basis + сумму всех ~100 лицевых морфов и голову разносило (см.
diag_pony_head_shapekeys.py). Сохраняет файл.

Запуск:
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
