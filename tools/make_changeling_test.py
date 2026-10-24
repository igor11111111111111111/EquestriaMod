"""Тестовый чейнджлинг: детали скачанной модели на нашей антро-пони.

Запуск (headless Blender, открывает готовую пони):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python make_changeling_test.py --
      ../assets/reference/changeling/dark_fluttershy/scene.gltf ../assets/changeling_test

Скачанная модель — четвероногая пони одним мешем без скелета (судя по атласу, выдрана из игры Gameloft),
поэтому ТОЛЬКО для проверки вида, не для публикации. Тело у неё не подходит (у нас антро на человеческом
скелете), берём отдельные куски:
  eq_changeling_mane — грива, рог, гребни и уши (слот шлема вместо eq_pony_mane), жёстко на кости головы;
  eq_changeling_tail — хвост и крылья (слот плаща вместо eq_pony_tail): хвост на тазе, крылья на спине.
Хитиновый цвет тела даёт окрас кожи расы (движок красит серую шерсть), отдельное тело не нужно.
"""
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

GLTF, OUT = sys.argv[sys.argv.index("--") + 1:][:2]
OUT = os.path.abspath(OUT)
os.makedirs(os.path.join(OUT, "textures"), exist_ok=True)
os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)
MAT = "eq_changeling_parts"


def log(*a):
    print("[changeling]", *a, flush=True)


skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pony = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
bones = {b.name: skel.matrix_world @ b.head_local for b in skel.data.bones}

bpy.ops.import_scene.gltf(filepath=GLTF)
src = next(o for o in bpy.context.selected_objects if o.type == "MESH")
image = next(n.image for m in src.data.materials for n in m.node_tree.nodes if n.type == "TEX_IMAGE")

# ---------------------------------------------------------------- 1. куски модели (связные части)
bm = bmesh.new()
bm.from_mesh(src.data)
bm.transform(src.matrix_world)
uv_layer = bm.loops.layers.uv.active
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
bm.faces.ensure_lookup_table()
face_part = {}
parts = []
for f in bm.faces:
    if f.index in face_part:
        continue
    stack, comp = [f], []
    face_part[f.index] = len(parts)
    while stack:
        x = stack.pop()
        comp.append(x)
        for v in x.verts:
            for y in v.link_faces:
                if y.index not in face_part:
                    face_part[y.index] = len(parts)
                    stack.append(y)
    pts = np.array([v.co[:] for g in comp for v in g.verts])
    parts.append({"faces": comp, "lo": pts.min(0), "hi": pts.max(0), "n": len(comp)})

body = max(parts, key=lambda p: p["n"])
tail = max(parts, key=lambda p: p["hi"][1])            # дальше всех назад (+Y)
mane = min(parts, key=lambda p: p["lo"][1])            # грива свисает дальше всех вперёд (-Y)
wings = [p for p in parts if p not in (body, tail, mane)
         and p["hi"][0] - p["lo"][0] < 0.5 and abs(p["lo"][0]) > 3]
horn = max((p for p in parts if p not in (body, tail, mane) and p not in wings),
           key=lambda p: p["hi"][2] - p["lo"][2] + (p["hi"][0] - p["lo"][0]))
crests = [p for p in parts if p not in (body, tail, mane, horn) and p not in wings
          and p["hi"][2] - p["lo"][2] > 10]
log(f"parts {len(parts)}: wings {len(wings)}, crests {len(crests)}")

# опорные точки головы по средней линии: кончик морды (мин. Y) и макушка (макс. Z)
mid = np.array([v.co[:] for f in body["faces"] for v in f.verts if abs(v.co.x) < 2.0 and v.co.z > 45])
cl_snout = mid[mid[:, 1].argmin()]
cl_crown = mid[mid[:, 2].argmax()]
# уши торчат по бокам выше макушки
ears = [f for f in body["faces"] if all(v.co.z > cl_crown[2] - 3 and abs(v.co.x) > 2.5 for v in f.verts)]
log(f"changeling snout {np.round(cl_snout, 1)}, crown {np.round(cl_crown, 1)}, ear faces {len(ears)}")

head = pony["eq_twilight_head"]
hv = np.array([(head.matrix_world @ v.co)[:] for v in head.data.vertices])
hm = hv[np.abs(hv[:, 0]) < 0.04]
hm = hm[hm[:, 2] > bones["bip01_head_13"].z]
pn_snout = hm[hm[:, 1].argmin()]
pn_crown = hm[hm[:, 2].argmax()]
log(f"pony snout {np.round(pn_snout, 3)}, crown {np.round(pn_crown, 3)}")

HEAD_SCALE = float(np.linalg.norm((pn_crown - pn_snout)[1:]) / np.linalg.norm((cl_crown - cl_snout)[1:]))
log(f"head scale {HEAD_SCALE:.5f}")


def placed(scale, src_pt, dst_pt):
    return Matrix.Translation(Vector(dst_pt)) @ Matrix.Scale(scale, 4) @ Matrix.Translation(-Vector(src_pt))


# голова: макушки совмещаем, центр по средней точке морда-макушка
T_HEAD = placed(HEAD_SCALE, (cl_snout + cl_crown) / 2, (pn_snout + pn_crown) / 2 + np.array([0, 0.01, 0.01]))

# хвост: корень (передний верх) — к корню хвоста пони
BODY_SCALE = HEAD_SCALE * 1.1
tail_root = np.array([0.0, tail["lo"][1], tail["hi"][2]])
bv = np.array([(pony["eq_twilight_body"].matrix_world @ v.co)[:] for v in pony["eq_twilight_body"].data.vertices])


def back_surface(z):
    near = bv[(np.abs(bv[:, 2] - z) < 0.03) & (np.abs(bv[:, 0]) < 0.05)]
    return near[:, 1].max()


# у пони хвост в меше вместе с меткой на бедре, поэтому корень ищем по спине у кости таза
pelvis = bones["bip01_pelvis_0"]
pn_tail_root = np.array([0.0, back_surface(pelvis.z) - 0.03, pelvis.z - 0.02])
T_TAIL = placed(BODY_SCALE, tail_root, pn_tail_root)

# крылья: основание (передний низ) — на спину между лопатками
wing_root = np.array([0.0, min(p["lo"][1] for p in wings), min(p["lo"][2] for p in wings)])
sp2 = bones["bip01_spine2_11"]
WING_ROOT = np.array([0.0, back_surface(sp2.z) - 0.02, sp2.z - 0.08])
WING_SCALE = BODY_SCALE * 1.4
WING_SPREAD = 0.05  # м, крылья чуть разводим от позвоночника


def wing_matrix(part):
    side = 1.0 if part["lo"][0] > 0 else -1.0
    return Matrix.Translation((side * WING_SPREAD, 0, 0)) @ placed(WING_SCALE, wing_root, WING_ROOT)


log(f"tail root {np.round(pn_tail_root, 3)}, wing root {np.round(WING_ROOT, 3)}")

mat = bpy.data.materials.new(MAT)
mat.use_nodes = True
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = image
image.name = f"{MAT}_d"
image.filepath_raw = os.path.join(OUT, "textures", f"{MAT}_d.png")
image.file_format = "PNG"
image.save()
mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])


def build(name, groups):
    """groups: [(faces, matrix, bone)] -> skinned object"""
    out = bmesh.new()
    uv = out.loops.layers.uv.new("UVMap")
    dvert = out.verts.layers.deform.verify()
    bone_index = {}
    for faces, matrix, bone in groups:
        gi = bone_index.setdefault(bone, len(bone_index))
        vmap = {}
        for f in faces:
            vs = []
            for v in f.verts:
                if v not in vmap:
                    nv = out.verts.new(matrix @ v.co)
                    nv[dvert][gi] = 1.0
                    vmap[v] = nv
                vs.append(vmap[v])
            try:
                nf = out.faces.new(vs)
            except ValueError:  # такая грань уже есть (двусторонние плоскости)
                continue
            for l_new, l_old in zip(nf.loops, f.loops):
                l_new[uv].uv = l_old[uv_layer].uv
    me = bpy.data.meshes.new(name)
    out.to_mesh(me)
    out.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for bone in bone_index:
        ob.vertex_groups.new(name=bone)
    ob.parent = skel
    ob.matrix_parent_inverse = skel.matrix_world.inverted()
    ob.modifiers.new("Armature", "ARMATURE").object = skel
    log(f"item {name}: {len(me.vertices)} verts, {len(me.polygons)} faces, bones {list(bone_index)}")
    return ob


HEAD_BONE, SPINE_BONE, PELVIS_BONE = "bip01_head_13", "bip01_spine2_11", "bip01_pelvis_0"
items = [
    build("eq_changeling_mane", [(mane["faces"], T_HEAD, HEAD_BONE), (horn["faces"], T_HEAD, HEAD_BONE),
                                 (ears, T_HEAD, HEAD_BONE)]
          + [(c["faces"], T_HEAD, HEAD_BONE) for c in crests]),
    build("eq_changeling_tail", [(tail["faces"], T_TAIL, PELVIS_BONE)]
          + [(w["faces"], wing_matrix(w), SPINE_BONE) for w in wings]),
]
bm.free()
bpy.data.objects.remove(src)

bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *items]:
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
fbx = os.path.join(OUT, "eq_changeling_test.fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
log("exported", fbx)

# ---------------------------------------------------------------- превью: тёмная шерсть + детали
for name in ("eq_twilight_mane", "eq_twilight_tail"):
    pony[name].hide_render = True
atlas = next(n.image for n in bpy.data.materials["eq_twilight_body"].node_tree.nodes if n.type == "TEX_IMAGE")
px = np.empty(len(atlas.pixels), dtype=np.float32)
atlas.pixels.foreach_get(px)
px = px.reshape(-1, 4)
# только для картинки, файл не сохраняется: темнеет серая шерсть (и белки — у чейнджлингов их нет),
# цветные радужки остаются
sat = px[:, :3].max(1) - px[:, :3].min(1)
coat = sat < 0.08
px[coat, :3] *= np.array([0.16, 0.17, 0.2], dtype=np.float32)
atlas.pixels.foreach_set(px.ravel())

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x, scene.render.resolution_y = 700, 1000
cam = bpy.data.objects.new("preview_cam", bpy.data.cameras.new("preview_cam"))
cam.data.type = "ORTHO"
scene.collection.objects.link(cam)
scene.camera = cam
for name, direction, center, size in [
        ("full_front", (0, -1, 0), (0, 0.1, 0.95), 2.3), ("full_side", (1, 0, 0), (0, 0.1, 0.95), 2.3),
        ("full_back", (0, 1, 0.3), (0, 0.1, 0.95), 2.3), ("full_three", (1, -1, 0.4), (0, 0.1, 0.95), 2.3),
        ("head_front", (0, -1, 0), (0, 0, 1.62), 0.7), ("head_side", (1, 0, 0), (0, 0, 1.62), 0.7)]:
    d = Vector(direction).normalized()
    cam.data.ortho_scale = size
    cam.location = Vector(center) + d * 6
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, "preview", f"{name}.png")
    bpy.ops.render.render(write_still=True)
log("done")
