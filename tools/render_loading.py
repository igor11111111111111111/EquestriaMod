"""Character render for the loading screen splash (transparent background).

  blender --background ../assets/changeling/eq_changeling.blend --python render_loading.py -- ../assets/loading

Draws two figures: a pony in imperial armour (the armour is taken from assets/pony_armor/eq_pony_armor.blend)
and a changeling with wings. The lighting is dramatic, the background transparent — it is filled in by
tools/make_loading_screen.py. Poses are set by bone rotations: in the source the character stands in a T-pose.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
HERE = os.path.dirname(os.path.abspath(__file__))
ARMOR_BLEND = os.path.join(HERE, "..", "assets", "pony_armor", "eq_pony_armor.blend")
ATLAS = os.path.join(HERE, "..", "assets", "changeling", "textures", "eq_twilight_body_d.png")
os.makedirs(OUT, exist_ok=True)

PONY = {"eq_twilight_head", "eq_twilight_body", "eq_twilight_legs", "eq_twilight_gloves",
        "eq_twilight_mane", "eq_twilight_tail"}
ARMOR = ["eq_pony_imperial_lamellar_a", "eq_pony_imperial_boots", "eq_pony_imperial_gauntlets"]
CHANGELING = {"eq_changeling_head", "eq_changeling_body", "eq_changeling_legs", "eq_changeling_gloves",
              "eq_changeling_crest", "eq_changeling_wings"}
POSE = {  # lower the arms along the body, turn the head slightly
    "bip01_l_upperarm_twist_15": (0.0, 0.0, -1.15),
    "bip01_r_upperarm_twist_22": (0.0, 0.0, -1.15),
    "bip01_head_13": (0.05, 0.0, 0.10),
    "bip01_spine1_10": (0.0, 0.04, 0.0),
}


def log(*a):
    print("[loading]", *a, flush=True)


scene = bpy.context.scene
skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")

# armour: load the needed meshes from the armour file and bind them to our skeleton.
# The file may be missing: pony armour was removed from the mod on 24.09.2026 (all races wear vanilla,
# see the header of tools/make_items.py), and assets/pony_armor was deleted along with it. The loading
# screen images are already rendered and lie in Module; if they need re-rendering, the armour will have
# to be fitted to the skeleton again — e.g. by exporting the vanilla meshes with
# tools/tpac_export obj and putting them here.
if not os.path.exists(ARMOR_BLEND):
    raise SystemExit("нет " + ARMOR_BLEND + " — пони-броня удалена из мода, рисовать нечего")
armor_objects = []
with bpy.data.libraries.load(os.path.abspath(ARMOR_BLEND)) as (src, dst):
    dst.objects = [name for name in src.objects if name in ARMOR]
for ob in dst.objects:
    if ob is None:
        continue
    scene.collection.objects.link(ob)
    ob.parent = skel
    ob.matrix_parent_inverse = skel.matrix_world.inverted()
    for mod in list(ob.modifiers):
        ob.modifiers.remove(mod)
    ob.modifiers.new("Armature", "ARMATURE").object = skel
    armor_objects.append(ob.name)
# the armour refers to vanilla materials that are not in this file: give it a plain grey metal
steel = bpy.data.materials.new("eq_loading_steel")
steel.use_nodes = True
bsdf = steel.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.32, 0.33, 0.36, 1.0)
bsdf.inputs["Metallic"].default_value = 0.85
bsdf.inputs["Roughness"].default_value = 0.35
for name in armor_objects:
    me = bpy.data.objects[name].data
    me.materials.clear()
    me.materials.append(steel)
log("броня:", armor_objects)

for mat in bpy.data.materials:
    if mat.name == "eq_twilight_body" and mat.node_tree:
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                node.image = bpy.data.images.load(os.path.abspath(ATLAS), check_existing=True)
    mat.use_backface_culling = True
for ob in bpy.data.objects:
    if ob.type == "MESH" and ob.data.shape_keys:
        for key in ob.data.shape_keys.key_blocks[1:]:
            key.value = 0.0
missing = []
for bone_name, rot in POSE.items():
    bone = skel.pose.bones.get(bone_name)
    if bone is None:
        missing.append(bone_name)
        continue
    bone.rotation_mode = "XYZ"
    bone.rotation_euler = rot
if missing:
    log("нет костей:", missing)
bpy.context.view_layer.update()

for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.render.resolution_x, scene.render.resolution_y = 1000, 1500
scene.render.film_transparent = True
world = bpy.data.worlds.new("loading")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.06, 0.08, 0.12, 1.0)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
scene.world = world

key = bpy.data.objects.new("key", bpy.data.lights.new("key", "AREA"))
key.data.energy, key.data.size = 1200.0, 3.0
key.location = Vector((2.4, -3.2, 2.8))
key.rotation_euler = (math.radians(60), 0, math.radians(38))
scene.collection.objects.link(key)
rim = bpy.data.objects.new("rim", bpy.data.lights.new("rim", "AREA"))
rim.data.energy, rim.data.size = 900.0, 2.0
rim.data.color = (0.45, 0.85, 1.0)
rim.location = Vector((-2.6, 2.4, 2.6))
rim.rotation_euler = (math.radians(68), 0, math.radians(-135))
scene.collection.objects.link(rim)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.lens = 85
scene.collection.objects.link(cam)
scene.camera = cam


def shot(names, path, target, distance, angle_deg, tilt=0.1):
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            ob.hide_render = ob.name not in names
    a = math.radians(angle_deg)
    direction = Vector((math.sin(a), -math.cos(a), tilt)).normalized()
    cam.location = Vector(target) + direction * distance
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log("отрисовано", os.path.basename(path))


shot(PONY | set(armor_objects), os.path.join(OUT, "pony.png"), (0, 0, 1.05), 4.6, 20)
shot(CHANGELING, os.path.join(OUT, "changeling.png"), (0, 0, 1.05), 4.6, -20)
