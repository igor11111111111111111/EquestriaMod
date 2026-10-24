# -*- coding: utf-8 -*-
"""Multiplies the "amount of blood" of the vanilla blood particle effects (psys_game_blood_*) -
the user's request "give 2 times more blood in all parameters" (08.10.2026), then once more
"double the blood splatter particles and the blood on units' bodies" (08.10.2026) - FACTOR is computed from
the ORIGINAL (vanilla) value every time, so the 4.0 below is exactly "double a second time" (it does not
compound on the already doubled value; a rerun reads the clean source again).

Where the blood on normal hits comes from: TaleWorlds.MountAndBlade.DefaultDamageParticleModel (decompiled
with ilspycmd) takes the effect names "psys_game_blood_sword_enter/_inside/_exit" via
ParticleSystemManager.GetRuntimeIdByName - the effects themselves are defined in text XML
(Native/ModuleData/particle_systems_hardcoded_misc1.xml, <particle_effects><effect name="psys_
game_blood_...">), NOT in the binary. project.mbproj registers several files under the same
id="soln_particle_systems" - unlike action_types (where only the file with the standard id wins,
see the bannerlord-animation-pipeline memory), here the engine loads/merges all of them,
so an add-on file of our own with the same effect NAMES is a working way to override.

Which parameters, and why exactly these ("amount of blood", not the shape/physics of the splatter):
  - emission_rate (base/bias)      - how many particles fly out per second
  - max_alive_particle_count       - how many particles are on screen at once (0 = no limit,
                                      *2 does not change it)
  - particle_size (base/bias)      - size of a single particle/splash
  - decal_min_scale, decal_max_scale (a pair of numbers) - size of the puddle decal on the ground/walls
Not touched: the nested <curve> of emission_rate/particle_size (multiplier curves over the emitter's
lifetime, 0..1 - multiplying base already scales the result, touching the curves is pointless and risky),
emitter_life/particle_life (duration - not "amount"), gravity/velocity/damping (shape
and trajectory of the splatter - changing them would mean not "more blood" but "blood behaves differently").

Which effects: psys_game_blood_sword_enter/_inside/_exit (sword on a normal hit, these are what
DefaultDamageParticleModel calls) + psys_game_blood_1..7 (the same "blood" group of names in the same file -
we decided not to find out where exactly the engine calls them, and doubled them too, since they are exported).
particle_systems2.xml (it has the same blood_1..4 once more) is NOT registered in project.mbproj at all -
dead data, not loaded by the game, not touched.

Run: py tools/make_more_blood.py <game Modules folder> <mod Module folder>
"""
import os
import sys
import xml.etree.ElementTree as ET

GAME_MODULES, MOD = sys.argv[1], sys.argv[2]
SRC = os.path.join(GAME_MODULES, "Native", "ModuleData", "particle_systems_hardcoded_misc1.xml")
OUT = os.path.join(MOD, "ModuleData")

FACTOR = 4.0

# An explicit list - after "psys_game_blood_" only what was actually found in the file (sword_enter/
# _inside/_exit plus blood_1..7), not a "starts with psys_game_blood" mask, so as not to catch
# something unfamiliar by name in future game updates.
BLOOD_EFFECTS = {
    "psys_game_blood_sword_enter", "psys_game_blood_sword_inside", "psys_game_blood_sword_exit",
    "psys_game_blood_1", "psys_game_blood_2", "psys_game_blood_3", "psys_game_blood_4",
    "psys_game_blood_5", "psys_game_blood_6", "psys_game_blood_7",
}

# For base/bias parameters (emission_rate, particle_size) - multiply BOTH, so that the spread
# (randomness) stays proportional to the new mean instead of collapsing into a fixed number.
BASE_BIAS_PARAMS = {"emission_rate", "particle_size"}
SCALE_PAIR_PARAMS = {"decal_min_scale", "decal_max_scale"}
COUNT_PARAMS = {"max_alive_particle_count"}


def scale_value(text, factor):
    parts = [p.strip() for p in text.split(",")]
    scaled = [f"{float(p) * factor:.3f}" for p in parts]
    return ", ".join(scaled)


root = ET.parse(SRC).getroot()
found = []
changed = 0
for effect in root.iter("effect"):
    name = effect.get("name")
    if name not in BLOOD_EFFECTS:
        continue
    found.append(name)
    for param in effect.iter("parameter"):
        pname = param.get("name")
        if pname in BASE_BIAS_PARAMS:
            for attr in ("base", "bias"):
                if attr in param.attrib:
                    param.set(attr, f"{float(param.get(attr)) * FACTOR:.3f}")
                    changed += 1
        elif pname in SCALE_PAIR_PARAMS and "value" in param.attrib:
            param.set("value", scale_value(param.get("value"), FACTOR))
            changed += 1
        elif pname in COUNT_PARAMS and "value" in param.attrib:
            count = float(param.get("value"))
            if count > 0:
                param.set("value", str(int(round(count * FACTOR))))
                changed += 1

missing = BLOOD_EFFECTS - set(found)
if missing:
    print("[blood] ВНИМАНИЕ: не нашлись в исходном файле:", ", ".join(sorted(missing)))

out_root = ET.Element("particle_effects")
for effect in root.iter("effect"):
    if effect.get("name") in BLOOD_EFFECTS:
        out_root.append(effect)

ET.indent(out_root, space="\t")
out_path = os.path.join(OUT, "equestria_more_blood.xml")
ET.ElementTree(out_root).write(out_path, encoding="utf-8", xml_declaration=True)
print(f"written {out_path}: {len(found)} эффектов, {changed} параметров умножено на {FACTOR}")
