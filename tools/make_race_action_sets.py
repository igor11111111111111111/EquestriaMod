# -*- coding: utf-8 -*-
"""Пересобирает ModuleData/pony_action_sets.xml на ВСЕ 7 рас разом (as_<раса>_* на основе
всех as_human_* из ванильного Native/ModuleData/action_sets.xml), а не только на пони.

Зачем: в большинстве игровых контекстов (бой, карта) монстру ставят action_set="as_human_warrior"
НАПРЯМУЮ, и свои as_<раса>_* никто не спрашивает (см. комментарий в tools/make_pony_race.py,
строки 560-566, — там же изначально генерировался только as_pony_*). НО кое-где движок сам
строит имя набора из ИМЕНИ РАСЫ, а не из атрибута монстра —
ActionSetCode.GenerateActionSetNameWithSuffix(monster, isFemale, suffix) делает
"as_" + monster.StringId + suffix (например suffix="_facegen" у портретов мастера создания
персонажа, CharacterCreationNarrativeStageView.CreateAgentVisual, decompiled ilspycmd). Для
пони набор as_pony_facegen уже существовал (88 алиасов, писал tools/make_pony_race.py), для
остальных 6 рас — нет вовсе: движок не находит набор и проваливается в мусорную/зацикленную
анимацию (замечено 08.10.2026 — атакующая поза и разворот тела у всех рас, кроме пони, в окнах
"Семья"/"Детство"/"Юность" мастера создания персонажа при .\run.ps1 -DefaultStart, первом
прогоне ПОЛНОГО мастера в принципе — раньше его никто целиком не проходил).

Запись идёт в тот же файл, что tools/make_pony_race.py (зарегистрирован как id="soln_action_sets"
в project.mbproj — на один стандартный id движок грузит только один файл, поэтому алиасы всех
рас обязаны жить в ОДНОМ файле, как и алиас act_eq_flight_pose там же, см. память
bannerlord-animation-pipeline). Этот скрипт ПОЛНОСТЬЮ перезаписывает файл (а не дописывает) —
запускать ПОСЛЕДНИМ, после tools/make_pony_race.py, если тот тоже перезапускается.

Запуск: py tools/make_race_action_sets.py <папка Modules игры> <папка Module мода>
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

# act_eq_flight_pose: свиток полёта (src/EquestriaFlightScroll.cs). ЧАСТИЧНЫЙ as_human_warrior
# (не override, не полная копия — движок МЕРЖИТ такой блок в глобальный набор) — так же, как у
# warg/spider в TAOM (docs/features/spider.md: "the FIRST set in action_sets_warg.xml is a
# partial as_human_warrior!"). Монстры всех рас используют action_set="as_human_warrior" НАПРЯМУЮ
# (не as_<раса>_warrior — те пустые алиасы, монстрам их не подсовываем, см. tools/make_pony_race.py
# строки 540-548), поэтому связку нужно класть именно сюда. См. bannerlord-animation-pipeline.md
# раздел 9. Блок первый в файле — тот же порядок, что у TAOM.
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
