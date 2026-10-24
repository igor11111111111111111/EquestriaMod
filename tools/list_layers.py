# Список слоёв рельефа сцены с их текстурами.
#
#   python list_layers.py <scene.xscene> [ещё сцены...]
import re
import sys

for path in sys.argv[1:]:
    text = open(path, encoding="utf-8").read()
    start = text.find("<layers", text.find("<terrain "))
    block = text[start:text.find("</layers>", start)]
    print("=" * 70)
    print(path)
    for layer in re.findall(r'<layer name="([^"]*)">(.*?)</layer>', block, re.S):
        name, body = layer
        summer = re.search(r"<summer (.*?)</summer>", body, re.S)
        if not summer:
            continue
        tex = dict(re.findall(r'<texture type="([^"]*)" name="([^"]*)"', summer.group(1)))
        scale = re.search(r'scale="([^"]*)"', summer.group(1))
        blend = re.search(r'is_mesh_blend_layer="([^"]*)"', summer.group(1))
        meshes = re.findall(r'<mesh name="([^"]*)"', summer.group(1))
        print("  %-14s d=%-32s n=%-24s s=%-22s scale=%s blend=%s flora=%s"
              % (name, tex.get("diffusemap"), tex.get("normalmap"), tex.get("specularmap"),
                 scale.group(1) if scale else "?", blend.group(1) if blend else "?", meshes[:3]))
