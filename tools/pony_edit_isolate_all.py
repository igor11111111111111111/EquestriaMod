import math, bpy
bpy.ops.wm.open_mainfile(filepath=r"C:\Users\New\EquestriaMod\assets\pony\eq_pony_edit.blend")
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"; scene.display.shading.light = "STUDIO"; scene.display.shading.color_type = "OBJECT"
scene.render.resolution_x = scene.render.resolution_y = 900
new_col = bpy.data.collections["Пони - цельная"]
names = [x.name for x in new_col.objects]
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); cam.data.type = "ORTHO"
scene.collection.objects.link(cam); scene.camera = cam
cam.location = (0.4, 4, 1.4); cam.rotation_euler = (math.pi/2, 0, math.pi); cam.data.ortho_scale = 1.8
for hide_name in [None] + names:
    show = set(names) - ({hide_name} if hide_name else set())
    for o in bpy.data.objects:
        if o.type == "MESH": o.hide_render = o.name not in show
        if o.type == "ARMATURE": o.hide_render = True
    tag = "without_" + hide_name if hide_name else "everything"
    scene.render.filepath = r"C:\Users\New\AppData\Local\Temp\claude\C--Users-New\35af1432-7ffb-43e5-8473-d763086e03ba\scratchpad\iso2_%s.png" % tag
    bpy.ops.render.render(write_still=True)
