# Summary of the world map navigation mesh (Module\SceneObj\Main_map\navmesh.bin). Read-only.
#
#   py -3 tools\make_navmesh.py [path to navmesh.bin]
#
# Also checks the settlements from ModuleData/equestria_settlements.xml: whether they and their gates
# stand on land faces and are connected by land to the capital (town_empire_0).
#
# The mesh (vertices and faces) is built by the Modding Kit editor, and the terrain types of the faces
# are set by tools/tag_navmesh.py. It used to be believed that the game rejects a file written by code —
# but the real cause of the motionless parties back then was face type 0 (see
# EquestriaPartyNavigationModel), and header bytes 32..48 are just junk from the editor's memory, not
# a checksum.
#
# How to rebuild the mesh:
#   1. tools\editor.ps1 — open the editor.
#   2. File -> Open Scene, enter the path via
#      tools\file_dialog.ps1 -Title "Open Scene" -Path "...\Modules\EquestriaMod\SceneObj\Main_map\scene.xscene"
#   3. The «N» icon on the toolbar (Navigation Mesh) -> Generation Tools -> Generate Grids ->
#      «Clear old faces?» -> Yes. Generation needs a sp_player spawn point in the scene — it is
#      in the centre of the map.
#   4. File -> Save Navigation Mesh. The scene does not need to be saved.
#
# Signs of a bad mesh: lords stand with the Hold activity and fight in place; the player's party does
# not go to a town when ordered (/eqlongrun writes "path check" to
# Module\eq_exceptions.log).
#
# Format (worked out from vanilla Main_map):
#   "RNM1", compressed size, 3, 0, uncompressed size, 0, compressed size, 0, 16 service bytes,
#   then an LZ4 stream. Inside:
#     "NMG9", vertex count, vertices as three floats (x, y, height);
#     edge count, an edge is 6 int32: (-1, vertex from, vertex to, -1, -1, 0);
#     face count, a face: corner count, corner indices, edge indices, 5 int32, a byte.
#         The third of the five numbers is the terrain type (TaleWorlds.Core.TerrainType: 1 plain,
#         4 forest, 7 mountains, 10 water). The editor leaves 0, and the game works with that;
#     tail: the number 32 and 256 zero bytes.
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain_bin import lz4_decompress

DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "Module", "SceneObj", "Main_map", "navmesh.bin")
PAYLOAD = 48


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    raw = open(path, "rb").read()
    if raw[:4] != b"RNM1":
        raise SystemExit("не сетка проходимости: " + path)
    data = lz4_decompress(raw[PAYLOAD:], struct.unpack_from("<I", raw, 16)[0])
    if data[:4] != b"NMG9":
        raise SystemExit("сетка не разобралась: " + path)

    count = struct.unpack_from("<I", data, 4)[0]
    vertices = [struct.unpack_from("<3f", data, 8 + i * 12) for i in range(count)]
    off = 8 + count * 12
    edges = struct.unpack_from("<I", data, off)[0]
    off += 4 + edges * 24
    faces = struct.unpack_from("<I", data, off)[0]
    off += 4
    corners = collections.Counter()
    terrain = collections.Counter()
    face_list = []
    for _ in range(faces):
        n = struct.unpack_from("<I", data, off)[0]
        corners[n] += 1
        verts = struct.unpack_from("<%dI" % n, data, off + 4)
        face_edges = struct.unpack_from("<%dI" % n, data, off + 4 + n * 4)
        off += 4 + n * 8
        kind = struct.unpack_from("<5i", data, off)[2]
        terrain[kind] += 1
        face_list.append((verts, face_edges, kind))
        off += 21

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    print(f"{path}: {len(raw)} байт на диске, {len(data)} данных")
    print(f"вершин {count}, рёбер {edges}, граней {faces} (углов: {dict(corners)})")
    print(f"охват x {min(xs):.1f}..{max(xs):.1f}, y {min(ys):.1f}..{max(ys):.1f}, высота {min(zs):.1f}..{max(zs):.1f}")
    print(f"типы местности: {dict(terrain)}")
    check_settlements(path, vertices, face_list)


# Types passable for normal parties (DefaultPartyNavigationModel.IsTerrainTypeValidForDefault);
# 0 is "not set", our EquestriaPartyNavigationModel treats it as plain.
PASSABLE = {0, 1, 2, 3, 4, 5, 6, 15, 16, 17, 20}


def check_settlements(path, vertices, faces):
    import xml.etree.ElementTree as ET
    xml = os.path.join(os.path.dirname(path), "..", "..", "ModuleData", "equestria_settlements.xml")
    if not os.path.exists(xml):
        return
    # our mesh is made of axis-aligned quads: find a face by the bounding box of its vertices
    boxes = []
    by_edge = collections.defaultdict(list)
    for index, (verts, face_edges, kind) in enumerate(faces):
        xs = [vertices[v][0] for v in verts]
        ys = [vertices[v][1] for v in verts]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
        for e in face_edges:
            by_edge[e].append(index)
    cell = max(boxes[0][2] - boxes[0][0], 1e-3)
    grid = {}
    for index, (x0, y0, _x1, _y1) in enumerate(boxes):
        grid[(int(round(x0 / cell)), int(round(y0 / cell)))] = index

    def face_at(x, y):
        return grid.get((int(x // cell), int(y // cell)))

    # land connectivity
    land = [kind in PASSABLE for _v, _e, kind in faces]
    component = [-1] * len(faces)
    current = 0
    for start in range(len(faces)):
        if component[start] >= 0 or not land[start]:
            continue
        stack = [start]
        component[start] = current
        while stack:
            f = stack.pop()
            for e in faces[f][1]:
                for g in by_edge[e]:
                    if component[g] < 0 and land[g]:
                        component[g] = current
                        stack.append(g)
        current += 1

    bad = []
    points = {}
    for node in ET.parse(xml).getroot():
        if node.get("posX") is None:
            continue
        sid = node.get("id")
        spots = [("центр", float(node.get("posX")), float(node.get("posY")))]
        if node.get("gate_posX") is not None:
            spots.append(("ворота", float(node.get("gate_posX")), float(node.get("gate_posY"))))
        for what, x, y in spots:
            f = face_at(x, y)
            if f is None:
                bad.append(f"{sid}: {what} вне сетки ({x:.0f}, {y:.0f})")
            elif not land[f]:
                bad.append(f"{sid}: {what} на непроходимой грани ({x:.0f}, {y:.0f})")
            points[(sid, what)] = f
    home = points.get(("town_empire_0", "ворота")) or points.get(("town_empire_0", "центр"))
    if home is not None and land[home]:
        islands = collections.Counter()
        for (sid, what), f in points.items():
            if f is not None and land[f] and component[f] != component[home] and what != "центр":
                islands[sid] += 1
            elif f is not None and land[f] and component[f] != component[home] and sid.startswith("village"):
                islands[sid] += 1
        if islands:
            bad.append("не связаны по суше со столицей: " + ", ".join(sorted(islands)))
    print(f"участков суши: {current}; поселений проверено: {len({k[0] for k in points})}")
    for line in bad:
        print("  !", line)
    if not bad:
        print("все поселения и ворота на суше и связаны со столицей")


if __name__ == "__main__":
    main()
