# -*- coding: utf-8 -*-
"""Печатает сырые свойства узлов-костей FBX: PreRotation, Lcl Rotation, Lcl Translation,
RotationOrder — тем парсером, которым Blender сам читает FBX (io_scene_fbx.parse_fbx), без
какой-либо конвертации осей. Нужно, чтобы увидеть, что реально лежит в файле TaleWorlds и в
нашем экспорте (гипотеза 10.10.2026: движок накладывает PreRotation скелета-владельца поверх
наших кривых, где pre-rotation уже вшит Blender'ом, и позвоночник получает двойной поворот).

Запуск:
    blender --background --factory-startup --python tools/dump_fbx_prerotation.py -- <файл.fbx>
"""
import sys

from io_scene_fbx import parse_fbx

path = sys.argv[sys.argv.index("--") + 1]
root, version = parse_fbx.parse(path)
print("FBX", path, "version", version)


def walk(elem, depth=0):
    for child in elem.elems:
        yield child
        yield from walk(child, depth + 1)


def props_of(model):
    out = {}
    for e in model.elems:
        if e.id == b"Properties70":
            for p in e.elems:
                if p.id != b"P":
                    continue
                name = p.props[0].decode() if isinstance(p.props[0], bytes) else str(p.props[0])
                vals = p.props[4:]
                out[name] = vals
    return out


objects = next(e for e in root.elems if e.id == b"Objects")
for e in objects.elems:
    if e.id != b"Model":
        continue
    name = e.props[1].decode(errors="replace").split("\x00")[0]
    kind = e.props[2].decode(errors="replace")
    pr = props_of(e)

    def fmt(key):
        v = pr.get(key)
        if v is None:
            return "-"
        return "(" + ",".join(f"{float(x):0.3f}" for x in v) + ")"

    print(f"{kind:12s} {name:32s} Pre={fmt('PreRotation')} Rot={fmt('Lcl Rotation')} "
          f"T={fmt('Lcl Translation')} order={pr.get('RotationOrder', ['-'])[0]} "
          f"active={pr.get('RotationActive', ['-'])[0]}")
