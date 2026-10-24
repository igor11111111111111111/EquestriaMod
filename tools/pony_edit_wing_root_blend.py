# -*- coding: utf-8 -*-
"""Привязать крыло к ключице (= кость передней ноги пони), чтобы оно взмахивало в такт бегу/бою.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_wing_root_blend.py

Раньше (до 07.10.2026) этот скрипт давал ключице лишь чуть веса у самого корня — только чтобы
закрыть щель у плеча при развороте руки, остальное крыло оставалось жёстко на bip01_spine2_11
(по прошлой просьбе не цепляться за кости ног). Теперь — наоборот: ключица уже качается в КАЖДОЙ
готовой анимации бега/боя (это кость передней лапы), и при 100% веса на одну кость вершина просто
жёстко вращается вместе с ней — так что отдать ей почти всё крыло даёт взмах "бесплатно", без
единой новой анимации. Кончик крыла получает самую большую амплитуду сам, просто от плеча рычага.
Короткий переходный участок у самого основания (ROOT_NEAR..ROOT_FAR) оставлен, чтобы не было щели/
складки на стыке с телом — дальше него крыло почти целиком на ключице (ROOT_MAX).
"""
import bpy

ROOT_NEAR = 0.05     # ближе этого к ключице (сам стык с телом) — вес ключицы ~0, держим spine2 как у тела
ROOT_FAR = 0.30       # дальше этого — уже чистый ROOT_MAX до самого кончика крыла (там макс. амплитуда)
ROOT_MAX = 0.92       # доля веса ключицы за переходным участком (не 1.0 — чуть держим spine2 для устойчивости)

ob = bpy.data.collections["Пони - цельная"].objects["eq_pony_wings"]
skel = bpy.data.objects["bip01_notused"]


def clavicle_pos(side):
    b = skel.data.bones["bip01_%s_clavicle_14" % side if side == "l" else "bip01_r_clavicle_21"]
    return skel.matrix_world @ ((b.head_local + b.tail_local) / 2)


CLAV = {"l": clavicle_pos("l"), "r": clavicle_pos("r")}
anchor = ob.vertex_groups["bip01_spine2_11"]
touched = 0
for v in ob.data.vertices:
    side = "l" if v.co.x > 0 else "r"
    pos = ob.matrix_world @ v.co
    d = (pos - CLAV[side]).length
    if d <= ROOT_NEAR:
        t = 0.0
    elif d >= ROOT_FAR:
        t = 1.0
    else:
        t = (d - ROOT_NEAR) / (ROOT_FAR - ROOT_NEAR)
    t = t * t * (3 - 2 * t)
    frac = ROOT_MAX * t
    bone_name = "bip01_l_clavicle_14" if side == "l" else "bip01_r_clavicle_21"
    grp = ob.vertex_groups.get(bone_name) or ob.vertex_groups.new(name=bone_name)
    grp.add([v.index], frac, "REPLACE")
    anchor.add([v.index], 1.0 - frac, "REPLACE")
    touched += 1

print("[wingroot] вершин с весом ключицы (взмах):", touched, "из", len(ob.data.vertices))
bpy.context.view_layer.objects.active = ob
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
bpy.ops.wm.save_mainfile()
print("[wingroot] сохранено")
