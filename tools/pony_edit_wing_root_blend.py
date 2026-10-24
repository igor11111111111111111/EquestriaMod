# -*- coding: utf-8 -*-
"""Bind the wing to the clavicle (= the pony's front leg bone) so it flaps in time with running/fighting.

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_wing_root_blend.py

Before (until 07.10.2026) this script gave the clavicle only a little weight right at the root — just to
close the gap at the shoulder when the arm turns, the rest of the wing stayed rigidly on bip01_spine2_11
(per an earlier request not to hook onto the leg bones). Now it is the opposite: the clavicle already
swings in EVERY ready run/fight animation (it is the front leg bone), and with 100% weight on one bone a
vertex simply rotates rigidly with it — so giving it almost the whole wing yields a flap "for free",
without a single new animation. The wing tip gets the largest amplitude by itself, simply from the lever arm.
A short transition zone right at the base (ROOT_NEAR..ROOT_FAR) is kept so there is no gap/fold at the
joint with the body — beyond it the wing is almost entirely on the clavicle (ROOT_MAX).
"""
import bpy

ROOT_NEAR = 0.05     # closer than this to the clavicle (the joint with the body) — clavicle weight ~0, keep spine2 like the body
ROOT_FAR = 0.30       # beyond this — pure ROOT_MAX all the way to the wing tip (max. amplitude there)
ROOT_MAX = 0.92       # clavicle weight share past the transition zone (not 1.0 — keep a bit of spine2 for stability)

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
