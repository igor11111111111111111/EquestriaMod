# Сборка расы из чужой модели: детали зверя на готовое антро-тело пони.
#
#   blender --background --factory-startup --python make_creature_parts.py -- <вид> <модель.glb>
#           <pony.blend> <папка вывода> [--preview]
#
# Что делает: вырезает из четвероногой модели те части, которым разворот не нужен (голова с
# клювом или рогами, крылья, хвост, когти), ставит каждую на своё место рядом с костью
# человеческого скелета Bannerlord и жёстко привязывает к ней. Туловище, руки и ноги берутся
# готовые — от нашей антро-пони, они уже привязаны и правильно анимируются.
#
# Почему так, а не «развернуть всю модель»: у четвероногого нет геометрии в тех местах, где у
# стоящего должны быть бок, подмышка и пах, — автоматический разворот рвёт там кожу (проверено
# четырьмя способами, см. docs/reference/creatures). Детали же переносятся жёстко и целиком,
# поэтому выглядят ровно так, как их слепил генератор.
#
# Размеры и повороты деталей — в tools/creature_data.py, ключ "graft".
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creature_data import BONES, CREATURES  # noqa: E402

_args = [a for a in sys.argv[sys.argv.index("--") + 1:]]
PREVIEW = "--preview" in _args
_args = [a for a in _args if not a.startswith("--")]
KEY, GLB, PONY, OUT = _args[:4]
OUT = os.path.abspath(OUT)      # пути должны быть полными: Блендер сохраняет картинки
GLB = os.path.abspath(GLB)      # относительно открытого .blend, а не текущей папки
CARD = CREATURES[KEY]
PREFIX = "eq_" + CARD["name"]
os.makedirs(OUT, exist_ok=True)
TEX_DIR = os.path.join(OUT, "textures")
os.makedirs(TEX_DIR, exist_ok=True)


def log(*a):
    print("[parts]", *a, flush=True)


# ---------------------------------------------------------------- 1. база: пони со скелетом
bpy.ops.wm.open_mainfile(filepath=PONY)
scene = bpy.context.scene
vl = bpy.context.view_layer
skel = next(o for o in scene.objects if o.type == "ARMATURE")
pony_meshes = {o.name: o for o in scene.objects if o.type == "MESH"}
log("основа: скелет %s, мешей пони %d" % (skel.name, len(pony_meshes)))


def select_only(objs, active):
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = active


def bone_head(key):
    return skel.matrix_world @ skel.data.bones[BONES[key]].head_local


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def match(q, rule):
    for cond, value in rule.items():
        if cond == "min_z" and q.z < value:
            return False
        if cond == "max_z" and q.z > value:
            return False
        if cond == "min_y" and q.y < value:
            return False
        if cond == "max_y" and q.y > value:
            return False
        if cond == "min_x" and q.x < value:
            return False
        if cond == "max_x" and q.x > value:
            return False
        if cond == "min_abs_x" and abs(q.x) < value:
            return False
    return True


# ---------------------------------------------------------------- 2. модель зверя
images_before = set(bpy.data.images.keys())
before = set(scene.objects)
bpy.ops.import_scene.gltf(filepath=GLB)
new = [o for o in scene.objects if o not in before]
meshes = [o for o in new if o.type == "MESH"]
for o in new:
    if o.type != "MESH":
        bpy.data.objects.remove(o, do_unlink=True)
select_only(meshes, meshes[0])
if len(meshes) > 1:
    bpy.ops.object.join()
beast = vl.objects.active
beast.name = PREFIX + "_beast"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# разворот мордой в -Y, как смотрит персонаж Bannerlord
turn = Matrix.Rotation(math.radians(CARD["yaw"]), 4, "Z")
beast.matrix_world = turn @ beast.matrix_world
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# сшивка «супа»: соседние треугольники у модели генератора не делят вершины
select_only([beast], beast)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0008)
bpy.ops.object.mode_set(mode="OBJECT")
log("модель зверя: %d вершин, %d треугольников" % (len(beast.data.vertices), tri_count(beast)))


def separate(ob, indices, name):
    if not indices:
        return None
    select_only([ob], ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    chosen = set(indices)
    for i in indices:
        ob.data.vertices[i].select = True
    # грань уезжает вместе с вершинами только если выбрана целиком — отмечаем такие грани сами,
    # иначе в новом объекте остаётся облако точек без единой грани
    for f in ob.data.polygons:
        f.select = all(i in chosen for i in f.vertices)
    was = set(scene.objects)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    fresh = [o for o in scene.objects if o not in was]
    if not fresh:
        return None
    fresh[0].name = name
    return fresh[0]


def drop_small_islands(ob, min_verts=24):
    """Выбрасывает мелкие обрывки: при резке по координатам всегда цепляются чужие кусочки,
    и они висят в воздухе рядом с деталью."""
    me = ob.data
    parent = list(range(len(me.vertices)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    groups = {}
    for v in me.vertices:
        groups.setdefault(find(v.index), []).append(v.index)
    small = [i for cells in groups.values() if len(cells) < min_verts for i in cells]
    if not small:
        return 0
    select_only([ob], ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for i in small:
        me.vertices[i].select = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="VERT")
    bpy.ops.object.mode_set(mode="OBJECT")
    return len(small)


def bounds(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


# ---------------------------------------------------------------- 3. детали
parts = {}
for name, spec in CARD.get("graft", {}).items():
    idx = [v.index for v in beast.data.vertices if match(beast.matrix_world @ v.co, spec["rule"])]
    part = separate(beast, idx, "%s_%s" % (PREFIX, name))
    if part is None:
        log("деталь %s: не нашлось вершин по правилу" % name)
        continue
    select_only([part], part)
    dropped = drop_small_islands(part)
    # дырка от разреза (плоский срез шеи) заращивается: иначе сзади видно, что голова полая
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.fill_holes(sides=0)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    # упрощение до разумного числа треугольников
    limit = spec.get("tris", 3000)
    if tri_count(part) > limit:
        dec = part.modifiers.new("dec", "DECIMATE")
        dec.ratio = limit / tri_count(part)
        bpy.ops.object.modifier_apply(modifier=dec.name)

    # масштаб: деталь должна стать заданной высоты (или ширины)
    lo, hi = bounds(part)
    size = hi - lo
    axis = {"z": 2, "y": 1, "x": 0}[spec.get("by", "z")]
    k = spec["size"] / max(size[axis], 1e-6)
    part.matrix_world = Matrix.Scale(k, 4) @ part.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # поворот вокруг своей середины
    pitch, roll, yaw = (math.radians(a) for a in spec.get("rotate", (0, 0, 0)))
    lo, hi = bounds(part)
    mid = (lo + hi) / 2
    rot = Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(pitch, 4, "X") @ Matrix.Rotation(roll, 4, "Y")
    part.matrix_world = Matrix.Translation(mid) @ rot @ Matrix.Translation(-mid) @ part.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # положение: заданная точка детали совмещается с точкой у кости
    lo, hi = bounds(part)
    anchor = {"bottom": Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)),
              "top": Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z)),
              "middle": (lo + hi) / 2,
              "front": Vector(((lo.x + hi.x) / 2, lo.y, (lo.z + hi.z) / 2)),
              "back": Vector(((lo.x + hi.x) / 2, hi.y, (lo.z + hi.z) / 2))}[spec.get("anchor", "middle")]
    target = bone_head(spec["bone"]) + Vector(spec.get("offset", (0, 0, 0)))
    part.matrix_world = Matrix.Translation(target - anchor) @ part.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # жёсткая привязка к кости
    for vg in list(part.vertex_groups):
        part.vertex_groups.remove(vg)
    vg = part.vertex_groups.new(name=BONES[spec["bone"]])
    vg.add([v.index for v in part.data.vertices], 1.0, "REPLACE")
    part.parent = skel
    part.matrix_parent_inverse = skel.matrix_world.inverted()
    mod = part.modifiers.new("Armature", "ARMATURE")
    mod.object = skel
    parts[name] = part
    lo, hi = bounds(part)
    log("деталь %-6s: %d вершин (обрывков убрано %d), размер %.2f x %.2f x %.2f, на кости %s"
        % (name, len(part.data.vertices), dropped, *(hi - lo), BONES[spec["bone"]]))

bpy.data.objects.remove(beast, do_unlink=True)

# ---------------------------------------------------------------- 4. текстуры и экспорт
for img in bpy.data.images:
    if img.size[0] == 0 or img.name in images_before:
        continue
    kind = "n" if "normal" in img.name.lower() else (
        "s" if "metallic" in img.name.lower() or "_rm" in img.name.lower() else "d")
    path = os.path.join(TEX_DIR, "%s_%s.png" % (PREFIX, kind))
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    log("текстура %s -> %s" % (img.name, os.path.basename(path)))

# в экспорт идут только наши детали и скелет: тело, ноги и кисти берутся от пони как есть
select_only(list(parts.values()) + [skel], skel)
fbx = os.path.join(OUT, PREFIX + ".fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y",
                         bake_space_transform=False, mesh_smooth_type="FACE",
                         path_mode="COPY", embed_textures=False)
log("записан", fbx)
if PREVIEW:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, PREFIX + "_parts.blend"))
    log("записан", os.path.join(OUT, PREFIX + "_parts.blend"))
