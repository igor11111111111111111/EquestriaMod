# -*- coding: utf-8 -*-
"""Striped texture of the pony mane/tail: bakes stripes ALONG the hair growth (like Twilight's: three
wide ribbons side by side along the whole length of the strand), not across it.

The first version (see history: bake_tail_stripes.py/bake_stripes_all.py, drafts) placed the stripes
along the object's local Z axis (along the growth) in Wave Texture BANDS mode; this gives RINGS stacked
one on another from root to tip, across the hair growth. The user checked against the original
(a screenshot of Twilight Sparkle, 30.09.2026): in the show the stripes are separate ribbon strands running ALONG
the whole length of the mane/tail, not transverse rings. To get this via Wave Texture
(it can only do a linear wave along one Cartesian axis, not an angular one), what is needed is not the built-in BANDS
but our own angle around the growth axis (Z): ATAN2(Y, X) -> 0..1 -> * number_of_stripes -> fractional part ->
a sharp step (ColorRamp CONSTANT). As before, we bake through the real 3D geometry/UV
(Cycles EMIT bake): the tail/mane UV is a ragged scatter of small islands, and anything painted directly in
texture space breaks into blotches (see dump_tail_uv.py, session history 29.09.2026).

Run:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\make_pony_hair_stripe_bake.py

Result: assets/pony/textures/eq_pony_hair_stripe_d.png (the tail, the name is historical) and
eq_pony_mane_stripe_d.png (the mane itself). Then tools/tpac_export (or the editor), to
re-upload the texture into the already existing materials eq_pony_tail_stripe/eq_pony_mane_stripe.
"""
import os

import bpy

ROOT = r"C:\Users\New\EquestriaMod"
TEX = os.path.join(ROOT, "assets", "pony", "textures")
SIZE = 1024

# (object, texture file, number of stripes around the growth axis)
PARTS = [
    ("eq_pony_tail", "eq_pony_hair_stripe_d.png", 3),
    ("eq_pony_hair", "eq_pony_mane_stripe_d.png", 3),
]

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.samples = 4
bpy.context.scene.cycles.bake_type = "EMIT"
# The tail/mane UV is a scatter of small islands (dump_tail_uv.py, 29.09.2026). Without padding each
# island is baked right up against the black atlas background around it; in game the texture goes through mipmaps/
# trilinear filtering, and at the island border this black gets mixed in: across the whole model
# this gives a "checkerboard" ripple (noticed 30.09.2026, in-game screenshot, although the Blender render
# from the live node, without baking through UV, looked even).
bpy.context.scene.render.bake.margin = 32

col = bpy.data.collections.get("Пони - цельная")


def log(*a):
    print("[bake]", *a, flush=True)


def bake_part(name, out_file, bands):
    ob = col.objects.get(name) if col else bpy.data.objects.get(name)
    if ob is None:
        log("НЕ НАЙДЕН:", name)
        return

    mat = bpy.data.materials.new(name + "_stripe_bake")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)

    coord = nt.nodes.new("ShaderNodeTexCoord")
    # Object coordinates measure the angle from the object's local ZERO, and it is not on the centre line of the
    # strand itself (the bone/pivot are offset to the side), so ATAN2(Y,X) jumped all over the place and the stripes
    # scattered into blotches (verified 30.09.2026, first attempt). Generated: coordinates in
    # the frame of the mesh's own bounding box (0..1 on each axis), the centre (0.5, 0.5) is already close
    # to the strand's centre line at any pivot offset.
    center = nt.nodes.new("ShaderNodeVectorMath")
    center.operation = "SUBTRACT"
    center.inputs[1].default_value = (0.5, 0.5, 0.5)

    sep = nt.nodes.new("ShaderNodeSeparateXYZ")

    # The angle around the hair growth axis (Z) from the X/Y of the cross-section, relative to the centre.
    angle = nt.nodes.new("ShaderNodeMath")
    angle.operation = "ARCTAN2"

    norm = nt.nodes.new("ShaderNodeMath")
    norm.operation = "DIVIDE"
    norm.inputs[1].default_value = 6.283185307  # 2*pi -> angle in 0..1 turns

    shift = nt.nodes.new("ShaderNodeMath")
    shift.operation = "ADD"
    shift.inputs[1].default_value = 0.5  # ATAN2 gives -0.5..0.5 turns, shift to 0..1

    scale = nt.nodes.new("ShaderNodeMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = bands

    frac = nt.nodes.new("ShaderNodeMath")
    frac.operation = "MODULO"
    frac.inputs[1].default_value = 1.0  # fractional part -> one stripe out of bands, repeated around the circle

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.47, 0.47, 0.47, 1.0)  # dark stripe
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)     # light stripe

    emit = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")

    img = bpy.data.images.new(name + "_stripe_bake_img", width=SIZE, height=SIZE)
    img_node = nt.nodes.new("ShaderNodeTexImage")
    img_node.image = img

    nt.links.new(coord.outputs["Generated"], center.inputs[0])
    nt.links.new(center.outputs["Vector"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Y"], angle.inputs[0])
    nt.links.new(sep.outputs["X"], angle.inputs[1])
    nt.links.new(angle.outputs["Value"], norm.inputs[0])
    nt.links.new(norm.outputs["Value"], shift.inputs[0])
    nt.links.new(shift.outputs["Value"], scale.inputs[0])
    nt.links.new(scale.outputs["Value"], frac.inputs[0])
    nt.links.new(frac.outputs["Value"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])

    for n in nt.nodes:
        n.select = False
    img_node.select = True
    nt.nodes.active = img_node

    ob.data.materials.clear()
    ob.data.materials.append(mat)

    for other in bpy.data.objects:
        other.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

    bpy.ops.object.bake(type="EMIT")

    out_path = os.path.join(TEX, out_file)
    img.filepath_raw = out_path
    img.file_format = "PNG"
    img.save()
    log(name, "->", out_path)


for part_name, part_file, part_bands in PARTS:
    bake_part(part_name, part_file, part_bands)
