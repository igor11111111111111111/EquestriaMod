# Каталог брони пони: какие ванильные вещи переделаны и в какой FBX-пакет они входят.
#
# Им пользуются adapt_armor.py (какие меши подгонять) и make_items.py (какие предметы описать).
#
# Пакеты:
#   armor      — первые 20 вещей: по пять лучших имперских в каждом слоте (tools/pick_armor.py).
#                FBX assets/pony_armor/eq_pony_armor.fbx.
#   empire     — вся остальная броня, которую носят войска Эквестрии (ванильное имперское дерево,
#                tools/make_troops.py). FBX assets/pony_armor_empire/eq_pony_armor_empire.fbx.
#   bandits    — броня разбойников, которой нет в первых двух пакетах.
#                FBX assets/pony_armor_bandits/eq_pony_armor_bandits.fbx.
#
# Слот накидки (наплечники, шарфы) не переделываем: у пони в нём хвост.
import os
import re
import xml.etree.ElementTree as ET

GAME = r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"

FILES = {
    "head_armors.xml": ("Head", "head"),
    "body_armors.xml": ("Body", "body"),
    "leg_armors.xml": ("Leg", "legs"),
    "arm_armors.xml": ("Gloves", "hands"),
}
SLOT_MODE = {slot: mode for slot, mode in FILES.values()}

# Первый набор с названиями, подобранными вручную.
ARMOR = {
    "head_armors.xml": [
        ("imperial_goggled_helmet", "Шлем катафракта с окулярами"),
        ("heavy_nasalhelm_over_imperial_mail", "Тяжёлый наносник поверх кольчуги"),
        ("empire_guarded_lord_helmet", "Королевский шлем катафракта"),
        ("ironlame_nasalhelm_over_imperial_mail", "Железный наносник поверх кольчуги"),
        ("ironlame_nasalhelm_over_imperial_coif", "Железный наносник поверх койфа"),
    ],
    "body_armors.xml": [
        ("imperial_scale_armor", "Тяжёлая чешуя поверх кольчуги"),
        ("lamellar_with_scale_skirt", "Ламеллярный доспех с чешуйчатой юбкой"),
        ("imperial_lamellar", "Ламеллярный доспех катафракта"),
        ("empire_plate_vest_armor", "Узорчатый чешуйчатый доспех"),
        ("empire_legion_b", "Узорчатая легионерская чешуя"),
    ],
    "leg_armors.xml": [
        ("plated_strip_boots", "Наборные сапоги"),
        ("decorated_imperial_boots", "Украшенные латные сапоги"),
        ("lamellar_plate_boots", "Ламеллярные латные сапоги"),
        ("strapped_leather_boots", "Кожаные сапоги с ремнями"),
        ("empire_horseman_boots", "Сапоги всадника"),
    ],
    "arm_armors.xml": [
        ("lamellar_plate_gauntlets", "Ламеллярные латные рукавицы"),
        ("plated_strip_gauntlets", "Наборные наручи"),
        ("decorated_imperial_gauntlets", "Украшенные имперские рукавицы"),
        ("reinforced_padded_mitten", "Усиленные стёганые рукавицы"),
        ("lordly_padded_mitten", "Господские стёганые рукавицы"),
    ],
}

PACKS = {
    "armor": "eq_pony_armor",
    "empire": "eq_pony_armor_empire",
    "bandits": "eq_pony_armor_bandits",
    "changeling": "eq_pony_armor_changeling",
}
# пакет -> группа войск из tools/make_troops.py, чью броню он переделывает
PACK_GROUPS = {
    "empire": "Эквестрия",
    "bandits": "разбойники",
    # рой носит асерайское дерево: свои силуэты (халаты, чешуя, тюрбаны) и свои текстуры,
    # перекрашенные в хитин с бирюзой (tools/recolor_armor.py)
    "changeling": "Чейнджлинги",
}

_TAG = re.compile(r"\{[^}]*\}")

# Названия, которые в локализации игры согласованы неверно.
NAME_FIXES = {
    "wolfhead": "Волчья голова",
    "bearhead": "Медвежья голова",
}


def _paths(game):
    base = os.path.join(game or GAME, "Modules", "SandBoxCore", "ModuleData")
    return (os.path.join(base, "items"),
            os.path.join(base, "spnpccharacters.xml"),
            os.path.join(base, "spcultures.xml"),
            os.path.join(base, "Languages", "RU", "std_spitems_xml_rus.xml"))


def _russian(game):
    """id строки -> русский текст без служебных меток {.MI} и вариантов множественного числа.

    Названия предметов разбросаны по нескольким файлам: часть в SandBoxCore (std_spitems),
    часть в Native (std_common_strings). Читаем русские файлы всех модулей.
    """
    modules = os.path.join(game or GAME, "Modules")
    result = {}
    for module in sorted(os.listdir(modules)):
        folder = os.path.join(modules, module, "ModuleData", "Languages", "RU")
        if not os.path.isdir(folder):
            continue
        for filename in sorted(os.listdir(folder)):
            if not filename.endswith(".xml"):
                continue
            try:
                root = ET.parse(os.path.join(folder, filename)).getroot()
            except ET.ParseError:
                continue
            for s in root.iter("string"):
                text = (s.get("text") or "").split("{@PLURAL")[0]
                result.setdefault(s.get("id"), _agree(text))
    return result


# Русские названия в файлах игры размечены для склонения: {.FI}Кожаный{.aj} {.FI}шапка{.nn}.
# Перед словом — род (M/F/N), после — часть речи: aj прилагательное, ajp прилагательное во
# множественном числе. Склоняет их движок; мы пишем готовый текст, поэтому согласуем сами.
_WORD = re.compile(r"\{\.([MFN])\w*\}([^{\s]+)\{\.(ajp|aj|nnp|nn)\}")
_HUSH = "гкхжшщч"


def _adjective(word, gender, plural):
    for ending in ("ый", "ий", "ой"):
        if not word.endswith(ending):
            continue
        stem = word[:-2]
        hard = ending == "ый" or (ending == "ой" and stem[-1:] not in _HUSH) \
            or (ending == "ий" and stem[-1:] in _HUSH)
        if plural:
            return stem + ("ые" if ending == "ый" or (ending == "ой" and stem[-1:] not in _HUSH) else "ие")
        if gender == "F":
            return stem + ("ая" if hard or ending == "ой" else "яя")
        if gender == "N":
            if ending == "ой" or (ending == "ий" and stem[-1:] in "гкх"):
                return stem + "ое"
            return stem + ("ое" if ending == "ый" else "ее")
        return word
    return word


def _agree(text):
    def fix(match):
        gender, word, kind = match.group(1), match.group(2), match.group(3)
        if kind.startswith("aj"):
            return _adjective(word, gender, kind == "ajp")
        return word
    return _TAG.sub("", _WORD.sub(fix, text)).strip()


def _vanilla_items(game):
    """id предмета -> (файл, элемент)"""
    items_dir = _paths(game)[0]
    result = {}
    for filename in FILES:
        for item in ET.parse(os.path.join(items_dir, filename)).getroot().iter("Item"):
            result[item.get("id")] = (filename, item)
    return result


def _troop_items(game, group):
    """Броня войск группы (tools/make_troops.py) в порядке появления."""
    import make_troops  # noqa: E402 — тот же список войск, что и при их сборке
    return make_troops.troop_armor(game)[group]


def pieces(pack, game=None):
    """Список вещей пакета: словари item, file, slot, mode, mesh, name, pony_item, pony_mesh."""
    vanilla = _vanilla_items(game)
    russian = _russian(game)
    first = [(f, item, name) for f, rows in ARMOR.items() for item, name in rows]
    if pack == "armor":
        chosen = first
    elif pack in PACK_GROUPS:
        # Вещи, уже вошедшие в предыдущие пакеты, не повторяем — но только среди пакетов пони.
        # Их у мода больше нет (вся броня пони удалена, расы носят ванильную), поэтому у улья
        # ничего не отнимаем: иначе 23 вещи из 66 оставались ванильными и трутни ходили в
        # песочных халатах рядом с хитиновыми стрелками (видно в игре 25.09.2026).
        taken = set() if pack == "changeling" else {item for _f, item, _n in first}
        for earlier in PACKS:
            if earlier == pack or pack == "changeling":
                break
            if earlier in PACK_GROUPS:
                taken.update(_troop_items(game, PACK_GROUPS[earlier]))
        chosen = []
        for item in _troop_items(game, PACK_GROUPS[pack]):
            if item in taken or item not in vanilla:
                continue
            filename, node = vanilla[item]
            # Шлемы улью не нужны: чейнджлинги их не носят (no_helmet в tools/make_troops.py),
            # а это два десятка лишних текстур по 4–11 МБ на импорт.
            if pack == "changeling" and filename == "head_armors.xml":
                continue
            key = (node.get("name") or "").split("}")[0].lstrip("{=")
            name = russian.get(key) or (node.get("name") or item).split("}")[-1]
            name = NAME_FIXES.get(item, name)
            chosen.append((filename, item, name[:1].upper() + name[1:]))
    else:
        raise ValueError("неизвестный пакет брони: " + pack)

    result = []
    seen_meshes = set()
    for filename, item, name in chosen:
        node = vanilla[item][1]
        slot, mode = FILES[filename]
        mesh = node.get("mesh")
        result.append({
            "item": item, "file": filename, "slot": slot, "mode": mode, "mesh": mesh,
            "name": name, "pony_item": "eq_pony_" + item, "pony_mesh": "eq_pony_" + mesh,
            "new_mesh": mesh not in seen_meshes,
        })
        seen_meshes.add(mesh)
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    for pack in PACKS:
        rows = pieces(pack)
        print(f"== {pack}: {len(rows)} вещей, мешей {len({r['mesh'] for r in rows})}")
        for r in rows:
            print(f"   {r['slot']:6} {r['item']:48} {r['mesh']:40} {r['name']}")
