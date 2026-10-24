# -*- coding: utf-8 -*-
"""Умножает "количество крови" у ванильных эффектов частиц крови (psys_game_blood_*) —
запрос пользователя "выдать в 2 раза больше крови по всем параметрам" (08.10.2026), затем ещё раз
"увеличь в 2 раза частицы брызгов крови и крови на теле юнитов" (08.10.2026) — FACTOR считается от
ПЕРВОНАЧАЛЬНОГО (ванильного) значения каждый раз, поэтому 4.0 ниже и есть "удвоить второй раз" (не
компаундится от уже удвоенного, перезапуск читает чистый исходник заново).

Откуда кровь на обычных ударах: TaleWorlds.MountAndBlade.DefaultDamageParticleModel (decompiled
ilspycmd) берёт имена эффектов "psys_game_blood_sword_enter/_inside/_exit" через
ParticleSystemManager.GetRuntimeIdByName — сами эффекты определены текстовым XML
(Native/ModuleData/particle_systems_hardcoded_misc1.xml, <particle_effects><effect name="psys_
game_blood_...">), НЕ в бинарнике. project.mbproj регистрирует несколько файлов под одним и тем
же id="soln_particle_systems" — в отличие от action_types (где побеждает только файл со
стандартным id, см. память bannerlord-animation-pipeline), здесь движок грузит/мёржит их все,
значит свой файл-довесок с теми же ИМЕНАМИ effect — рабочий путь переопределения.

Какие параметры и почему трогаем именно их ("количество крови", не форма/физика брызг):
  - emission_rate (base/bias)      — сколько частиц в секунду вылетает
  - max_alive_particle_count       — сколько частиц одновременно на экране (0 = без лимита,
                                      *2 не меняет)
  - particle_size (base/bias)      — размер отдельной частицы/брызги
  - decal_min_scale, decal_max_scale (пара чисел) — размер лужи-декали на земле/стенах
Не трогаем: emission_rate/particle_size вложенные <curve> (кривые-множители по времени жизни
эмиттера, 0..1 — умножение base уже масштабирует итог, трогать кривые незачем и рискованно),
emitter_life/particle_life (длительность — не "количество"), gravity/velocity/damping (форма
и траектория брызг — поменять это значило бы не "больше крови", а "кровь ведёт себя иначе").

Какие эффекты: psys_game_blood_sword_enter/_inside/_exit (меч на обычный удар, их и зовёт
DefaultDamageParticleModel) + psys_game_blood_1..7 (та же "кровавая" группа имён в том же файле —
решили не выяснять, где именно их зовут движок, и удвоить заодно, раз уж экспортируются).
particle_systems2.xml (там те же blood_1..4 ещё раз) НЕ регистрирован в project.mbproj вообще —
мёртвые данные, не грузится игрой, не трогаем.

Запуск: py tools/make_more_blood.py <папка Modules игры> <папка Module мода>
"""
import os
import sys
import xml.etree.ElementTree as ET

GAME_MODULES, MOD = sys.argv[1], sys.argv[2]
SRC = os.path.join(GAME_MODULES, "Native", "ModuleData", "particle_systems_hardcoded_misc1.xml")
OUT = os.path.join(MOD, "ModuleData")

FACTOR = 4.0

# Явный список — после "psys_game_blood_" только то, что реально нашли в файле (sword_enter/
# _inside/_exit плюс blood_1..7), не маска "начинается с psys_game_blood", чтобы не зацепить
# что-то незнакомое по имени при будущих обновлениях игры.
BLOOD_EFFECTS = {
    "psys_game_blood_sword_enter", "psys_game_blood_sword_inside", "psys_game_blood_sword_exit",
    "psys_game_blood_1", "psys_game_blood_2", "psys_game_blood_3", "psys_game_blood_4",
    "psys_game_blood_5", "psys_game_blood_6", "psys_game_blood_7",
}

# Для base/bias-параметров (emission_rate, particle_size) — умножаем ОБА, чтобы разброс
# (случайность) оставался пропорционален новому среднему, а не схлопывался в фиксированное число.
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
