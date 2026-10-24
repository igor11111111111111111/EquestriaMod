# Generates the races "pony", "changeling" and "deer" from Bannerlord's vanilla human race
# (the way The Old Realms makes races):
#   ModuleData/pony_skins.xml        — <race id="pony">: 10 skin variants with Twilight meshes,
#                                      <race id="changeling"> and <race id="deer">: the same with their own meshes
#   ModuleData/pony_monsters.xml     — pony, pony_child, pony_settlement(_slow/_fast) and the same for the other races
#   ModuleData/pony_action_sets.xml  — as_pony_* based on all as_human_* (the changeling moves the same way)
#   ModuleData/project.mbproj        — skin / monster / action_set registration for the engine
#
# py tools/make_pony_race.py <game Modules folder> <mod Module folder>
import colorsys
import copy
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

GAME_MODULES, MOD = sys.argv[1], sys.argv[2]
NATIVE = os.path.join(GAME_MODULES, "Native", "ModuleData")
OUT = os.path.join(MOD, "ModuleData")

RACE = "pony"
MESHES = {
    "body_meta_mesh": "eq_twilight_body",
    "body_meta_mesh_shoulders": "eq_twilight_body",
    "legs_mesh": "eq_twilight_legs",
    "hands_mesh": "eq_twilight_gloves",
    "face_meta_mesh": "eq_twilight_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
MATERIAL = "eq_twilight_body"  # shared atlas material of the old pony: the placeholders use it too
# The new pony (tools/make_pony_model.py, Meshy alicorn): its own model with a horn, the mane in the head,
# wings and tail. The former Twilight stayed as placeholder meshes (MESHES above) for races that
# are waiting for their import, and as the pony itself until the new FBX is imported in the editor.
PONY_MESHES = {
    "body_meta_mesh": "eq_pony_body",
    "body_meta_mesh_shoulders": "eq_pony_body",
    "legs_mesh": "eq_pony_legs",
    "hands_mesh": "eq_pony_gloves",
    "face_meta_mesh": "eq_pony_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
# The new pony's texture is white with blue eyes: the palette multiplies it, so the first tone is
# "as in the model", the rest are soft coats. No dark ones: they dim the painted eyes.
PONY_PALETTE = [
    "1.00, 1.00, 1.00",  # the model's own colour: white
    "1.00, 0.86, 0.94",  # pink
    "0.80, 0.92, 1.00",  # light blue
    "1.00, 0.96, 0.75",  # cream
    "0.93, 0.80, 0.98",  # lilac
    "0.82, 1.00, 0.86",  # mint
    "1.00, 0.84, 0.68",  # peach
    "0.78, 0.84, 1.00",  # bluish
    "0.88, 0.88, 0.92",  # grey
    "0.72, 0.70, 0.78",  # dark grey
]
# The new pony's hairstyle is her built-in wavy mane (eq_pony_hair): the only one, but the hair colour
# from the appearance screen works on it (material eq_pony_hair on the vanilla hair shader,
# tools/pony_material.ps1). The horn is a separate body part (eq_pony_horn), like the tail and wings: it is
# attached to the skeleton by src/EquestriaBodyParts.cs and is not chosen as a hairstyle.
PONY_MANE = ["eq_pony_hair"]
# Exactly 24 colours, all different: the appearance screen draws two rows of 12, and with 12 colours the
# bottom row repeated the top one. The hair shader bleaches light colours, so the tones are saturated; the
# top row is bright "cartoon" colours, the bottom one muted and natural.
PONY_MANE_COLORS = [
    "0.85, 0.20, 0.55", "0.45, 0.20, 0.75", "0.15, 0.30, 0.85", "0.10, 0.60, 0.85",
    "0.05, 0.65, 0.60", "0.15, 0.70, 0.30", "0.60, 0.80, 0.15", "0.90, 0.75, 0.10",
    "0.95, 0.50, 0.10", "0.85, 0.15, 0.15", "0.95, 0.55, 0.65", "0.65, 0.45, 0.90",
    "0.55, 0.12, 0.30", "0.25, 0.12, 0.45", "0.10, 0.18, 0.50", "0.08, 0.35, 0.45",
    "0.10, 0.35, 0.25", "0.40, 0.35, 0.10", "0.55, 0.30, 0.08", "0.35, 0.18, 0.08",
    "0.75, 0.70, 0.60", "0.50, 0.50, 0.55", "0.20, 0.20, 0.24", "0.06, 0.06, 0.08",
]
PONY_MANE_TAG = "PonyMane"   # the same tag as the old manes: troops and world depend on it (make_troops, make_world)
# The new pony (tools/make_pony_model.py, Meshy alicorn): its own model with a horn, the mane in the head,
# wings and tail. The former Twilight stayed as placeholder meshes (MESHES above) for races that
# are waiting for their import, and as the pony itself until the new FBX is imported in the editor.
PONY_MESHES = {
    "body_meta_mesh": "eq_pony_body",
    "body_meta_mesh_shoulders": "eq_pony_body",
    "legs_mesh": "eq_pony_legs",
    "hands_mesh": "eq_pony_gloves",
    "face_meta_mesh": "eq_pony_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
# The new pony's texture is white with blue eyes: the palette multiplies it, so the first tone is
# "as in the model", the rest are soft coats. No dark ones: they dim the painted eyes.
PONY_PALETTE = [
    "1.00, 1.00, 1.00",  # the model's own colour: white
    "1.00, 0.86, 0.94",  # pink
    "0.80, 0.92, 1.00",  # light blue
    "1.00, 0.96, 0.75",  # cream
    "0.93, 0.80, 0.98",  # lilac
    "0.82, 1.00, 0.86",  # mint
    "1.00, 0.84, 0.68",  # peach
    "0.78, 0.84, 1.00",  # bluish
    "0.88, 0.88, 0.92",  # grey
    "0.72, 0.70, 0.78",  # dark grey
]
# The horn is the new pony's only "hairstyle" (the mane is built into the head and tinted with the coat):
# the hair colour from the appearance screen works on it (material eq_pony_hair on the vanilla hair
# shader, tools/pony_material.ps1). The hair shader bleaches light colours, so the tones are saturated.
PONY_HORN = ["eq_pony_hair"]
PONY_HORN_TAG = "PonyMane"   # the same tag as the old manes: troops and world depend on it (make_troops, make_world)
PONY_HORN_COLORS = [
    "0.80, 0.72, 0.55", "0.70, 0.55, 0.25", "0.55, 0.45, 0.60", "0.45, 0.60, 0.75",
    "0.75, 0.50, 0.60", "0.60, 0.65, 0.65", "0.85, 0.80, 0.70", "0.50, 0.35, 0.55",
    "0.35, 0.50, 0.70", "0.65, 0.60, 0.45", "0.80, 0.60, 0.40", "0.30, 0.30, 0.40",
]
# Special changeling face variant: green eyes with a slit pupil (Chrysalis and her line).
# It was made for the OLD model (tools/make_changeling.py, its own eye cell in the pony atlas).
# The new model came with its own atlas that has no such cell, so there is no special face for now:
# None means all face variants use the race's shared material. Bring it back once the queen's eye
# cell is drawn in the new atlas.
CHANGELING_QUEEN_FACE = None

# Pony coats: multipliers for the body texture (the base fur is lilac, so the shades are soft).
# The first point is 1,1,1: the model's original colour.
# Cutie marks: names of their own overlay materials, once they appear in the editor. An empty list keeps
# the human tattoos (handy to check whether the overlay channel works on the pony material).
# The cutie mark is made as geometry in the tail item (convert_twilight.py): engine overlays are drawn only
# on the face, never on the body. What remains here is human war paint for the face.
TATTOO_MATERIALS = []

COAT_PALETTE = [
    "0.93, 0.74, 0.95",  # lilac, like the original Twilight
    "1.00, 0.98, 0.95",  # white
    "1.00, 0.78, 0.85",  # pink
    "0.70, 0.90, 1.00",  # light blue
    "1.00, 0.95, 0.65",  # yellow
    "0.75, 1.00, 0.80",  # mint
    "1.00, 0.80, 0.55",  # orange
    "0.60, 0.70, 1.00",  # blue
    "0.85, 0.85, 0.88",  # grey
    "0.55, 0.50, 0.60",  # dark grey
]


def write(root, name):
    ET.indent(root, space="\t")
    path = os.path.join(OUT, name)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    print("written", path)


def keep_only_empty(parent):
    """Replace all variants with "empty" ones (no name): bald / no beard / no tattoo.

    The list length is kept: the appearance editor ("Randomize all") picks a random index
    from the human range, and with a shortened list the game crashed inside the engine.
    """
    children = list(parent)
    empty = next((c for c in children if not c.get("name")), None)
    if empty is None:
        return
    for i, child in enumerate(children):
        if child.get("name"):
            parent.remove(child)
            parent.insert(i, copy.deepcopy(empty))


# Changeling (tools/make_changeling_model.py): its own model with a horn, ears, two pairs of
# dragonfly wings and a tail; the wings and tail are attached to the skeleton by src/EquestriaBodyParts.cs.
# The former changeling was made from the pony mesh (tools/make_changeling.py); it is replaced entirely,
# the mesh names are the same.
# The black chitin is painted in the texture, so the palette is light, only a slight tint: the engine
# multiplies the whole head atlas by it, and a dark palette would dim the blue eyes and white fangs.
CHANGELING = "changeling"
CHANGELING_MESHES = {
    "body_meta_mesh": "eq_changeling_body",
    "body_meta_mesh_shoulders": "eq_changeling_body",
    "legs_mesh": "eq_changeling_legs",
    "hands_mesh": "eq_changeling_gloves",
    "face_meta_mesh": "eq_changeling_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
CHANGELING_PALETTE = [
    "1.00, 1.00, 1.00",
    "0.92, 0.96, 1.00",  # cold bluish
    "0.95, 1.00, 0.96",  # greenish
    "1.00, 0.97, 1.00",
    "0.88, 0.92, 0.98",
]

# Doe (tools/make_deer_model.py): its own model: long muzzle, deer ears, braids, antlers and
# a short tail. The former deer was a reworked pony on the shared atlas; nothing is left of it
# but the mesh names.
# The tail is a separate mesh attached to the skeleton by src/EquestriaBodyParts.cs; the antlers work
# as a hairstyle and are tinted by hair colour.
# Until the FBX is imported in the editor, the race sits in NOT_IMPORTED and uses the pony meshes.
DEER = "deer"
DEER_MESHES = {
    "body_meta_mesh": "eq_deer_body",
    "body_meta_mesh_shoulders": "eq_deer_body",
    "legs_mesh": "eq_deer_legs",
    "hands_mesh": "eq_deer_gloves",
    "face_meta_mesh": "eq_deer_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
# The doe has its own texture (assets/deer): the palette multiplies it, so the tones are close to white,
# from fawn to slightly cold, so that deer differ from each other but stay reddish.
DEER_PALETTE = [
    "1.00, 1.00, 1.00",  # the model's own colour
    "1.00, 0.94, 0.86",  # fawn
    "0.88, 0.80, 0.72",  # dark brown
    "0.94, 0.90, 0.86",  # grey-brown
    "1.00, 0.98, 0.94",  # light, almost white
    "0.78, 0.72, 0.68",  # almost black for such an atlas
    "1.00, 0.90, 0.78",  # red
    "0.92, 0.90, 0.88",  # grizzled
    "0.86, 0.78, 0.70",
    "1.00, 0.96, 0.90",
]
# Braids are the doe's "hairstyle"; the hair colour from the appearance screen works on them (material
# eq_deer_hair on the vanilla hair shader, see tools/deer_material.ps1). The antlers are a separate body part
# in four variants (10.10.2026), chosen by this same list: one braid lies under four names (copies are made
# by tools/deer_edit_export.py), and src/EquestriaBodyParts.cs shows the antlers with the same index as the
# worn braid. The list cycles: hairstyle 1, 5, 9… gives antlers 1,
# 2, 6, 10… gives antlers 2 and so on; the "bald" one (zero) gives antlers 1.
DEER_HAIR = ["eq_deer_hair", "eq_deer_hair_2", "eq_deer_hair_3", "eq_deer_hair_4"]
DEER_HAIR_TAG = "DeerAntlers"
DEER_HAIR_COLORS = [  # antlers: from white bone to dark brown, plus grizzled tones
    "0.82, 0.74, 0.60", "0.66, 0.54, 0.38", "0.50, 0.40, 0.28", "0.36, 0.28, 0.20",
    "0.24, 0.20, 0.16", "0.74, 0.70, 0.64", "0.56, 0.52, 0.48", "0.88, 0.82, 0.70",
    "0.62, 0.46, 0.30", "0.42, 0.34, 0.26", "0.78, 0.66, 0.46", "0.30, 0.26, 0.24",
]


# Griffon (tools/make_griffon.py): eagle head with a beak, feather "ears", clawed hands,
# a lion tail and wings growing from the arms. Wings and tail are separate meshes attached to the skeleton by
# src/EquestriaBodyParts.cs; the crown and nape feathers work as a hairstyle and are tinted by hair colour.
# The palette multiplies the model texture, so the tones are close to white: from warm sand
# to cold steel, so that griffons differ from each other but stay birds.
GRIFFON = "griffon"
GRIFFON_MESHES = {
    "body_meta_mesh": "eq_griffon_body",
    "body_meta_mesh_shoulders": "eq_griffon_body",
    "legs_mesh": "eq_griffon_legs",
    "hands_mesh": "eq_griffon_gloves",
    "face_meta_mesh": "eq_griffon_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
GRIFFON_PALETTE = [
    "1.00, 0.96, 0.88",  # fawn, the usual coat
    "0.96, 0.86, 0.68",  # sandy
    "1.00, 0.92, 0.78",  # golden
    "0.88, 0.80, 0.72",  # grey-brown
    "1.00, 1.00, 0.96",  # white, like a polar eagle
    "0.82, 0.74, 0.66",  # dark brown
    "0.98, 0.88, 0.74",  # reddish
    "0.86, 0.86, 0.84",  # steel
    "0.94, 0.82, 0.64",  # copper
    "0.78, 0.72, 0.68",  # almost black for a model with such an atlas
]
GRIFFON_HAIR = None  # the griffon has no separate hairstyle: head and ears are one piece with the head
GRIFFON_HAIR_TAG = "GriffonCrest"
GRIFFON_HAIR_COLORS = [  # crown feathers: from white to dark brown, plus a few bright ones
    "0.96, 0.92, 0.84", "0.86, 0.74, 0.54", "0.62, 0.50, 0.36", "0.40, 0.32, 0.24",
    "0.24, 0.20, 0.16", "0.72, 0.72, 0.70", "0.52, 0.56, 0.60", "0.90, 0.66, 0.30",
    "0.70, 0.30, 0.20", "0.34, 0.46, 0.62", "0.46, 0.58, 0.40", "0.58, 0.40, 0.56",
]
YAK = "yak"
# The yak's own model (tools/make_yak_model.py): horns, shaggy fur, a light mane and a tail
# tuft. The model's proportions are almost human, so the proportions were barely adjusted.
# The tail is a separate mesh attached to the skeleton by src/EquestriaBodyParts.cs; the mane works
# as a hairstyle and is tinted by hair colour.
# Until the FBX is imported in the editor, the race sits in NOT_IMPORTED and uses the pony meshes.
YAK_MESHES = {
    "body_meta_mesh": "eq_yak_body",
    "body_meta_mesh_shoulders": "eq_yak_body",
    "legs_mesh": "eq_yak_legs",
    "hands_mesh": "eq_yak_gloves",
    "face_meta_mesh": "eq_yak_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
# Head material per race (the others use the shared pony atlas MATERIAL): the engine takes the face
# material from face_textures in skins, and a race with its own texture must have its own.
RACE_MATERIAL = {YAK: "eq_yak_body", "dragon": "eq_dragon_body",  # DRAGON is declared below
                 GRIFFON: "eq_griffon_body", CHANGELING: "eq_changeling_body",
                 DEER: "eq_deer_body",
                 "hippogriff": "eq_hippogriff_body"}   # HIPPOGRIFF is declared below, as is DRAGON
# The yak has its own fur texture (assets/yak): the palette multiplies it, so the tones are close to white,
# from slightly warm to slightly cold, so that yaks differ from each other but stay brown.
YAK_PALETTE = [
    "1.00, 1.00, 1.00",
    "1.00, 0.94, 0.86",
    "0.92, 0.88, 0.84",
    "1.00, 0.90, 0.80",
    "0.86, 0.86, 0.90",
    "1.00, 0.97, 0.92",
    "0.90, 0.84, 0.78",
    "0.96, 0.96, 1.00",
    "1.00, 0.92, 0.90",
    "0.84, 0.80, 0.76",
]
YAK_HAIR = ["eq_yak_hair"]
YAK_HAIR_TAG = "YakMane"
YAK_HAIR_COLORS = [  # mane: from white and fawn to brown and black, like the fur of real yaks
    "0.94, 0.90, 0.80", "0.86, 0.74, 0.52", "0.66, 0.52, 0.34", "0.44, 0.34, 0.24",
    "0.26, 0.20, 0.16", "0.74, 0.72, 0.68", "0.54, 0.52, 0.50", "0.88, 0.84, 0.76",
    "0.62, 0.44, 0.28", "0.36, 0.30, 0.26", "0.80, 0.66, 0.44", "0.20, 0.18, 0.18",
]

# Previously the dragon and hippogriff realms used ordinary ponies, and the race did not match the culture.
# Now both have their own model, each with its own coat: in game you can see who is who.
DRAGON = "dragon"
# The dragon's own meshes (tools/make_dragon.py): body with arms, legs, hands, head. Tail and wings
# do not go here: src/EquestriaBodyParts.cs attaches them to the skeleton, like the pony's tail.
DRAGON_MESHES = {
    "body_meta_mesh": "eq_dragon_body",
    "body_meta_mesh_shoulders": "eq_dragon_body",
    "legs_mesh": "eq_dragon_legs",
    "hands_mesh": "eq_dragon_gloves",
    "face_meta_mesh": "eq_dragon_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
# Horns and crest are the dragon's "hairstyle": the only one, but the hair colour from the appearance
# screen works on it (material eq_dragon_hair on the vanilla hair shader, see tools/dragon_material.ps1).
# All hairstyle entries are taken by it, so a "bald" dragon cannot be chosen.
DRAGON_HAIR = ["eq_dragon_hair"]
DRAGON_HAIR_TAG = "DragonCrest"
# The hair shader strongly bleaches light colours, so brightness is kept lower than for the skin,
# but the whole hue circle is covered: horns can be any colour.
DRAGON_HAIR_COLORS = ["%.2f, %.2f, %.2f" % colorsys.hsv_to_rgb(i / 24.0, 0.80, 0.70)
                      for i in range(24)]
# Dragons come in all kinds, so they get not shades of one colour but the whole circle: over the 24 gradient
# points (as many as in the vanilla entry) there is a full pass over hue. Saturation and brightness
# are a little below the maximum: pure computer colour on scales looks poisonous.
DRAGON_PALETTE = ["%.2f, %.2f, %.2f" % colorsys.hsv_to_rgb(i / 24.0, 0.72, 0.92)
                  for i in range(24)]
# Hippogriff (tools/make_hippogriff.py): eagle head with a feather collar, wings from the arms,
# bird feet and a wide fan tail. The model is of the same kind as the griffon's and is split the same way;
# wings and tail are attached to the skeleton by src/EquestriaBodyParts.cs, the crown feathers work as a hairstyle.
# The palette multiplies the model texture (it is brown with gold), so the shades are light: from
# sea green to sand; hippogriffs from Seaquestria come in any colour.
HIPPOGRIFF = "hippogriff"
HIPPOGRIFF_MESHES = {
    "body_meta_mesh": "eq_hippogriff_body",
    "body_meta_mesh_shoulders": "eq_hippogriff_body",
    "legs_mesh": "eq_hippogriff_legs",
    "hands_mesh": "eq_hippogriff_gloves",
    "face_meta_mesh": "eq_hippogriff_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
HIPPOGRIFF_PALETTE = [
    "1.00, 0.98, 0.94",  # the model's own colour
    "0.86, 0.96, 1.00",  # sea green
    "0.94, 0.90, 1.00",  # lilac
    "1.00, 0.92, 0.82",  # sandy
    "0.88, 1.00, 0.94",  # mint
    "1.00, 0.88, 0.90",  # pinkish
    "0.90, 0.94, 1.00",  # light blue
    "0.96, 1.00, 0.86",  # lettuce green
    "0.84, 0.88, 0.92",  # steel
    "1.00, 0.94, 0.72",  # golden
]
HIPPOGRIFF_HAIR = None  # the hippogriff has no separate hairstyle: head and ears are one piece with the head
HIPPOGRIFF_HAIR_TAG = "HippogriffCrest"
HIPPOGRIFF_HAIR_COLORS = [  # crown feathers: from white to dark blue, plus bright sea tones
    "0.94, 0.92, 0.90", "0.62, 0.78, 0.86", "0.32, 0.54, 0.70", "0.18, 0.34, 0.52",
    "0.50, 0.70, 0.62", "0.74, 0.60, 0.78", "0.86, 0.72, 0.52", "0.40, 0.46, 0.56",
    "0.66, 0.34, 0.42", "0.24, 0.46, 0.44", "0.80, 0.84, 0.88", "0.30, 0.28, 0.34",
]
# The qilin race is no longer here: it was a test race on pony meshes, and its realm (Lands of the
# Qilin) became Deerland; our deer have their own model (tools/make_deer_model.py).

# ---------------------------------------------------------------- skins
human = next(r for r in ET.parse(os.path.join(NATIVE, "skins.xml")).getroot() if r.get("id") == "human")


# Real hairstyles (hair slot). On a human the face sliders also move the hair (deforms_hair on face keys),
# and on the pony head this tore any hairstyle to pieces; for our races the hair does not depend on the face
# (checked in game 2026-09-17: with deforms_hair=0 vanilla hairstyles stay intact).
# Chrysalis's mane is tools/make_changeling_hair.py; length variants are separate hairstyles, mirroring is a checkbox.
CHANGELING_HAIR = None  # disabled 05.10.2026: strand manes looked like human hairstyles
HAIR_TAG = "ChangelingMane"  # hairstyle tag: lords and companions get a mane, drones get Bald
# Pony: cartoon manes only: Twilight's mane (tools/make_pony_hair.py) and the styles of tools/make_pony_manes.py.
# Strand manes (like the changelings') look too much like human hairstyles; ponies do not get them.
PONY_HAIR = ["eq_hair_pony_twilight", "eq_hair_pony_straight", "eq_hair_pony_curly", "eq_hair_pony_wild",
             "eq_hair_pony_puffy", "eq_hair_pony_long", "eq_hair_pony_ponytail", "eq_hair_pony_short"]
PONY_HAIR_TAG = "PonyMane"
# Twilight's mane is coloured in the texture and does not depend on the palette. The palette tints the strands
# of the other manes:
# the hair shader strongly bleaches light colours, so they are dark and saturated (like the changelings').
PONY_HAIR_COLORS = [
    "0.45, 0.12, 0.30", "0.20, 0.10, 0.45", "0.10, 0.22, 0.50", "0.55, 0.35, 0.05",
    "0.50, 0.08, 0.10", "0.08, 0.35, 0.18", "0.55, 0.20, 0.05", "0.30, 0.05, 0.40",
    "0.05, 0.35, 0.50", "0.12, 0.10, 0.14", "0.60, 0.50, 0.30", "0.35, 0.18, 0.08",
]
# Mane colour: turquoise, sea green, green and the blue of the hive. List length as for the human (24).
CHANGELING_HAIR_COLORS = [  # the strand texture is light and shiny, so the shades are dark and saturated
    # Exactly 24 colours, all different: the appearance screen draws two rows of 12, and with 12 colours the
    # bottom row repeated the top one. Top: turquoise, sea green, green; bottom: blue, violet, poison.
    "0.06, 0.42, 0.45", "0.04, 0.34, 0.40", "0.08, 0.48, 0.40", "0.03, 0.28, 0.36",
    "0.10, 0.55, 0.52", "0.05, 0.40, 0.30", "0.05, 0.30, 0.52", "0.12, 0.50, 0.62",
    "0.03, 0.22, 0.26", "0.08, 0.40, 0.28", "0.02, 0.18, 0.34", "0.16, 0.62, 0.58",
    "0.10, 0.25, 0.70", "0.20, 0.15, 0.60", "0.35, 0.12, 0.55", "0.55, 0.10, 0.50",
    "0.15, 0.65, 0.20", "0.45, 0.70, 0.10", "0.70, 0.75, 0.15", "0.10, 0.70, 0.75",
    "0.25, 0.40, 0.45", "0.06, 0.12, 0.20", "0.30, 0.55, 0.30", "0.02, 0.45, 0.65",
]


def make_race(race_id, meshes, palette, hair=None, hair_colors=None, hair_tag=HAIR_TAG,
              face_material=None, material=MATERIAL, keep_bald=True):
    race = copy.deepcopy(human)
    race.set("id", race_id)
    for skin in race:
        fill_skin(skin, meshes, palette, hair, hair_colors, hair_tag, face_material, material, keep_bald)
    return race


# Hair follows the face sliders (deforms_hair) only if all the race's hairstyles are built on its head:
# vanilla hairstyles tore on the pony head, and otherwise our own mane passes through the muzzle when the face changes.
OWN_HAIR_FOLLOWS_FACE = True


# The barber shows only hairstyles with the culture tag (BodyPropertiesModel.GetHairIndicesForCulture),
# so the mane has the tags of all cultures. Troops that are not supposed to have a mane get the Bald tag (make_troops.py).
CULTURE_TAGS = ["empire", "battania", "aserai", "sturgia", "vlandia", "khuzait", "nord"]


def fill_hair(parent, names, hair_tag, keep_bald=True):
    """Hairstyles in a cycle; the list length is the human one.

    The first (bald) entry stays by default: it is the "bald" item in the barber's hairstyle
    list. keep_bald=False removes it too; ponies must not have it (ordered 28.09.2026).

    cover_type4 is the same hairstyle: without a helmet and without armour (Equipment.HairCoverType = Type4) the
    engine shows exactly this variant; without it a bare hero was bald. Under type1..3 helmets the mane is hidden.
    """
    children = list(parent)
    start = 1 if keep_bald else 0
    for i, child in enumerate(children[start:], start=start):
        parent.remove(child)
        name = names[(i - start) % len(names)]
        entry = ET.Element("hair_mesh", name=name, cover_type4=name)
        tags = ET.SubElement(entry, "style_tags")
        for tag in [hair_tag] + CULTURE_TAGS:
            ET.SubElement(tags, "style_tag", name=tag)
        parent.insert(i, entry)


def fill_skin(skin, meshes, palette, hair=None, hair_colors=None, hair_tag=HAIR_TAG,
              face_material=None, material=MATERIAL, keep_bald=True):
    for attr, value in meshes.items():
        skin.set(attr, value)
    if not (hair and OWN_HAIR_FOLLOWS_FACE):
        for key in skin.find("deform_keys"):
            if key.get("deforms_hair") is not None:
                key.set("deforms_hair", "0")
    if hair_colors:
        for i, point in enumerate(skin.find("hair_color_gradient_points")):
            point.set("point", hair_colors[i % len(hair_colors)])
    if hair:
        fill_hair(skin.find("hair_meshes"), hair, hair_tag, keep_bald)
    else:
        keep_only_empty(skin.find("hair_meshes"))
    keep_only_empty(skin.find("beard_meshes"))
    # Tattoos stay human: this is a ready channel for cutie marks, and they are used to check
    # whether the pony material responds to engine overlays. Our own cutie marks will replace them later.
    if TATTOO_MATERIALS:
        for i, tattoo in enumerate(skin.find("tattoo_materials")):
            tattoo.set("name", TATTOO_MATERIALS[i % len(TATTOO_MATERIALS)])
    else:
        # without our own overlays the list is empty: human war paint is drawn for the UV layout of the
        # human face and lands on the pony muzzle as crooked blotches
        keep_only_empty(skin.find("tattoo_materials"))
    # Eyebrows stay human: with an empty list the appearance editor crashes when creating a hero.
    # They are placed at a point of the human face; inside the larger pony head they are not visible.
    # the pony head uses the model's shared material instead of the human face skin
    # (as many variants as the human has, with the same tags, for random selection in the editor)
    faces = list(skin.find("face_textures"))
    for i, face in enumerate(faces):
        # the last entry is the race's special face variant (changelings: the queen's green eyes):
        # the engine picks the face material for each character separately (the "face" slider in the
        # appearance editor), so a unique look like Chrysalis does not need its own race.
        # material is the race's head material (the yak has its own eq_yak_body: with the pony atlas the head is motley)
        mat = face_material if face_material and i == len(faces) - 1 else material
        face.set("name", mat)
        face.set("lod_material", mat)
    # Coat palette: the skin colour slider in the character editor picks a point of this gradient, and the engine
    # multiplies the body texture by it. The list length is kept (the engine takes the index from the human
    # range). Works only if the model's material uses the skin shader, like body_female_a.
    points = skin.find("skin_color_gradient_points")
    for i, point in enumerate(points):
        point.set("point", palette[i % len(palette)])


# Until the new pony's FBX is imported (NOT_IMPORTED below), she uses the former Twilight meshes.
# Declared here, before the pony is built, because it is checked right below.
NOT_IMPORTED = set()   # assets/pony/eq_pony.fbx is built, waiting for import: tools/pony_material.ps1 removes it
PONY_WAITING = RACE in NOT_IMPORTED or "--placeholder" in sys.argv
if PONY_WAITING:
    print("pony: меши новой модели ещё не импортированы — пока Twilight")
    # Until the new pony's FBX is imported (NOT_IMPORTED below), she uses the former Twilight meshes.
# Declared here, before the pony is built, because it is checked right below.
NOT_IMPORTED = set()   # assets/pony/eq_pony.fbx is built, waiting for import: tools/pony_material.ps1 removes it
PONY_WAITING = RACE in NOT_IMPORTED or "--placeholder" in sys.argv
if PONY_WAITING:
    print("pony: меши новой модели ещё не импортированы — пока Twilight")
    pony = make_race(RACE, MESHES, COAT_PALETTE,
                     hair=None if "--placeholder" in sys.argv else PONY_HAIR,
                     hair_colors=PONY_HAIR_COLORS, hair_tag=PONY_HAIR_TAG)
else:
    pony = make_race(RACE, PONY_MESHES, PONY_PALETTE, hair=PONY_MANE, hair_colors=PONY_MANE_COLORS,
                     hair_tag=PONY_MANE_TAG, material="eq_pony_body", keep_bald=False)
skins = ET.Element("skins")
skins.append(pony)
# Until a race's meshes are imported in the editor, it uses the pony meshes; otherwise the editor and the game
# stop at «Meta mesh ... cannot be found». Once the FBX is imported, remove the race from this list.
# The --placeholder switch does the same for all races at once (needed after rebuilding all models).
# Races whose meshes are not yet imported in the editor: such a race temporarily uses the pony meshes,
# otherwise the game stops at «Meta mesh ... cannot be found». After the FBX is imported into the Modding Kit
# the race is removed from here and skins are rebuilt; the corresponding *_material.ps1 does that.
PLACEHOLDER = "--placeholder" in sys.argv
for race_id, race_meshes, race_palette, race_hair, race_colors, race_tag in (
        (CHANGELING, CHANGELING_MESHES, CHANGELING_PALETTE, CHANGELING_HAIR, CHANGELING_HAIR_COLORS, HAIR_TAG),
        (DEER, DEER_MESHES, DEER_PALETTE, DEER_HAIR, DEER_HAIR_COLORS, DEER_HAIR_TAG),
        (GRIFFON, GRIFFON_MESHES, GRIFFON_PALETTE, GRIFFON_HAIR, GRIFFON_HAIR_COLORS, GRIFFON_HAIR_TAG),
        (YAK, YAK_MESHES, YAK_PALETTE, YAK_HAIR, YAK_HAIR_COLORS, YAK_HAIR_TAG),
        (DRAGON, DRAGON_MESHES, DRAGON_PALETTE, DRAGON_HAIR, DRAGON_HAIR_COLORS, DRAGON_HAIR_TAG),
        (HIPPOGRIFF, HIPPOGRIFF_MESHES, HIPPOGRIFF_PALETTE, HIPPOGRIFF_HAIR, HIPPOGRIFF_HAIR_COLORS, HIPPOGRIFF_HAIR_TAG)):
    waiting = PLACEHOLDER or race_id in NOT_IMPORTED
    if waiting:
        print(f"{race_id}: меши ещё не импортированы — временно меши пони")
    skins.append(make_race(race_id, MESHES if waiting else race_meshes, race_palette,
                           hair=None if waiting else race_hair, hair_colors=race_colors, hair_tag=race_tag,
                           face_material=None if waiting or race_id != CHANGELING else CHANGELING_QUEEN_FACE,
                           material=MATERIAL if waiting else RACE_MATERIAL.get(race_id, MATERIAL)))
write(skins, "pony_skins.xml")

# ---------------------------------------------------------------- monsters
native_monsters = {m.get("id"): m for m in ET.parse(os.path.join(NATIVE, "monsters.xml")).getroot().iter("Monster")}
monsters = ET.Element("Monsters")
for race_id in (RACE, CHANGELING, DEER, GRIFFON, YAK, DRAGON, HIPPOGRIFF):
    # Copy the vanilla human ENTIRELY instead of inheriting with one line via base_monster:
    # bone names are not carried over by inheritance.
    #
    # THE MOVEMENT SET STAYS VANILLA (as_human_*); our as_pony_* is not given to the monsters.
    # Reason: the engine looks up the monster's bones THROUGH THE SKELETON OF ITS SET (Monster.DeserializeBoneIndex →
    # GetBoneIndexWithId(ActionSetCode, name)), and with our sets all bones came out -1, silently.
    # The engine then passes this -1 to fitting the helmet to the head, and the helmet flew up a full body height;
    # gaze direction, foot IK and ragdoll bones were dead too.
    # And our 88 sets are empty copies: not a single animation inside, only base_set="as_human_*".
    # So the layer gave nothing but broke bone resolution. When real pony animations
    # appear, the set can be brought back, but then check that the bones are still found.
    main = copy.deepcopy(native_monsters["human"])
    main.set("id", race_id)
    monsters.append(main)
    for suffix in ("_child", "_settlement", "_settlement_slow", "_settlement_fast"):
        m = copy.deepcopy(native_monsters["human" + suffix])
        m.set("id", race_id + suffix)
        m.set("base_monster", m.get("base_monster").replace("human", race_id, 1))
        monsters.append(m)      # the movement set is vanilla too, see above
write(monsters, "pony_monsters.xml")

# ---------------------------------------------------------------- action sets
# Skeleton and movement set are NOT WRITTEN. They used to be on every set: without them the monster's
# bones came out -1, which broke helmet fitting, gaze direction, foot IK and the
# ragdoll. But what fixed that was not this, but the monster's movement set: now the monsters use
# vanilla as_human_* (see above), and nobody asks for our sets.
# On the other hand, for every such attribute the editor shows the window «skeleton already defined the same in
# base_set for as_pony_warrior»: 88 sets with two windows each, 176 clicks on every launch
# (noticed by the user 24.09.2026). The value comes through the base_set chain anyway.
#
# If the monsters ever need OUR sets again, bring back not the attribute but a full
# set with animations; an empty copy with the attribute only repeats what the parent already has.
native_sets = {a.get("id"): a for a in ET.parse(os.path.join(NATIVE, "action_sets.xml")).getroot().iter("action_set")}
human_sets = [i for i in native_sets if i.startswith("as_human_")]
# The sets file itself is written by tools/make_race_action_sets.py: the sets of ALL races (as_<race>_facegen and
# others) and the flight pose binding act_eq_flight_pose → anim_eq_flight_pose. Previously a
# trimmed file with only as_pony_* was written here, and every *_material.ps1 (they all call this script) silently
# erased the binding: fighters with a scroll in character screens took an attack pose instead of flight
# (noticed by the user 10.10.2026 after yak_material.ps1).
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "make_race_action_sets.py"), GAME_MODULES, MOD],
               check=True)
print(f"{len(pony)} skins, {len(monsters)} monsters, {len(human_sets)} action sets на расу")

# ---------------------------------------------------------------- project.mbproj
project = ET.Element("base", {"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                              "xmlns:xsd": "http://www.w3.org/2001/XMLSchema", "type": "solution"})
for file_id, name, kind in (("soln_soundtrack", "Music/soundtrack.xml", "soundtrack"),
                            ("soln_skins", "ModuleData/pony_skins.xml", "skin"),
                            ("soln_action_sets", "ModuleData/pony_action_sets.xml", "action_set"),
                            ("soln_monsters", "ModuleData/pony_monsters.xml", "monster"),
                            # Doubled blood effects (tools/make_more_blood.py): the same
                            # standard id="soln_particle_systems" as several
                            # vanilla particle_systems_*.xml in Native/project.mbproj: the engine
                            # loads/merges all of them, not just one, unlike action_types.
                            ("soln_particle_systems", "ModuleData/equestria_more_blood.xml",
                             "particle_system"),
                            # act_eq_flight_pose (src/EquestriaFlightScroll.cs): registration of the
                            # action name, see bannerlord-animation-pipeline.md section 7.
                            ("soln_action_types", "ModuleData/action_types.xml", "action_type")):
    ET.SubElement(project, "file", id=file_id, name=name, type=kind)
write(project, "project.mbproj")
