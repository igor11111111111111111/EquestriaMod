# -*- coding: utf-8 -*-
"""Только чтение: сравнивает каждый шейп-ключ eq_pony_head с Basis и печатает максимальное и
среднее отклонение вершин — чтобы найти битый ключ без сохранения файла.

Запуск:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\diag_pony_head_shapekeys.py
"""
import bpy

col = bpy.data.collections.get("Пони - цельная")
ob = col.objects.get("eq_pony_head") if col else bpy.data.objects.get("eq_pony_head")
if ob is None:
    raise SystemExit("eq_pony_head не найден")

keys = ob.data.shape_keys
if keys is None:
    raise SystemExit("шейп-ключей нет")

basis = keys.key_blocks.get("Basis")
if basis is None:
    raise SystemExit("Basis не найден")

print("[diag] объект:", ob.name, "вершин:", len(basis.data))
for kb in keys.key_blocks:
    if kb.name == "Basis":
        continue
    max_d = 0.0
    sum_d = 0.0
    max_idx = -1
    for i in range(len(basis.data)):
        d = (kb.data[i].co - basis.data[i].co).length
        sum_d += d
        if d > max_d:
            max_d = d
            max_idx = i
    avg_d = sum_d / len(basis.data)
    print(f"[diag] {kb.name}: value={kb.value:.3f} mute={kb.mute} "
          f"max_offset={max_d:.4f} (vertex {max_idx}) avg_offset={avg_d:.5f}")
