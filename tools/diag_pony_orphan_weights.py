# -*- coding: utf-8 -*-
"""Read-only: finds vertices whose DOMINANT bone matches NONE of their neighbours along mesh
edges: a narrow, reliable sign of an accidentally misbound island (a couple of vertices on new
polygons that, when a hole was sealed, got the weight of an unrelated spot that is adjacent in 3D but not
connected through the mesh).

Run:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\diag_pony_orphan_weights.py
"""
import bpy

col = bpy.data.collections.get("Пони - цельная")
NAMES = ("eq_pony_head", "eq_pony_hair", "eq_pony_horn", "eq_pony_body")


def check(name):
    ob = col.objects.get(name) if col else bpy.data.objects.get(name)
    if ob is None:
        print(f"[diag] {name}: НЕ НАЙДЕН")
        return
    mesh = ob.data
    groups = {vg.index: vg.name for vg in ob.vertex_groups}

    dominant = {}
    for v in mesh.vertices:
        if v.groups:
            dom = max(v.groups, key=lambda g: g.weight)
            dominant[v.index] = groups.get(dom.group)
        else:
            dominant[v.index] = None

    neighbours = {v.index: set() for v in mesh.vertices}
    for e in mesh.edges:
        a, b = e.vertices[0], e.vertices[1]
        neighbours[a].add(b)
        neighbours[b].add(a)

    flagged = []
    for idx, nbrs in neighbours.items():
        if not nbrs or dominant[idx] is None:
            continue
        nbr_bones = {dominant[n] for n in nbrs if dominant[n] is not None}
        if nbr_bones and dominant[idx] not in nbr_bones:
            flagged.append((idx, dominant[idx], sorted(nbr_bones), tuple(mesh.vertices[idx].co)))

    print(f"[diag] {name}: вершин {len(mesh.vertices)}, с чужой костью среди соседей {len(flagged)}")
    for idx, bone, nbr_bones, co in flagged[:30]:
        print(f"[diag]   вершина {idx}: своя кость={bone} соседи=({', '.join(nbr_bones)}) позиция={co}")


for n in NAMES:
    check(n)
