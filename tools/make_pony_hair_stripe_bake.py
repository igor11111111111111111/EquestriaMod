# -*- coding: utf-8 -*-
"""Полосатая текстура гривы/хвоста пони — печёт полосы ВДОЛЬ роста волоса (как у Твайлайт: три
широкие ленты бок о бок по всей длине пряди), а не поперёк.

Первая версия (см. историю: bake_tail_stripes.py/bake_stripes_all.py, черновики) ставила полосы
по локальной оси Z объекта (вдоль роста) в режиме Wave Texture BANDS — это даёт КОЛЬЦА, сложенные
одно на другое от корня к кончику, поперёк роста волоса. Пользователь сверился с оригиналом
(скриншот Твайлайт Спаркл, 30.09.2026): в шоу полосы — это отдельные пряди-ленты, бегущие ВДОЛЬ
всей длины гривы/хвоста, а не поперечные кольца. Чтобы получить такое через Wave Texture
(она умеет только линейную волну по одной декартовой оси, не угловую), нужна не встроенная BANDS,
а свой угол вокруг оси роста (Z): ATAN2(Y, X) -> 0..1 -> * число_полос -> дробная часть ->
резкая ступенька (ColorRamp CONSTANT). Печём, как и раньше, через реальную 3D-геометрию/UV
(Cycles EMIT bake) — UV хвоста/гривы рваная россыпь мелких островов, нарисованное прямо в
текстурное пространство рвётся на пятна (см. dump_tail_uv.py, история сессии 29.09.2026).

Запуск:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\make_pony_hair_stripe_bake.py

Результат — assets/pony/textures/eq_pony_hair_stripe_d.png (хвост, имя историческое) и
eq_pony_mane_stripe_d.png (сама грива). Дальше — tools/tpac_export (или редактор), чтобы
перезалить текстуру в уже существующие материалы eq_pony_tail_stripe/eq_pony_mane_stripe.
"""
import os

import bpy

ROOT = r"C:\Users\New\EquestriaMod"
TEX = os.path.join(ROOT, "assets", "pony", "textures")
SIZE = 1024

# (объект, файл текстуры, число полос по кругу вокруг оси роста)
PARTS = [
    ("eq_pony_tail", "eq_pony_hair_stripe_d.png", 3),
    ("eq_pony_hair", "eq_pony_mane_stripe_d.png", 3),
]

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.samples = 4
bpy.context.scene.cycles.bake_type = "EMIT"
# UV хвоста/гривы — россыпь мелких островов (dump_tail_uv.py, 29.09.2026). Без запаса каждый
# остров печётся впритык к чёрному фону атласа вокруг; в игре текстура идёт через мипмапы/
# трилинейную фильтрацию, и на границе острова подмешивается этот чёрный — по всей модели
# получается рябь "шашечками" (замечено 30.09.2026, скриншот в игре, хотя рендер в Blender
# по живому узлу — без запекания через UV — выглядел ровно).
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
    # Object-координаты меряют угол от локального НУЛЯ объекта — а он не на осевой линии самой
    # пряди (кость/пивот смещены в сторону), поэтому ATAN2(Y,X) прыгал как попало и полосы
    # рассыпались в пятна (проверено 30.09.2026, первая попытка). Generated — координаты в
    # рамке собственного bounding box меша (0..1 по каждой оси), центр (0.5, 0.5) уже близко
    # к осевой линии пряди при любом смещении пивота.
    center = nt.nodes.new("ShaderNodeVectorMath")
    center.operation = "SUBTRACT"
    center.inputs[1].default_value = (0.5, 0.5, 0.5)

    sep = nt.nodes.new("ShaderNodeSeparateXYZ")

    # Угол вокруг оси роста волоса (Z) из X/Y поперечного сечения, относительно центра.
    angle = nt.nodes.new("ShaderNodeMath")
    angle.operation = "ARCTAN2"

    norm = nt.nodes.new("ShaderNodeMath")
    norm.operation = "DIVIDE"
    norm.inputs[1].default_value = 6.283185307  # 2*pi -> угол в 0..1 оборота

    shift = nt.nodes.new("ShaderNodeMath")
    shift.operation = "ADD"
    shift.inputs[1].default_value = 0.5  # ATAN2 даёт -0.5..0.5 оборота, сдвигаем в 0..1

    scale = nt.nodes.new("ShaderNodeMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = bands

    frac = nt.nodes.new("ShaderNodeMath")
    frac.operation = "MODULO"
    frac.inputs[1].default_value = 1.0  # дробная часть -> одна полоса из bands, повторяется по кругу

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.47, 0.47, 0.47, 1.0)  # тёмная полоса
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)     # светлая полоса

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
