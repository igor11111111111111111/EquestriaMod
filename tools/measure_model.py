# Промеры чужой модели: куда смотрит, где ноги, где голова, где хвост.
#
#   blender --background --factory-startup --python measure_model.py -- <файл .glb> [ось_длины]
#
# Печатает профиль объёма по длинной оси (сколько вершин и какая высота в каждом срезе) и
# положение «стоп» — сгустков вершин у самого пола. По этому видно, четвероногая ли модель,
# с какого конца голова и где крепятся ноги. Нужен перед переделкой модели в антро-позу
# (tools/convert_creature.py).
import sys

import bpy
import numpy as np
from mathutils import Vector

path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=path)
obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
pts = []
for ob in obs:
    m = ob.matrix_world
    pts.extend([m @ v.co for v in ob.data.vertices])
P = np.array([[p.x, p.y, p.z] for p in pts])
lo, hi = P.min(0), P.max(0)
size = hi - lo
print("[measure] вершин %d, габариты X=%.3f Y=%.3f Z=%.3f" % (len(P), *size))
print("[measure] минимум %s, максимум %s" % (np.round(lo, 3).tolist(), np.round(hi, 3).tolist()))

long_axis = int(np.argmax(size[:2]))          # 0 = X, 1 = Y: длинная горизонтальная ось
if len(sys.argv) > sys.argv.index("--") + 2:
    long_axis = int(sys.argv[sys.argv.index("--") + 2])
side_axis = 1 - long_axis
print("[measure] длинная ось: %s, поперечная: %s, верх: Z" % ("XY"[long_axis], "XY"[side_axis]))

# профиль по длинной оси: 20 срезов
N = 20
edges = np.linspace(lo[long_axis], hi[long_axis], N + 1)
print("[measure] профиль (срез: доля вершин, верх Z, низ Z, ширина по поперечной оси):")
for i in range(N):
    m = (P[:, long_axis] >= edges[i]) & (P[:, long_axis] < edges[i + 1] + (1e-6 if i == N - 1 else 0))
    if m.sum() == 0:
        print("   %5.2f..%5.2f  пусто" % (edges[i], edges[i + 1]))
        continue
    q = P[m]
    print("   %5.2f..%5.2f  %5.1f%%  Z %5.2f..%5.2f  ширина %.2f"
          % (edges[i], edges[i + 1], 100 * m.mean(), q[:, 2].min(), q[:, 2].max(),
             q[:, side_axis].max() - q[:, side_axis].min()))

# «стопы»: вершины у самого пола, разбитые по четвертям
floor = P[P[:, 2] < lo[2] + 0.12 * size[2]]
print("[measure] вершин у пола: %d" % len(floor))
if len(floor):
    mid_long = (lo[long_axis] + hi[long_axis]) / 2
    mid_side = (lo[side_axis] + hi[side_axis]) / 2
    for a, alabel in ((True, "перед"), (False, "зад")):
        for b, blabel in ((True, "лево"), (False, "право")):
            m = ((floor[:, long_axis] < mid_long) == a) & ((floor[:, side_axis] < mid_side) == b)
            if m.sum():
                c = floor[m].mean(0)
                print("   %s-%s: %d вершин, центр %s" % (alabel, blabel, m.sum(), np.round(c, 3).tolist()))
