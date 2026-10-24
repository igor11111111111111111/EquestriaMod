# Эталонное тело Bannerlord (Skinned Body Base Meshes, Nexus 2286) в системе координат нашей модели.
# Совмещение — по суставам: кости эталона (pelvis, l_thigh, ...) -> кости human_skeleton (bip01_pelvis_0, ...),
# подбирается подобие (поворот + масштаб + сдвиг, при необходимости с отражением) методом Умеямы.
import re

import bpy
import numpy as np
from mathutils import Matrix, Vector


def _strip(name):
    return re.sub(r"_\d+$", "", name).replace("bip01_", "")


def fit_matrix(ref_armature, target_armature, turn_around=True):
    """4x4-матрица, переводящая мир ref_armature в мир target_armature (подобие по суставам [+ поворот 180°])."""
    target = {_strip(b.name): target_armature.matrix_world @ b.head_local for b in target_armature.data.bones}
    pairs = [(ref_armature.matrix_world @ b.head_local, target[_strip(b.name)])
             for b in ref_armature.data.bones if _strip(b.name) in target and "nub" not in b.name]
    src = np.array([p[0] for p in pairs])
    dst = np.array([p[1] for p in pairs])
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    u, d, vt = np.linalg.svd(xd.T @ xs / len(src))
    sign = np.eye(3)
    if np.linalg.det(u @ vt) < 0:
        sign[2, 2] = -1
    rot = u @ sign @ vt
    scale = (d * np.diag(sign)).sum() / xs.var(0).sum()
    shift = mu_d - scale * rot @ mu_s
    m = np.eye(4)
    m[:3, :3] = scale * rot
    m[:3, 3] = shift
    error = float(np.abs((m[:3, :3] @ src.T).T + shift - dst).max())
    if turn_around:
        m = np.diag([-1.0, -1.0, 1.0, 1.0]) @ m
    return Matrix(m.tolist()), {"pairs": len(pairs), "scale": float(scale), "max_joint_error": error}


def bone_name_map(target_armature):
    """'l_thigh' / 'bip01_l_thigh_1' -> 'bip01_l_thigh_1'."""
    return {_strip(b.name): b.name for b in target_armature.data.bones}


def import_reference(fbx_path, target_armature, turn_around=True):
    """Импортирует эталон и возвращает {имя меша: вершины в мире target_armature}, сведения о совмещении.

    turn_around: по суставам эталон смотрит в +Y, а наши модели построены лицом к -Y (так они правильно
    стоят в игре: движок поворачивает меш на 180° относительно FBX-скелета). Поворот на 180° вокруг Z
    ставит эталон так же, как наша модель.
    """
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.fbx(filepath=fbx_path, automatic_bone_orientation=False,
                             primary_bone_axis="X", secondary_bone_axis="-Y")
    new = [o for o in bpy.context.scene.objects if o not in before]
    bpy.context.view_layer.update()
    ref_arm = next(o for o in new if o.type == "ARMATURE")

    target = {_strip(b.name): target_armature.matrix_world @ b.head_local for b in target_armature.data.bones}
    pairs = [(ref_arm.matrix_world @ b.head_local, target[_strip(b.name)])
             for b in ref_arm.data.bones if _strip(b.name) in target and "nub" not in b.name]
    src = np.array([p[0] for p in pairs])
    dst = np.array([p[1] for p in pairs])

    # Умеяма: dst ≈ s * R @ src + t
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    u, d, vt = np.linalg.svd(xd.T @ xs / len(src))
    sign = np.eye(3)
    reflected = np.linalg.det(u @ vt) < 0
    if reflected:
        sign[2, 2] = -1
    rot = u @ sign @ vt
    scale = (d * np.diag(sign)).sum() / xs.var(0).sum()
    shift = mu_d - scale * rot @ mu_s
    error = np.abs((scale * (rot @ src.T)).T + shift - dst).max()

    dg = bpy.context.evaluated_depsgraph_get()
    meshes = {}
    for ob in new:
        if ob.type != "MESH":
            continue
        me = ob.evaluated_get(dg).to_mesh()
        pts = np.array([tuple(ob.matrix_world @ v.co) for v in me.vertices])
        fitted = (scale * (rot @ pts.T)).T + shift
        if turn_around:
            fitted[:, :2] *= -1
        meshes[ob.name] = {
            "verts": fitted,
            "faces": [tuple(p.vertices) for p in me.polygons],
        }
        ob.evaluated_get(dg).to_mesh_clear()
    for ob in new:
        bpy.data.objects.remove(ob, do_unlink=True)
    info = {"pairs": len(pairs), "scale": float(scale), "reflected": bool(reflected), "max_joint_error": float(error)}
    return meshes, info


def build_object(name, verts, faces, color=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if color is not None:
        ob.color = color
    return ob
