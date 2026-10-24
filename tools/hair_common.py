"""Общее для причёсок (запускается внутри Blender на eq_twilight.blend): голова, уши, глаза, линии прядей,
веса костей, вырез у ушей, локоны, экспорт и превью. Используют tools/make_changeling_hair.py,
tools/make_pony_manes.py.

Как устроены волосы в Bannerlord (проверено 2026-09-17):
  - причёска — обычный скиненный меш (кости head / neck / spine2, как у ванильных), перечисленный
    в skins.xml расы (<hair_mesh name=...>); слайдера длины нет — длина = отдельные варианты,
    зеркальный вариант даёт галочка «Отразить» в редакторе;
  - цвет волос движок умножает на текстуру ванильного материала female_hair_mat (двусторонний, шейдер
    волос) — в FBX только имя материала, редактор найдёт его;
  - волосы следуют за слайдерами лица (deforms_hair), поэтому строятся прямо по голове нашей расы.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HAIR_MAT = "female_hair_mat"
HORN_MAT = "eq_twilight_body"  # рог красится своей текстурой, а не палитрой волос
HORN_CELL = (1, 2)  # клетка атласа с текстурой рога (меш eq_twilight_mane)
HEAD, NECK, SPINE2 = "bip01_head_13", "bip01_neck_12", "bip01_spine2_11"
HERE = os.path.dirname(os.path.abspath(__file__))
SKIN_CELL = (3, 1)
# По какой голове строить причёску. Расе со своей моделью можно подсунуть её голову через
# EQ_HEAD_MESH — так делалось для оленьих рогов, пока они были отдельной причёской.
HEAD_MESH = os.environ.get("EQ_HEAD_MESH", "eq_twilight_head")
BODY_MESH = os.environ.get("EQ_BODY_MESH", "eq_twilight_body")


def log(*a):
    print("[hair]", *a, flush=True)


skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pony = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
bones = {b.name: skel.matrix_world @ b.head_local for b in skel.data.bones}
# в сохранённой пони все ключи мимики стоят на 1 — работаем с базовой формой
for _ob in pony.values():
    if _ob.data.shape_keys:
        for _kb in _ob.data.shape_keys.key_blocks[1:]:
            _kb.value = 0.0


def cell(u, v):
    return (min(int(u * 4), 3), min(int(v * 4), 3))


def world_mesh(ob, keep=None):
    """Вершины и грани меша в мировых координатах; keep(center, uv_cell) -> bool отбирает грани."""
    me = ob.data
    uv = me.uv_layers.active.data
    verts = [ob.matrix_world @ v.co for v in me.vertices]
    polys = []
    for p in me.polygons:
        c = sum((verts[i] for i in p.vertices), Vector()) / p.loop_total
        if keep is None or keep(c, cell(*uv[p.loop_indices[0]].uv)):
            polys.append(list(p.vertices))
    return verts, polys


def ear_polygons(ob, centre):
    """Грани ушей: плоские лепестки, стоящие боком к центру головы, плюс всё, что далеко от центра."""
    me = ob.data
    uv = me.uv_layers.active.data
    mw = ob.matrix_world
    info = {}
    for p in me.polygons:
        c = mw @ p.center
        nrm = (mw.to_3x3() @ p.normal).normalized()
        info[p.index] = (cell(*uv[p.loop_indices[0]].uv) == SKIN_CELL, c, abs(nrm.dot((c - centre).normalized())))
    ear = {i for i, (sk, c, d) in info.items()
           if sk and abs(c.x) > 0.05 and c.z > 1.70 and d < 0.6 and (c - centre).length > 0.11}
    by_vert = {}
    for p in me.polygons:
        for vi in p.vertices:
            by_vert.setdefault(vi, []).append(p.index)
    for _ in range(3):
        ear |= {j for i in ear for vi in me.polygons[i].vertices for j in by_vert[vi]
                if j not in ear and info[j][0] and info[j][1].z > 1.72 and abs(info[j][1].x) > 0.05 and info[j][2] < 0.7}
    ear |= {i for i, (sk, c, d) in info.items()
            if sk and c.z > 1.72 and abs(c.x) > 0.05 and (c - centre).length > 0.18}
    return ear


head_ob = pony[HEAD_MESH]
_sv, _sp = world_mesh(head_ob, lambda c, cl: cl == SKIN_CELL)
_skin = np.array([_sv[i][:] for p in _sp for i in p])
C = Vector((0.0, float(_skin[:, 1].mean()) + 0.02, bones[HEAD].z + 0.09))
EAR_FACES = ear_polygons(head_ob, C)


def head_part(ears_only):
    me = head_ob.data
    verts = [head_ob.matrix_world @ v.co for v in me.vertices]
    uv = me.uv_layers.active.data
    polys = [list(p.vertices) for p in me.polygons
             if cell(*uv[p.loop_indices[0]].uv) == SKIN_CELL and ((p.index in EAR_FACES) == ears_only)]
    return verts, polys


# голова без ушей и без глаз — по ней идут корни и пряди
hv, hp = head_part(False)
scalp = BVHTree.FromPolygons(hv, hp)
# руки в T-позе торчат в стороны — в игре они опущены, пряди об них не мнём
bv, bp = world_mesh(pony[BODY_MESH], lambda c, cl: not (abs(c.x) > 0.19 and c.z > 1.1))
solid = BVHTree.FromPolygons(hv + bv, hp + [[i + len(hv) for i in p] for p in bp])
ev, ep = head_part(True)
ears = BVHTree.FromPolygons(ev, ep)
EAR_NEAR, EAR_GAP, EAR_SNAP = 0.025, 0.003, 0.02


# ---------------------------------------------------------------- глаза: зона, куда волосам нельзя
class EyeZone:
    def __init__(self, side):
        me = head_ob.data
        mw = head_ob.matrix_world
        eye = me.attributes["eq_eye"]
        pts = np.array([(mw @ me.vertices[i].co)[:] for i in range(len(me.vertices)) if eye.data[i].value == 1])
        pts = pts[pts[:, 0] * side > 0]
        self.d = Vector((0.15 * side, -1.0, 0.0)).normalized()
        self.e1 = Vector((side, 0.0, 0.0)) - self.d * self.d.x * side
        self.e1.normalize()
        self.e2 = self.e1.cross(self.d).normalized()
        if self.e2.z < 0:
            self.e2 = -self.e2
        centre = pts.mean(0)
        front = pts[(pts - centre) @ np.array(self.d[:]) > 0]
        visible = np.array([scalp.ray_cast(Vector(p) + self.d * 0.0005, self.d, 0.5)[0] is None for p in front])
        vis = front[visible]
        self.c = Vector(vis.mean(0))
        q = vis - np.array(self.c[:])
        x, y = q @ np.array(self.e1[:]), q @ np.array(self.e2[:])
        self.rx = float(np.percentile(np.abs(x), 97))
        self.ry = float(np.percentile(np.abs(y), 97))
        log(f"eye zone {side:+d}: centre {tuple(round(v, 3) for v in self.c)}, "
            f"{self.rx * 200:.1f} x {self.ry * 200:.1f} cm")

    def push(self, p, margin):
        q = p - self.c
        depth = q.dot(self.d)
        if depth < -0.05:
            return p
        x, y = q.dot(self.e1), q.dot(self.e2)
        rx, ry = self.rx + margin, self.ry + margin
        k = (x / rx) ** 2 + (y / ry) ** 2
        if k >= 1.0:
            return p
        if k < 1e-6:
            x, y = rx, 0.0
        else:
            s = 1.0 / math.sqrt(k)
            x, y = x * s, y * s
        return self.c + self.e1 * x + self.e2 * y + self.d * max(depth, 0.0)


EYES = [EyeZone(1), EyeZone(-1)]
EYE_MARGIN = 0.012


def avoid_eyes(p, margin=EYE_MARGIN):
    for z in EYES:
        p = z.push(p, margin)
    return p


log(f"head centre {tuple(round(x, 3) for x in C)}")


def direction(theta, phi):
    """theta — азимут от затылка (0 = +Y, назад), 180 = морда; phi — возвышение."""
    t, p = math.radians(theta), math.radians(phi)
    return Vector((math.sin(t) * math.cos(p), math.cos(t) * math.cos(p), math.sin(p)))


_last_r = [0.12]


def scalp_point(d, offset):
    """Внешняя точка головы по направлению d от центра + зазор."""
    d = d.normalized()
    hit = scalp.ray_cast(C + d * 0.6, -d)
    if hit[0] is not None:
        _last_r[0] = (hit[0] - C).length
    return C + d * (_last_r[0] + offset)


def axis_of(p):
    return C if p.z > bones[NECK].z + 0.04 else Vector((0.0, 0.01, p.z))


def push_out(p, margin):
    """Вытолкнуть точку из тела/головы (наружу от оси тела или центра головы) и из зоны глаз."""
    loc, normal, _, _ = solid.find_nearest(p)
    if loc is not None:
        if normal.dot(loc - axis_of(loc)) < 0:
            normal = -normal
        if (p - loc).dot(normal) < margin:
            p = loc + normal * margin
    return avoid_eyes(p)


def slerp(a, b, t):
    a, b = a.normalized(), b.normalized()
    om = math.acos(max(-1.0, min(1.0, a.dot(b))))
    if om < 1e-5:
        return a.copy()
    return (a * math.sin((1 - t) * om) + b * math.sin(t * om)) / math.sin(om)


def hair_line(root_dir, exit_dir, hang, offset, down, spread, n_scalp, n_hang, root_sink=0.006):
    """Линия пряди: по голове от корня к точке схода, затем вниз; число точек у всех линий слоя одинаковое."""
    pts = []
    for i in range(n_scalp + 1):
        t = i / n_scalp
        # у корня прядь уходит под кожу — край прячется в голове
        off = offset - root_sink * max(0.0, 1.0 - t / 0.2)
        pts.append(avoid_eyes(scalp_point(slerp(root_dir, exit_dir, t), off)))
    tan = (pts[-1] - pts[-2]).normalized()
    p = pts[-1].copy()
    x0 = p.x
    step = hang / max(n_hang, 1)
    for j in range(n_hang):
        f = min(1.0, j * step / 0.08)
        tan = (tan * (1 - 0.35 * f) + down * (0.35 * f + 0.05)).normalized()
        p = p + tan * step
        p.x += x0 * spread / n_hang
        p = push_out(p, offset + 0.004)
        pts.append(p.copy())
    return pts


def hairline_dir(a, lift=0.0):
    """Корень на линии роста волос: a=0 — лоб за рогом, |a|=1 — виски."""
    sgn = 1.0 if a >= 0 else -1.0
    return direction(sgn * (180 - 85 * abs(a)), 60 - 40 * abs(a) + lift)


def horn_source():
    """Грани рога единорога из меша гривы: мировые координаты, UV. Рог входит в каждую причёску пони
    вторым материалом — в слоте шлема он больше не нужен, и его видно вместе с причёской."""
    ob = pony["eq_twilight_mane"]
    me = ob.data
    uv = me.uv_layers.active.data
    verts = [ob.matrix_world @ v.co for v in me.vertices]
    faces = []
    for p in me.polygons:
        if cell(*uv[p.loop_indices[0]].uv) == HORN_CELL:
            faces.append(([verts[i] for i in p.vertices], [tuple(uv[li].uv) for li in p.loop_indices]))
    return faces


def bone_weights(p):
    """Как у ванильных причёсок: голова, ниже — шея, ещё ниже — spine2; не больше двух костей."""
    z = p.z
    zh, zn, zs = bones[HEAD].z, bones[NECK].z, bones[SPINE2].z
    if z >= zh - 0.06:
        return {HEAD: 1.0}
    if z >= zn:
        t = (z - zn) / (zh - 0.06 - zn)
        return {HEAD: t, NECK: 1 - t}
    if z >= zs:
        t = (z - zs) / (zn - zs)
        return {NECK: t, SPINE2: 1 - t}
    return {SPINE2: 1.0}


GROUPS = [HEAD, NECK, SPINE2]


class MeshBuilder:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.dv = self.bm.verts.layers.deform.verify()
        self.parts = 0
        self.horn = False

    def vertex(self, pos):
        v = self.bm.verts.new(pos)
        for bone, wgt in bone_weights(pos).items():
            v[self.dv][GROUPS.index(bone)] = wgt
        return v

    def face(self, verts, uvs, material=0):
        try:
            f = self.bm.faces.new(verts)
        except ValueError:
            return None
        f.material_index = material
        for loop, uv in zip(f.loops, uvs):
            loop[self.uv].uv = uv
        return f

    def add_horn(self):
        """Рог второй частью меша (свой материал) — как у ванильных причёсок с двумя материалами."""
        for verts, uvs in horn_source():
            self.face([self.vertex(p) for p in verts], uvs, material=1)
        self.horn = True
        self.parts += 1

    def cut_ears(self):
        bm = self.bm
        for reach in (EAR_NEAR, EAR_NEAR / 2.5, EAR_NEAR / 6):
            close = {e for f in bm.faces if any(ears.find_nearest(v.co, reach)[0] is not None for v in f.verts)
                     for e in f.edges}
            if close:
                bmesh.ops.subdivide_edges(bm, edges=list(close), cuts=1, use_grid_fill=True)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        tris = bm.calc_loop_triangles()
        hair_bvh = BVHTree.FromPolygons([v.co for v in bm.verts], [[l.vert.index for l in t] for t in tris])
        hit = {tris[i][0].face for i, _ in hair_bvh.overlap(ears)}
        hit |= {f for f in bm.faces if ears.find_nearest(f.calc_center_median(), EAR_GAP)[0] is not None}
        edge_verts = {v for f in hit for v in f.verts if any(g not in hit for g in v.link_faces)}
        bmesh.ops.delete(bm, geom=list(hit), context="FACES")
        # край выреза притягивается к уху — без щели у основания уха
        for v in edge_verts:
            if not v.is_valid:
                continue
            loc = ears.find_nearest(v.co, EAR_SNAP)[0]
            if loc is not None:
                away = v.co - loc
                v.co = loc + (away.normalized() if away.length > 1e-6 else Vector((0, 0, 1))) * 0.002
        return len(hit)

    def to_object(self, radial_normals=True, cut_ears=True):
        cut = self.cut_ears() if cut_ears else 0
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        me.materials.append(bpy.data.materials.get(HAIR_MAT) or bpy.data.materials.new(HAIR_MAT))
        if self.horn:
            me.materials.append(bpy.data.materials[HORN_MAT])
        for poly in me.polygons:
            poly.use_smooth = True
        if self.horn:
            # у рога свои нормали (он не часть оболочки волос) — пересчитываем по геометрии
            radial_normals = False
        if radial_normals:
            me.normals_split_custom_set_from_vertices([(v.co - axis_of(v.co)).normalized()[:] for v in me.vertices])
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        for g in GROUPS:
            ob.vertex_groups.new(name=g)
        ob.parent = skel
        ob.matrix_parent_inverse = skel.matrix_world.inverted()
        ob.modifiers.new("Armature", "ARMATURE").object = skel
        log(f"{self.name}: {self.parts} частей, {len(me.vertices)} вершин, {len(me.polygons)} граней, "
            f"у ушей вырезано {cut}")
        return ob


# ---------------------------------------------------------------- локоны: трубки вдоль линии пряди
# Материал волос — ванильный female_hair_mat, но весь локон лежит на крошечном однотонном непрозрачном
# участке его текстуры: пряди текстуры не видны, локон выходит гладким, как нарисованный.
TEX = 2048.0
LIGHT, DARK = (192.0, 156.0), (744.0, 300.0)  # светлый и тёмный участки (пиксели, сверху вниз)
SPAN = 8.0
SEGS = 10


def patch_uv(tone, a01, s01):
    cx, cy = tone
    return ((cx + (a01 - 0.5) * SPAN) / TEX, 1.0 - (cy + (s01 - 0.5) * SPAN) / TEX)


def D(theta, phi):
    return direction(theta, phi)


def V(x, y, z):
    return Vector((x, y, z)).normalized()


def avoid_ears(p, r):
    loc = ears.find_nearest(p, r)[0]
    if loc is None:
        return p
    away = p - loc
    if away.length < 1e-6:
        away = p - C
    return loc + away.normalized() * r


def lock_path(root_dir, exit_dir, hang, down, thick, width, curl=0.0, curl_r=0.035, wave=0.0,
              waves=2.0, n_scalp=10):
    """Осевая линия локона. curl > 0 — завиток внутрь (под себя), < 0 — кончик отгибается наружу."""
    offset = thick * 0.5 + 0.004
    n_hang = int(round(hang / 0.015)) if hang > 0 else 0
    pts = hair_line(root_dir, exit_dir, hang, offset, down, 0.0, n_scalp, n_hang, root_sink=thick * 0.5)
    if wave and n_hang:
        start = n_scalp + 1
        for j, i in enumerate(range(start, len(pts))):
            p = pts[i]
            t = (pts[min(i + 1, len(pts) - 1)] - pts[i - 1]).normalized()
            side = t.cross(p - axis_of(p)).normalized()
            pts[i] = p + side * math.sin((j + 1) / n_hang * waves * math.pi) * wave
    if curl:
        t = (pts[-1] - pts[-2]).normalized()
        p = pts[-1].copy()
        out = p - axis_of(p)
        target = -out if curl > 0 else out
        axis = t.cross(target)
        if axis.length < 1e-6:
            axis = t.cross(Vector((0, 0, 1)))
        axis.normalize()
        total = abs(curl) * 2 * math.pi
        steps = max(4, int(total / 0.35))
        r = curl_r
        for k in range(steps):
            t = Matrix.Rotation(total / steps, 3, axis) @ t
            p = p + t * (r * total / steps)
            r *= 0.93
            pts.append(push_out(p, offset * 0.6))
    return [avoid_ears(p, width * 0.5 + 0.006) for p in pts]


class Mane(MeshBuilder):
    """Причёска из локонов: сплошная шапочка + трубки-пряди."""

    def cap(self, hang=0.03, tone=LIGHT, lift=0.0):
        """Сплошная «шапочка» волос под локонами: между ними не просвечивает голова. Вырез у ушей делается
        только в ней (локоны уши обходят) — поэтому шапочку строят первой."""
        lines = [hair_line(hairline_dir(a, lift), direction(95 * a, -18), hang, 0.004, V(0, 0.3, -1), 0.0, 14, 2)
                 for a in np.linspace(-1, 1, 27)]
        rows = min(len(l) for l in lines)
        grid = [[self.vertex(l[j]) for j in range(rows)] for l in lines]
        for i in range(len(lines) - 1):
            for j in range(rows - 1):
                self.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]),
                          [patch_uv(tone, i % 2, j / rows), patch_uv(tone, (i + 1) % 2, j / rows),
                           patch_uv(tone, (i + 1) % 2, (j + 1) / rows), patch_uv(tone, i % 2, (j + 1) / rows)])
        self.cut_ears()
        self.bm.normal_update()
        for f in self.bm.faces:
            c = f.calc_center_median()
            if f.normal.dot(c - axis_of(c)) < 0:
                f.normal_flip()
        self.parts += 1

    def lock(self, path, width, thick, tone=LIGHT, tip="point", root_scale=0.7, flat_min=0.35):
        n = len(path)
        if n < 2:
            return
        lengths = [0.0]
        for a, b in zip(path, path[1:]):
            lengths.append(lengths[-1] + (b - a).length)
        total = max(lengths[-1], 1e-6)
        first = len(self.bm.verts)
        rings = []
        for i, p in enumerate(path):
            t = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)])
            t = t.normalized() if t.length > 1e-9 else Vector((0, 0, -1))
            out = p - axis_of(p)
            out = out - t * out.dot(t)
            out = out.normalized() if out.length > 1e-9 else Vector((0, 1, 0))
            side = t.cross(out).normalized()
            s = lengths[i] / total
            prof = root_scale + (1 - root_scale) * min(1.0, s / 0.15)
            if tip == "point":
                prof *= min(1.0, (1 - s) / 0.4) ** 0.85
            elif tip == "round" and s > 0.85:
                prof *= math.sqrt(max(0.0, 1 - ((s - 0.85) / 0.15) ** 2))
            w = width * prof
            th = max(thick * prof, w * flat_min) if w > 1e-5 else 0.0
            if w < 1e-5:
                rings.append([(self.vertex(p), s)])
                continue
            ring = []
            for k in range(SEGS):
                a = 2 * math.pi * k / SEGS
                ring.append((self.vertex(p + side * (math.cos(a) * w / 2) + out * (math.sin(a) * th / 2)), s))
            rings.append(ring)
        for i in range(n - 1):
            ra, rb = rings[i], rings[i + 1]
            if len(ra) == 1 and len(rb) == 1:
                continue  # две точки-кончика подряд (отрезок нулевой длины)
            for k in range(SEGS):
                k2 = (k + 1) % SEGS
                a0, a1 = k / SEGS, (k + 1) / SEGS
                if len(rb) == 1:
                    self.face((ra[k][0], ra[k2][0], rb[0][0]),
                              [patch_uv(tone, a0, ra[k][1]), patch_uv(tone, a1, ra[k][1]),
                               patch_uv(tone, 0.5, rb[0][1])])
                elif len(ra) == 1:
                    self.face((ra[0][0], rb[k2][0], rb[k][0]),
                              [patch_uv(tone, 0.5, ra[0][1]), patch_uv(tone, a1, rb[k][1]),
                               patch_uv(tone, a0, rb[k][1])])
                else:
                    self.face((ra[k][0], ra[k2][0], rb[k2][0], rb[k][0]),
                              [patch_uv(tone, a0, ra[k][1]), patch_uv(tone, a1, ra[k][1]),
                               patch_uv(tone, a1, rb[k][1]), patch_uv(tone, a0, rb[k][1])])
        for ring, at_end in ((rings[0], False), (rings[-1], True)):
            if len(ring) == 1 or (at_end and tip != "blunt"):
                continue
            centre = self.vertex(sum((v.co for v, _ in ring), Vector()) / len(ring))
            s = ring[0][1]
            for k in range(SEGS):
                k2 = (k + 1) % SEGS
                self.face((centre, ring[k2][0], ring[k][0]) if not at_end else (centre, ring[k][0], ring[k2][0]),
                          [patch_uv(tone, 0.5, s)] * 3)
        self.bm.verts.ensure_lookup_table()
        faces = {f for v in self.bm.verts[first:] for f in v.link_faces}
        bmesh.ops.recalc_face_normals(self.bm, faces=list(faces))
        self.parts += 1


def export(objects, path):
    """Скелет + причёски; материал — только имя (без картинки)."""
    bpy.ops.object.select_all(action="DESELECT")
    for ob in [skel, *objects]:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = skel
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, add_leaf_bones=False, bake_anim=False,
                             primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
    log("exported", path)


def preview(objects, out_dir, tint, hide_coat=False):
    """EEVEE-превью с ванильной текстурой волос, окрашенной в tint; по три вида на причёску."""
    os.makedirs(out_dir, exist_ok=True)
    tex_path = os.path.join(HERE, "..", "assets", "reference", "vanilla_hair", "textures", "female_hair.dds")
    mat = bpy.data.materials[HAIR_MAT]
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    tex = nodes.new("ShaderNodeTexImage")
    try:
        tex.image = bpy.data.images.load(tex_path)
    except RuntimeError:
        log("dds не читается Blender'ом — превью без текстуры")
    bsdf = nodes.get("Principled BSDF")
    if bsdf and tex.image:
        mix = nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        mix.inputs[2].default_value = (*tint, 1.0)
        mat.node_tree.links.new(tex.outputs["Color"], mix.inputs[1])
        mat.node_tree.links.new(mix.outputs[0], bsdf.inputs["Base Color"])
        mat.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
    scene = bpy.context.scene
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.resolution_x, scene.render.resolution_y = 600, 800
    mat.use_backface_culling = False
    for m in bpy.data.materials:
        if m is not mat:
            m.use_backface_culling = True
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(200))
    scene.collection.objects.link(sun)
    world = bpy.data.worlds.new("preview")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.33, 0.4, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    scene.world = world
    hide = {"eq_twilight_mane", "eq_twilight_tail"}
    if HEAD_MESH != "eq_twilight_head":  # в файле лежит и пони, и новая раса — показываем только её
        hide |= {n for n in pony if n.startswith("eq_twilight_")}
    for name in hide:
        if name in pony:
            pony[name].hide_render = True
    cam = bpy.data.objects.new("preview_cam", bpy.data.cameras.new("preview_cam"))
    cam.data.type = "ORTHO"
    scene.collection.objects.link(cam)
    scene.camera = cam
    only = os.environ.get("EQ_HAIR_PREVIEW")
    for ob in objects:
        if only and only not in ob.name:
            continue
        for other in objects:
            other.hide_render = other is not ob
        for view, d in (("front", (0.25, -1, 0.1)), ("side", (1, 0.15, 0.1)), ("back", (-0.3, 1, 0.25))):
            d = Vector(d).normalized()
            cam.data.ortho_scale = float(os.environ.get("EQ_HAIR_PREVIEW_SCALE", 1.0))  # рога выше головы
            cam.location = Vector((0, 0.02, 1.45)) + d * 6
            cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
            scene.render.filepath = os.path.join(out_dir, f"{ob.name}_{view}.png")
            bpy.ops.render.render(write_still=True)
    log("preview done")
