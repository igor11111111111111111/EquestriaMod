# -*- coding: utf-8 -*-
"""Rebuilds ModuleData/pony_action_sets.xml for ALL 7 races at once (as_<race>_* based on
all as_human_* from vanilla Native/ModuleData/action_sets.xml), not only for ponies.

Why: in most game contexts (battle, map) a monster is given action_set="as_human_warrior"
DIRECTLY, and nobody asks for its own as_<race>_* (see the comment in tools/make_pony_race.py,
lines 560-566 — that is also where only as_pony_* was originally generated). BUT in some places
the engine builds the set name itself from the RACE NAME rather than from the monster attribute —
ActionSetCode.GenerateActionSetNameWithSuffix(monster, isFemale, suffix) does
"as_" + monster.StringId + suffix (e.g. suffix="_facegen" for the portraits of the character
creation wizard, CharacterCreationNarrativeStageView.CreateAgentVisual, decompiled ilspycmd). For
ponies the set as_pony_facegen already existed (88 aliases, written by tools/make_pony_race.py),
for the other 6 races it did not exist at all: the engine cannot find the set and falls back to a
garbage/looping animation (noticed 08.10.2026 — an attack pose and a turned body for all races
except ponies in the "Family"/"Childhood"/"Youth" windows of the character
creation wizard with .\run.ps1 -DefaultStart, the first run of the FULL wizard ever — nobody had
gone through it completely before).

Output goes to the same file as tools/make_pony_race.py (registered as id="soln_action_sets"
in project.mbproj — the engine loads only one file per standard id, so the aliases of all
races must live in ONE file, as does the act_eq_flight_pose alias there, see memory
bannerlord-animation-pipeline). This script FULLY overwrites the file (it does not append) —
run it LAST, after tools/make_pony_race.py, if that one is rerun too.

Usage: py tools/make_race_action_sets.py <game Modules folder> <mod Module folder>
"""
import os
import sys
import xml.etree.ElementTree as ET

GAME_MODULES, MOD = sys.argv[1], sys.argv[2]
NATIVE = os.path.join(GAME_MODULES, "Native", "ModuleData")
OUT = os.path.join(MOD, "ModuleData")

RACES = ["pony", "changeling", "deer", "griffon", "yak", "dragon", "hippogriff"]

native_sets = {a.get("id") for a in ET.parse(os.path.join(NATIVE, "action_sets.xml")).getroot().iter("action_set")}
human_sets = sorted(i for i in native_sets if i.startswith("as_human_"))

action_sets = ET.Element("action_sets")

# act_eq_flight_pose: the flight scroll (src/EquestriaFlightScroll.cs). A PARTIAL as_human_warrior
# (not an override, not a full copy — the engine MERGES such a block into the global set) — the same
# as warg/spider in TAOM (docs/features/spider.md: "the FIRST set in action_sets_warg.xml is a
# partial as_human_warrior!"). Monsters of all races use action_set="as_human_warrior" DIRECTLY
# (not as_<race>_warrior — those are empty aliases that we do not give to monsters, see
# tools/make_pony_race.py lines 540-548), so the binding has to go exactly here. See
# bannerlord-animation-pipeline.md section 9. The block is first in the file — same order as TAOM.
flight_pose_set = ET.SubElement(action_sets, "action_set", id="as_human_warrior")
ET.SubElement(flight_pose_set, "action", type="act_eq_flight_pose", animation="anim_eq_flight_pose")

for race in RACES:
    for set_id in human_sets:
        ET.SubElement(action_sets, "action_set",
                      id=set_id.replace("as_human_", f"as_{race}_"), base_set=set_id)

ET.indent(action_sets, space="\t")
out_path = os.path.join(OUT, "pony_action_sets.xml")
ET.ElementTree(action_sets).write(out_path, encoding="utf-8", xml_declaration=True)
print(f"written {out_path}: {len(RACES)} рас x {len(human_sets)} наборов "
      f"= {len(RACES) * len(human_sets)} алиасов")
