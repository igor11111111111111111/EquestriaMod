# Собирает все XML кампании из таблицы world_data.py: культуры, королевства, кланы, лордов,
# их семьи, поселения и шаблоны снаряжения. Плюс преобразования XSLT, которые вычищают ванильные
# записи ДО того, как подмешаются наши.
#
#   python make_world.py <папка Module мода>
#
# Про XSLT: игра применяет <имя нашего файла>.xslt к уже собранному документу этого типа прямо
# перед тем, как добавить наш файл (MBObjectManager.CreateMergedXmlFile). Пустой шаблон означает
# «удалить». Так The Old Realms убирает ванильные расы и культуры.
# ПОСЛЕ этого скрипта запускать tools/replace_mounts.py: кони в слоте Horse → свитки полёта по уровню (10.10.2026).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_data import (FACE_KEYS, FORT_NAMES, HERO_GEAR, KINGDOMS, ALL_KINGDOMS, DROP_KINGDOMS,  # noqa: E402
                        SPARE_CULTURES, MAP_SIZE, NAMES, COMPANION_TITLES, MINOR_CLANS, MINOR_SHORT,
                        SETTLEMENT_BASE, CITY_VALUE, CITY_MOVE, RENAMES, MINOR_HOMES,
                        CANON_COMPANIONS, DIPLOMACY)
import equus_map  # noqa: E402
import lang  # noqa: E402
import settlement_visuals  # noqa: E402

import xml.etree.ElementTree as ET

MOD = sys.argv[1]
GAME = sys.argv[2] if len(sys.argv) > 2 else \
    r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
DATA = os.path.join(MOD, "ModuleData")
VANILLA = os.path.join(GAME, "Modules", "SandBox", "ModuleData")
# Ванильные «доноры» внешнего вида поселений: по ним ставим ворота (см. settlement_visuals.py)
DONORS = settlement_visuals.load_donors(GAME)

# ---------------------------------------------------------------- знамёна
# Ключ знамени — это два слоя по десять чисел: фон и эмблема.
#   значок . цвет . цвет2 . ширина . высота . X . Y . обводка . зеркало . поворот
# Свои значки рисовать пока нечем, поэтому берём ванильные эмблемы (у каждого королевства своя)
# и перекрашиваем в цвета державы. Цвет задаётся НОМЕРОМ из палитры banner_icons.xml, а не
# шестнадцатеричным кодом, — поэтому подбираем ближайший из 229 доступных.
BANNER_PATTERN = 11          # фон-подложка, общая для всех
KINGDOM_EMBLEMS = [163, 160, 462, 461, 463]   # по эмблеме на державу, в порядке KINGDOMS
CLAN_PATTERNS = [3, 7, 22, 30, 17]            # клан отличается от королевства подложкой

_PALETTE = None

# Культуры без своих сцен и моделей в игре берут их у ванильной (см. settlement_visuals.DONOR_CULTURE)
DONOR_CULTURE = settlement_visuals.DONOR_CULTURE


def donor_culture(culture):
    return DONOR_CULTURE.get(culture, culture)


def unique_cultures():
    """Культуры держав без повторов, в порядке KINGDOMS (у четырёх Эквестрий она одна)."""
    out = []
    for k in KINGDOMS:
        if k["culture"] not in out:
            out.append(k["culture"])
    return out


def palette():
    """Номер цвета -> (r, g, b) из палитры знамён игры."""
    global _PALETTE
    if _PALETTE is None:
        path = os.path.join(GAME, "Modules", "Native", "ModuleData", "banner_icons.xml")
        data = ET.parse(path).getroot().find("BannerIconData").find("BannerColors")
        _PALETTE = {}
        for entry in data:
            value = int((entry.get("hex") or "0xff000000")[-6:], 16)
            _PALETTE[int(entry.get("id"))] = (value >> 16, (value >> 8) & 255, value & 255)
    return _PALETTE


def nearest_color(hex_argb):
    """Ближайший номер из палитры к нашему цвету вида FF9B59B6."""
    value = int(hex_argb[-6:], 16)
    want = (value >> 16, (value >> 8) & 255, value & 255)
    return min(palette(), key=lambda i: sum((a - b) ** 2 for a, b in zip(palette()[i], want)))


def kingdom_emblem(kingdom):
    """Значок державы: из таблицы, иначе ванильная эмблема по порядку."""
    return kingdom.get("emblem", KINGDOM_EMBLEMS[ALL_KINGDOMS.index(kingdom) % len(KINGDOM_EMBLEMS)])


def banner_key(color, color2, emblem, pattern=BANNER_PATTERN):
    back = nearest_color(color)
    front = nearest_color(color2)
    return ("%d.%d.%d.4345.4345.764.764.1.0.0.%d.%d.%d.512.512.764.764.1.0.0"
            % (pattern, back, back, emblem, front, front))

# Снаряжение по культурам пока общее — ванильная имперская броня. Разойдётся, когда у держав
# появятся свои вещи. По пять вещей в слоте, каждой державе своя — так пять армий отличаются
# на вид, пока у них нет собственных моделей.
# Раньше здесь стояли пони-версии (eq_pony_*): броня шилась на тело пони. Теперь все расы
# подогнаны под ванильного человека и носят обычные вещи игры (решено 24.09.2026).
ARMOR_SETS = {
    "helmet": ["empire_guarded_lord_helmet", "imperial_goggled_helmet",
               "heavy_nasalhelm_over_imperial_mail",
               "ironlame_nasalhelm_over_imperial_mail",
               "ironlame_nasalhelm_over_imperial_coif"],
    "body": ["empire_plate_vest_armor", "imperial_scale_armor",
             "lamellar_with_scale_skirt", "imperial_lamellar",
             "empire_legion_b"],
    "gloves": ["decorated_imperial_gauntlets", "lamellar_plate_gauntlets",
               "plated_strip_gauntlets", "reinforced_padded_mitten",
               "lordly_padded_mitten"],
    "leg": ["decorated_imperial_boots", "lamellar_plate_boots",
            "plated_strip_boots", "empire_horseman_boots",
            "strapped_leather_boots"],
}

# Своя броня у культуры: улью — асерайские силуэты, остальным культурам достаётся имперский
# набор из ARMOR_SETS. Слот шлема у чейнджлингов занят рогом (RACE_GEAR), поэтому здесь его
# не трогаем. Перекраска в хитин (tools/recolor_armor.py) жила на пони-мешах и ушла вместе
# с ними — остались ванильные асерайские вещи, силуэт тот же.
CULTURE_GEAR = {
    "aserai": {
        "body": "Item.aserai_full_scale_armor_on_chain",
        "gloves": "Item.eastern_plated_leather_vambraces",
        "leg": "Item.strapped_mail_chausses",
    },
}

GEAR_COMMON = {
    "sword": "Item.empire_sword_4_t4",
    "shield": "Item.stronger_reinforced_kite_shield",
    "horse": "Item.empire_horse",
    # у пони рог — часть причёски (tools/make_pony_manes.py), в слоте шлема ничего не нужно;
    # строки со слотом None выбрасываются при записи файла
    "mane": None,
    # хвост и крылья — части тела: их вешает код (src/EquestriaBodyParts.cs), а слот плаща
    # остаётся свободным под настоящие плащи
    "tail": None,
}


# Раса по культуре; кто не указан — пони. Чейнджлинги — своя раса (tools/make_pony_race.py,
# модель tools/make_changeling.py).
# У остальных нелошадиных культур раса пока проверочная: меши пони со своим окрасом
# (tools/make_pony_race.py). Своя раса есть у каждой культуры, кроме Эквестрии, — иначе в игре
# грифон, дракон и олень неотличимы от пони.
RACE_BY_CULTURE = {"aserai": "changeling", "vlandia": "griffon", "khuzait": "yak",
                   "sturgia": "dragon", "battania": "hippogriff", "nord": "deer"}
# Части тела-предметы расы. У чейнджлингов раньше в слоте шлема сидел предмет-рог
# (eq_changeling_horn): на старой модели рога не было, его надевали. У новой модели
# (tools/make_changeling_model.py) рог и уши — часть головы, а крылья с хвостом вешает на скелет
# src/EquestriaBodyParts.cs. Предмета-рога больше нет, поэтому слот шлема пуст — и чейнджлинги,
# включая Кризалис, носят обычный шлем своей державы.
RACE_GEAR = {
    "changeling": {"tail": None},
}
# Теги причёсок для знати расы (style_tag в skins.xml, tools/make_pony_race.py)
RACE_HAIR_TAGS = {"changeling": "ChangelingMane", "pony": "PonyMane"}
# У грифонов и яков своих причёсок нет: гребень и косички — часть головы


def race_for(culture):
    return RACE_BY_CULTURE.get(culture, "pony")


def face_xml(hero_id, age):
    """Лицо героя: обычно шаблон, а у героев из FACE_KEYS — снятый в редакторе ключ.

    Вариант лица расы (face_textures в skins.xml — у чейнджлингов зелёные глаза королевы) тегом
    в XML не задаётся, он лежит внутри ключа. Ключ снимается в редакторе внешности: мод пишет его
    в журнал (EquestriaShowcase.WatchBodyProperties), оттуда — в world_data.FACE_KEYS.
    """
    key = FACE_KEYS.get(hero_id)
    if not key:
        return '\t\t\t<face_key_template value="BodyProperty.fighter_empire_tall"/>\n'
    return ('\t\t\t<BodyProperties version="4" age="%d" weight="0.5355" build="0.5015" key="%s"/>\n'
            % (age, key))


def hair_tags_xml(culture):
    tag = RACE_HAIR_TAGS.get(race_for(culture))
    if not tag:
        return ""
    return '\t\t\t<hair_tags><hair_tag name="%s"/></hair_tags>\n' % tag


def gear_for(culture):
    """Набор снаряжения державы: общее оружие плюс своя броня."""
    index = unique_cultures().index(culture)
    out = dict(GEAR_COMMON)
    for slot, ids in ARMOR_SETS.items():
        out[slot] = "Item." + ids[index % len(ids)]
    out.update(CULTURE_GEAR.get(culture, {}))
    out.update(RACE_GEAR.get(race_for(culture), {}))
    return out


def log(*a):
    print("[world]", *a, flush=True)


def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def write(name, body, comment):
    # слоты без предмета (например, свободная голова у пони) выпадают из файла
    body = "\n".join(line for line in body.split("\n") if 'id="None"' not in line)
    path = os.path.join(DATA, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write("<!-- %s\n     Файл собран tools/make_world.py из tools/world_data.py — правьте таблицу, не его. -->\n"
                % comment)
        f.write(body)
    log("записан", name)


def write_file(name, text):
    path = os.path.join(DATA, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    log("записан", name)


def write_xslt(name, matches, comment):
    """Преобразование, удаляющее перечисленные узлы из ванильных данных."""
    lines = ['<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">',
             "  <!-- %s -->" % comment,
             "  <xsl:template match=\"@*|node()\">",
             "    <xsl:copy><xsl:apply-templates select=\"@*|node()\"/></xsl:copy>",
             "  </xsl:template>"]
    for match in matches:
        lines.append('  <xsl:template match="%s"/>' % match)
    lines.append("</xsl:stylesheet>")
    path = os.path.join(DATA, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write("\n".join(lines) + "\n")
    log("записан", name)


# ---------------------------------------------------------------- координаты
# Где что стоит, считает tools/world_layout.py: он делит сушу между державами (примерно поровну,
# с поправкой на силу — "power" в world_data.py) и расставляет поселения так, чтобы они не
# кучковались и не оставляли пустых мест — как в оригинальной кампании.
#
# Здесь остаётся только «человеческая» часть: имена, описания и идентификаторы. Точка берётся у
# города Equestria at War, если он попал в эти земли; если город достался чужой державе — имя ему
# даётся в её духе, а канонные названия (Кантерлот, Понивилль и прочие) не трогаются никогда.
HIDEOUT_GAP = 12.0

# Названия добавочных деревень: прилагательное + существительное мужского рода.
VILLAGE_WORDS = {
    "empire": ["Клеверный", "Медовый", "Солнечный", "Яблочный", "Росистый", "Радужный", "Тихий",
               "Ясный", "Звёздный", "Ромашковый", "Пряничный", "Лунный"],
    "aserai": ["Хитиновый", "Сумрачный", "Жужжащий", "Пустой", "Тёмный", "Кислый", "Зелёный",
               "Смоляной", "Мёртвый", "Тихий", "Чёрный", "Коконный"],
    "battania": ["Приливный", "Коралловый", "Жемчужный", "Туманный", "Перьевой", "Морской", "Бирюзовый",
                 "Солёный", "Раковинный", "Ветреный", "Серебряный", "Небесный"],
    "sturgia": ["Угольный", "Пепельный", "Огненный", "Дымный", "Серный", "Лавовый", "Каменный",
                "Жаркий", "Чешуйчатый", "Рубиновый", "Обсидиановый", "Вулканический"],
    "khuzait": ["Ячий", "Снежный", "Ледяной", "Громовой", "Каменный", "Мшистый", "Горный",
                "Буйный", "Рогатый", "Белый", "Суровый", "Высокий"],
    "vlandia": ["Грифоний", "Орлиный", "Золотой", "Скалистый", "Горный", "Каменный", "Ледовый",
                "Пограничный", "Перьевой", "Вольный", "Ветреный", "Когтистый"],
    "nord": ["Огненный", "Осенний", "Тихий", "Кленовый", "Туманный", "Горный", "Янтарный",
             "Дымный", "Цветущий", "Молчаливый", "Сияющий", "Рыжий"],
}
VILLAGE_NOUNS = ["Луг", "Ручей", "Холм", "Брод", "Дол", "Бор", "Яр", "Хутор", "Родник", "Выселок"]

# Описания известных городов; остальным пишется общее по области.
TEXTS = {
    "Кантерлот": "Столица Солнечной Эквестрии, белокаменный город на склоне горы.",
    "Мейнхеттен": "Город, который не спит.",
    "Филлидельфия": "Старая столица торговли и законов.",
    "Лас-Пегасус": "Город ночных огней, столица Лунной Эквестрии.",
    "Балтимейр": "Портовый город на восточном побережье.",
    "Ванхувер": "Порт среди хвойных лесов.",
    "Понивилль": "Тихий городок с Замком Дружбы — столица Эквестрии Дружбы.",
    "Клаудсдейл": "Город пегасов на облаках, где делают погоду.",
    "Кристальный Город": "Бьющееся сердце Кристальной Империи, хранящее Кристальное Сердце.",
    "Кристальный Пик": "Северная твердыня Кристальной Империи.",
    "Яктаун": "Столица яков под ледником.",
    "Сайхан Толгод": "Старая ставка горных яков.",
    "Весалиполис": "Столица ульев чейнджлингов.",
    "Дитрисиум": "Белый порт чейнджлингов.",
    "Гора Арис": "Столица гиппогрифов, парящая над морем гора.",
    "Сиквестрия": "Подводный город морских пони.",
    "Оленья Роща": "Столица Олении: дубовые чертоги над озером.",
    "Логово Лорда Драконов": "Вулканическое логово, где лорд драконов держит Скипетр.",
    "Вулкан Состязания": "Вулкан, где драконы бьются за титул лорда.",
    "Грифонстоун": "Столица грифонов, где снова хранится Идол Бориаса.",
    "Ледяной Порт": "Северная гавань яков среди льдов.",
    "Наш Городок": "Деревня «равных», где когда-то все носили одинаковые метки.",
}

KIND_TEXT = {"town": "Город", "castle": "Крепость", "village": "Деревня"}
KIND_TEXT_EN = {"town": "Town", "castle": "Castle", "village": "Village"}


def kind_by_value(value):
    if value >= TOWN_VALUE:
        return "town"
    if value >= CASTLE_VALUE:
        return "castle"
    return "village"


def _group(kind):
    return "village" if kind == "village" else "fort"


_LAYOUT = None

# Канонные названия, которые не переименовываются, даже если город достался другой державе.
CANON_NAMES = set(TEXTS) | set(RENAMES.values())
FORT_NOUNS = ["Кряж", "Утёс", "Застава", "Твердыня", "Перевал", "Оплот"]


def _pick_name(pool, used):
    for name in pool:
        if name not in used:
            used.add(name)
            return name
    return None


def fort_name(culture, used):
    """Имя для придуманной или переименованной крепости."""
    name = _pick_name(FORT_NAMES.get(culture, []), used)
    if name:
        return name
    return _pick_name(["%s %s" % (word, noun) for noun in FORT_NOUNS
                       for word in VILLAGE_WORDS[culture]], used)


def village_name(culture, used, rng):
    names = ["%s %s" % (word, noun) for word in VILLAGE_WORDS[culture] for noun in VILLAGE_NOUNS]
    rng.shuffle(names)
    return _pick_name(names, used) or _pick_name(
        ["%s %s %d" % (word, noun, n) for n in range(2, 9)
         for word in VILLAGE_WORDS[culture] for noun in VILLAGE_NOUNS], used)


def layout():
    """{id державы: {"town": [...], "castle": [...], "village": [...]}}, запись поселения —
    словарь: name, text, x, y, eaw (страна EaW), value, sid, bound (у деревни — sid крепости)."""
    global _LAYOUT
    if _LAYOUT is not None:
        return _LAYOUT
    import random

    import world_layout

    rng = random.Random(20260918)
    # Вес города решает, станет он городом, замком или деревней. У канонных мест MLP вес на карте
    # EaW бывает случайно мал (Клаудсдейл — 10), поэтому поднимаем его по таблице CITY_VALUE.
    cities = []
    for c in equus_map.cities():
        x, y = CITY_MOVE.get(c["name"], (c["x"], c["y"]))
        cities.append(dict(c, value=CITY_VALUE.get(c["name"], c["value"]), x=x, y=y))
    by_name = {c["name"]: c for c in cities}

    kings = []
    for k in KINGDOMS:
        cap = by_name.get(k["capital"])
        if cap is None:
            log("столица «%s» (%s) не найдена среди городов карты" % (k["capital"], k["kingdom"]))
        anchors = []
        for name in k.get("anchors", []):
            spot = by_name.get(name)
            if spot is None:
                log("опорный город «%s» державы %s не найден на карте" % (name, k["kingdom"]))
            else:
                anchors.append((spot["x"], spot["y"]))
        kings.append({"kingdom": k["kingdom"], "capital": k["capital"], "anchors": anchors,
                      "anchor_names": list(k.get("anchors", [])),
                      "capital_xy": (cap["x"], cap["y"]) if cap else (MAP_SIZE / 2, MAP_SIZE / 2)})

    spots = world_layout.plan(kings, cities, [k["power"] for k in KINGDOMS],
                              SETTLEMENT_BASE, log, pinned=set(CITY_MOVE))

    used_names = set()
    counters = {}

    def next_id(kind, culture):
        n = counters.get((kind, culture), 0)
        counters[(kind, culture)] = n + 1
        return "%s_%s_%d" % (kind, culture, n)

    result = {}
    for k in KINGDOMS:
        kid, culture = k["kingdom"], k["culture"]
        out = {"town": [], "castle": [], "village": []}
        renamed = invented = 0
        for kind in ("town", "castle", "village"):
            for entry in spots[kid][kind]:
                city = entry["city"]
                name = None
                if city is not None:
                    name = RENAMES.get(city["name"], city["name"])
                    if name in used_names:
                        name = None
                    elif city["owner"] not in k["eaw"] and name not in CANON_NAMES:
                        name = None            # земля сменила хозяина — и название вместе с ней
                        renamed += 1
                if name is None:
                    name = (fort_name(culture, used_names) if kind != "village"
                            else village_name(culture, used_names, rng))
                    if city is None:
                        invented += 1
                used_names.add(name)
                state = (city.get("state") or "") if city else ""
                text = TEXTS.get(name) or (TEXTS.get(city["name"]) if city else None)
                text_en = None
                if text is None:
                    # Описание собирается шаблоном, поэтому английский складываем рядом:
                    # переводить по словарю готовое предложение — гадание (tools/lang.py)
                    if (state and city and name == RENAMES.get(city["name"], city["name"])):
                        text = "%s в области «%s»." % (KIND_TEXT[kind], state)
                        text_en = "%s in the %s region." % (KIND_TEXT_EN[kind], lang.en(state))
                    else:
                        text = "%s державы «%s»." % (KIND_TEXT[kind], k["short"])
                        text_en = "%s of %s." % (KIND_TEXT_EN[kind], lang.en(k["short"]))
                record = {"name": name, "text": text, "text_en": text_en,
                          "x": entry["x"], "y": entry["y"],
                          "eaw": city["owner"] if city else "",
                          "value": city["value"] if city else 0.0,
                          "sid": next_id(kind, culture)}
                if kind == "village":
                    record["bound_ref"] = entry["bound"]
                out[kind].append(record)
        result[kid] = out
        log("%s: городов %d, замков %d, деревень %d (придумано %d, переименовано %d)"
            % (k["name"], len(out["town"]), len(out["castle"]), len(out["village"]),
               invented, renamed))

    # деревню привязываем к её крепости уже по идентификаторам
    for k in KINGDOMS:
        out = result[k["kingdom"]]
        forts = {("town", i): t["sid"] for i, t in enumerate(out["town"])}
        forts.update({("castle", i): c["sid"] for i, c in enumerate(out["castle"])})
        for village in out["village"]:
            village["bound"] = forts[village.pop("bound_ref")]

    taken = [(e["x"], e["y"], "village" if kind == "village" else "fort")
             for kid in result for kind in ("town", "castle", "village") for e in result[kid][kind]]
    result["hideouts"] = place_hideouts(rng, taken)
    _LAYOUT = result
    return result


HIDEOUT_TERRAIN = {
    "forest": (equus_map.FOREST, equus_map.SWAMP),
    "mountain": (equus_map.MOUNTAIN, equus_map.STEPPE),
    "desert": (equus_map.DESERT,),
    "steppe": (equus_map.STEPPE, equus_map.PLAIN),
    "seaside": None,  # у самой воды
}


def place_hideouts(rng, taken):
    import numpy as np
    ids = []
    for node in ET.parse(os.path.join(VANILLA, "settlements.xml")).getroot():
        comp = node.find("Components")
        if comp is not None and comp.find("Hideout") is not None:
            ids.append((node.get("id"), node.get("name")))
    terrain = equus_map.terrain_map()
    size = terrain.shape[0]
    water = np.isin(terrain, (equus_map.WATER, equus_map.LAKE))
    near_water = water.copy()
    for shift in (-12, 12):
        near_water |= np.roll(water, shift, 0) | np.roll(water, shift, 1)
    out = {}
    spots = []
    for hid, name in ids:
        kind = hid.split("_")[1] if "_" in hid else "forest"
        wanted = HIDEOUT_TERRAIN.get(kind, (equus_map.FOREST,))
        for attempt in range(4000):
            j, i = rng.randrange(size), rng.randrange(size)
            t = int(terrain[j, i])
            relaxed = attempt > 2000
            if wanted is None:
                ok = near_water[j, i] and not water[j, i]
            else:
                ok = t in wanted
            if not ok and not relaxed:
                continue
            x, y = i / (size - 1) * MAP_SIZE, j / (size - 1) * MAP_SIZE
            if not (15 < x < MAP_SIZE - 15 and 15 < y < MAP_SIZE - 15):
                continue
            if not equus_map.solid_ground(x, y, 3.0):
                continue
            if any((x - px) ** 2 + (y - py) ** 2 < HIDEOUT_GAP ** 2 for px, py, _g in taken):
                continue
            if any((x - px) ** 2 + (y - py) ** 2 < HIDEOUT_GAP ** 2 for px, py in spots):
                continue
            spots.append((x, y))
            out[hid] = (name, round(x, 1), round(y, 1))
            break
        else:
            raise SystemExit("не нашлось места для логова " + hid)
    log("логовищ расставлено по местности:", len(out))
    return out


def fief_owners(kingdom):
    """{id крепости: id клана}. Столица — правящему клану, крепости стран из eaw_clans — этим
    кланам, остальные — всем кланам по кругу."""
    spots = layout()[kingdom["kingdom"]]
    clans = [c["id"] for c in kingdom["clans"]]
    ruling = next(c["id"] for c in kingdom["clans"] if c.get("ruling"))
    special = kingdom.get("eaw_clans", {})
    owners = {}
    turn = {tag: 0 for tag in special}
    pick = 0
    for kind in ("town", "castle"):
        for i, fort in enumerate(spots[kind]):
            fid = fort["sid"]
            if kind == "town" and i == 0:
                owners[fid] = ruling
            elif fort["eaw"] in special:
                group = special[fort["eaw"]]
                owners[fid] = group[turn[fort["eaw"]] % len(group)]
                turn[fort["eaw"]] += 1
            else:
                owners[fid] = clans[pick % len(clans)]
                pick += 1
    return owners


def capital_id(kingdom):
    return layout()[kingdom["kingdom"]]["town"][0]["sid"]


def clan_home(kingdom, clan_id):
    """Дом клана — первое его владение; у безземельного — столица."""
    for fid, owner in fief_owners(kingdom).items():
        if owner == clan_id:
            return fid
    return capital_id(kingdom)


# ---------------------------------------------------------------- имена жителей
def name_list(culture, sex):
    spec = NAMES.get(culture)
    if spec is None:
        # У культуры без своей таблицы (Оления) берём эквестрийские имена.
        spec = NAMES["empire"]
    spec = spec[sex]
    # четвёртый элемент, если есть, — лорные имена целиком, сверх составных
    extras = list(spec[3]) if len(spec) > 3 else []
    if spec[0] == "составное":
        return ["%s %s" % (first, second) for first in spec[1] for second in spec[2]] + extras
    return list(spec[1]) + extras


# ---------------------------------------------------------------- спутники в тавернах
def build_companions():
    """Перекрывает ванильные шаблоны спутников: делает их пони и даёт русские прозвища.

    Игра сама расселяет спутников по тавернам городов, исходя из культуры поселения. Имя она
    подставляет в {FIRSTNAME} из списков культуры, поэтому здесь задаём только прозвище и расу.
    """
    body = ["<NPCCharacters>"]
    total = 0
    templates = {}   # ванильные шаблоны по культуре — с них копируются канонные спутники
    for node in ET.parse(os.path.join(VANILLA, "spspecialcharacters.xml")).getroot():
        if node.get("occupation") != "Wanderer":
            continue
        culture = (node.get("culture") or "").replace("Culture.", "")
        titles = COMPANION_TITLES.get(culture)
        if not titles:
            continue  # культура не наша (Оления) — оставляем как есть
        templates.setdefault(culture, []).append(node)
        cid = node.get("id")
        index = int(cid.rsplit("_", 1)[-1]) if cid.rsplit("_", 1)[-1].isdigit() else total
        title = titles[index % len(titles)]
        # culture обязательна по схеме NPCCharacters.xsd («required attribute 'culture'» в
        # rgl_log) — та же, что у ванильного шаблона
        body.append('\t<NPCCharacter id="%s" race="%s" culture="Culture.%s" name="%s" />'
                    % (cid, race_for(culture), culture,
                       lang.loc(cid + "_name", "{FIRSTNAME} — " + title)))
        total += 1

    # Канонные спутники (world_data.CANON_COMPANIONS): копия ванильного шаблона своей культуры —
    # навыки, снаряжение, черты и лицо остаются, — но имя фиксированное, без {FIRSTNAME}.
    # Игра создаёт спутника из шаблона, и такой шаблон даёт героя ровно с этим именем.
    canon = 0
    body.append("\n\t<!-- канонные спутники: имя фиксированное, шаблон скопирован у ванильного -->")
    for culture, people in CANON_COMPANIONS.items():
        pool = templates.get(culture) or templates.get("empire")
        for i, (hid, name, sex, age) in enumerate(people):
            copy = ET.fromstring(ET.tostring(pool[i % len(pool)]))
            cid = "spc_eq_" + hid
            copy.set("id", cid)
            copy.set("name", lang.loc(cid + "_name", name))
            copy.set("age", str(age))
            copy.set("is_female", "true" if sex == "f" else "false")
            copy.set("culture", "Culture." + culture)
            copy.set("race", race_for(culture))
            body.append("\t" + ET.tostring(copy, encoding="unicode").strip())
            canon += 1
    body.append("</NPCCharacters>\n")
    write("equestria_companions.xml", "\n".join(body),
          "Спутники, которых игрок нанимает в тавернах. Ванильные шаблоны перекрываем по id:\n"
          "     раса пони и русское прозвище, имя игра подставит из списка имён культуры.\n"
          "     Ниже — канонные спутники с фиксированными именами (world_data.CANON_COMPANIONS).")
    log("спутников переделано в пони: %d, канонных добавлено: %d" % (total, canon))


# ---------------------------------------------------------------- культуры
# Названия и описания культур (одна культура может быть у нескольких держав)
CULTURES = {
    "empire": ("Эквестрия", "Пони Эквестрии: земные пони, пегасы и единороги под рукой принцесс-аликорнов."),
    "vlandia": ("Грифоны", "Грифоны Грифонстоуна: гордые, прижимистые, но верные своему слову."),
    "battania": ("Гиппогрифы", "Гиппогрифы горы Арис и морские пони Сиквестрии."),
    "nord": ("Олени", "Олени северных лесов: молчаливые следопыты и упрямые лучники."),
    "sturgia": ("Драконы", "Драконы вулканических земель: сила, сокровища и Состязание за Скипетр."),
    "khuzait": ("Яки", "Яки Якьякистана: громкие, честные и очень любят крушить."),
    "aserai": ("Чейнджлинги", "Чейнджлинги ульев: оборотни, питающиеся чужой любовью."),
}

# Культура, которой в игре почти нет (nord — заготовка без войск и горожан), собирается целиком
# из ванильной культуры-донора: те же войска, горожане, шаблоны знати и турниров.
# Обмен ветками (10.10.2026, tools/make_troops.py ROSTER_OF): культура берёт у донора ВСЕ ссылки —
# войска, ополчение, горожан, шаблоны знати и снаряжения, — а сами записи донора получают нашу
# культуру в make_troops (swap_cultures). Держава, города и лорды при этом остаются своими.
# Летающие грифоны и драконы — конные хузаиты и вландийцы, пешие яки и олени — стургийцы и
# баттанийцы, гиппогрифы — копии стургийской ветки (make_troops.COPY_CULTURE, ссылки
# переводятся на копии).
FULL_CULTURE_FROM = None   # заполняется из make_troops.ROSTER_OF в build_cultures()
# color/color2 пишем свои (culture_colors), ванильные из донора не копируем — иначе задвоятся
CULTURE_SKIP_ATTRS = {"id", "name", "text", "is_main_culture", "faction_banner_key",
                      "color", "color2", "start_point_position_x", "start_point_position_y"}
CULTURE_SKIP_CHILDREN = {"male_names", "female_names", "clan_names"}


def full_culture_parts(cid, donor):
    path = os.path.join(GAME, "Modules", "SandBoxCore", "ModuleData", "spcultures.xml")
    node = next(c for c in ET.parse(path).getroot() if c.get("id") == donor)
    # У культуры, берущей КОПИИ ветки (гиппогрифы), ссылки на записи донора переводим на копии
    # (tools/make_troops.py, copy_map): иначе гора Арис набирала бы ячьи войска и селила ячьих
    # горожан — раса у записи своя, а культура на неё смотрит чужая.
    import make_troops  # noqa: E402 — импорт здесь: модуль тяжёлый и нужен только тут
    swap = {"NPCCharacter." + old: "NPCCharacter." + new
            for old, new in make_troops.copy_map(GAME).items()} \
        if cid == make_troops.COPY_CULTURE else {}

    def retarget(text):
        for old, new in swap.items():
            text = text.replace('"%s"' % old, '"%s"' % new)
        return text

    attrs = "".join('\n\t\t%s="%s"' % (key, esc(retarget('"%s"' % value)[1:-1]))
                    for key, value in node.attrib.items() if key not in CULTURE_SKIP_ATTRS)
    children = [retarget(ET.tostring(child, encoding="unicode").strip()) for child in node
                if child.tag not in CULTURE_SKIP_CHILDREN]
    if swap:
        log("%s: ссылок культуры переведено на копии — %d" % (cid, len(swap)))
    return attrs, children


def culture_colors(cid):
    """Цвета культуры: берём у её державы, иначе ванильные.

    Ими движок красит ткань и канты брони (маска _c у ванильных текстур). Наши культуры заменяют
    ванильные, и без этих двух чисел вся броня в игре выходит белой (проверено 18.09.2026).
    """
    for k in ALL_KINGDOMS:
        if k["culture"] == cid:
            return k["color"], k["color2"]
    path = os.path.join(GAME, "Modules", "SandBoxCore", "ModuleData", "spcultures.xml")
    node = next((c for c in ET.parse(path).getroot() if c.get("id") == cid), None)
    if node is None:
        return "FFFFFFFF", "FFFFFFFF"
    return (node.get("color", "0xffFFFFFF")[2:].upper(), node.get("color2", "0xffFFFFFF")[2:].upper())


# Названия кланов культуры (<clan_names>). По ним движок называет НОВЫЕ кланы: клан игрока при
# создании персонажа (FactionHelper.GenerateClanNameforPlayer), кланы спутников и мятежников.
# Пустой список — NullReferenceException в NameGenerator.GenerateClanName (10.10.2026: культуры,
# собранные из донора, теряли список, и мастер создания персонажа падал на выборе народности).
# Стиль тот же, что у кланов держав (world_fill.CLAN_STYLE): «Дом …», «Род …», «Клан …», «Улей …».
CLAN_NAMES_PER_CULTURE = 30


def clan_name_list(cid):
    import world_fill  # noqa: E402 — нужен только тут
    word, style = world_fill.CLAN_STYLE.get(cid, ("Дом", "pair"))
    spec = world_fill.NAMES.get(cid, world_fill.NAMES["empire"])["m"]
    if style == "surname":
        bodies = list(spec[2])
    elif style == "pair":
        # по диагонали, чтобы первые имена не повторялись подряд: Санни Дэш, Мун Харт, …
        firsts, seconds = list(spec[1]), list(spec[2])
        bodies = ["%s %s" % (firsts[(i + j) % len(firsts)], seconds[i % len(seconds)])
                  for j in range(len(firsts)) for i in range(len(seconds))]
    else:
        bodies = list(spec[1])
    names = []
    for body in bodies:
        name = "%s %s" % (word, body)
        if name not in names:
            names.append(name)
        if len(names) >= CLAN_NAMES_PER_CULTURE:
            break
    return names


def build_cultures():
    global FULL_CULTURE_FROM
    import make_troops  # noqa: E402
    FULL_CULTURE_FROM = dict(make_troops.ROSTER_OF)
    rows = []
    for cid in unique_cultures():
        name, text = CULTURES[cid]
        rows.append((cid, name, text))
    for cid, (name, text) in SPARE_CULTURES.items():
        rows.append((cid, name, text))
    body = ["<Cultures>"]
    for cid, name, text in rows:
        extra_attrs, extra_children = full_culture_parts(cid, FULL_CULTURE_FROM[cid]) if cid in FULL_CULTURE_FROM else ("", [])
        color, color2 = culture_colors(cid)
        body.append('\t<Culture id="%s" name="%s" text="%s"'
                    ' color="0x%s" color2="0x%s"%s>'
                    % (cid, lang.loc("culture_" + cid, name),
                       lang.loc("culture_%s_text" % cid, text), color, color2, extra_attrs))
        for child in extra_children:
            body.append("\t\t" + child.replace("\n", "\n\t\t"))
        for sex, tag in (("m", "male_names"), ("f", "female_names")):
            body.append("\t\t<%s>" % tag)
            for i, person in enumerate(name_list(cid, sex)):
                body.append('\t\t\t<name name="%s" />'
                            % lang.loc("eq_name_%s_%s_%d" % (cid, sex, i), person))
            body.append("\t\t</%s>" % tag)
        body.append("\t\t<clan_names>")
        for i, clan in enumerate(clan_name_list(cid)):
            body.append('\t\t\t<name name="%s" />' % lang.loc("eq_clanname_%s_%d" % (cid, i), clan))
        body.append("\t\t</clan_names>")
        body.append("\t</Culture>")
    body.append("</Cultures>\n")
    write("equestria_cultures.xml", "\n".join(body),
          "Культуры Equus. Занимают ванильные идентификаторы: на них есть жёстко прописанные\n"
          "     ссылки в коде игры (список из шести культур при создании персонажа и прочее).\n"
          "     Меняем названия, описания и списки имён — бойцы и горожане остаются ванильные.")
    # Списки имён у культуры не заменяются слиянием, а дополняются: ванильные имена остались бы
    # рядом с нашими. Поэтому сначала вырезаем их преобразованием, а потом подмешиваем свои.
    write_xslt("equestria_cultures.xslt",
               ["Culture[@id='%s']/%s" % (cid, tag)
                for cid, _n, _t in rows if cid not in FULL_CULTURE_FROM
                for tag in ("male_names", "female_names", "clan_names")]
               # собранная целиком культура: вырезаем все её ванильные списки, иначе они задвоятся
               + ["Culture[@id='%s']/*" % cid for cid in FULL_CULTURE_FROM if cid in unique_cultures()],
               "Вырезаем ванильные списки имён у наших культур — иначе рядом с пони "
               "остались бы кальрадийцы.")


# ---------------------------------------------------------------- королевства
def build_kingdoms():
    body = ["<Kingdoms>"]
    for k in KINGDOMS:
        ruler_clan = next(c for c in k["clans"] if c.get("ruling"))
        ruler = ruler_clan["heroes"][0][0]
        capital = capital_id(k)
        body.append(
            '\t<Kingdom\n'
            '\t\tid="%s"\n'
            '\t\tinitial_home_settlement="Settlement.%s"\n'
            '\t\towner="Hero.eq_%s"\n'
            '\t\tbanner_key="%s"\n'
            '\t\tprimary_banner_color="0x%s"\n'
            '\t\tsecondary_banner_color="0x%s"\n'
            '\t\tcolor="%s"\n'
            '\t\tcolor2="%s"\n'
            '\t\tculture="Culture.%s"\n'
            '\t\tsettlement_banner_mesh="encounter_flag_a"\n'
            '\t\tflag_mesh="info_screen_flags_b"\n'
            '\t\tname="%s"\n'
            '\t\tshort_name="%s"\n'
            '\t\ttitle="%s"\n'
            '\t\truler_title="%s"\n'
            '\t\ttext="%s" />'
            % (k["kingdom"], capital, ruler,
               banner_key(k["color"], k["color2"], kingdom_emblem(k)),
               k["color"].lower(), k["color2"].lower(), k["color"], k["color2"], k["culture"],
               lang.loc(k["kingdom"], k["name"]),
               lang.loc(k["kingdom"] + "_short", k["short"]),
               lang.loc(k["kingdom"] + "_title", k["title"]),
               lang.loc(k["kingdom"] + "_ruler", k["ruler_title"]),
               lang.loc(k["kingdom"] + "_text", k["text"])))
    body.append("</Kingdoms>\n")
    write("equestria_kingdoms.xml", "\n".join(body),
          "Державы Equus. Ванильные королевства убираются преобразованием\n"
          "     equestria_kingdoms.xslt.")
    write_xslt("equestria_kingdoms.xslt",
               ['Kingdom[@id=\'%s\']' % kid for kid in DROP_KINGDOMS]
               # и у выключенных держав тоже: их культуры по-прежнему заняты нами
               + ['Kingdom[@id=\'%s\']' % k["culture"] for k in ALL_KINGDOMS],
               "Убираем ванильные королевства: и лишние, и те, чьи культуры мы заняли "
               "(наши заведены под своими id).")


# ---------------------------------------------------------------- кланы
def build_clans():
    body = ["<Factions>"]
    for k in KINGDOMS:
        for clan in k["clans"]:
            leader = clan["heroes"][0][0]
            home = clan_home(k, clan["id"])
            body.append(
                '\t<Faction\n'
                '\t\tid="%s"\n'
                '\t\tinitial_home_settlement="Settlement.%s"\n'
                '\t\towner="Hero.eq_%s"\n'
                '\t\tis_noble="true"\n'
                '\t\tsuper_faction="Kingdom.%s"\n'
                '\t\tbanner_key="%s"\n'
                '\t\tcolor="%s"\n'
                '\t\tcolor2="%s"\n'
                '\t\tculture="Culture.%s"\n'
                '\t\tsettlement_banner_mesh="encounter_flag_a"\n'
                '\t\tname="%s"\n'
                '\t\tshort_name="%s"\n'
                '\t\ttier="%d" />'
                % (clan["id"], home, leader, k["kingdom"],
                   banner_key(clan.get("color", k["color"]), clan.get("color2", k["color2"]),
                              clan.get("emblem", kingdom_emblem(k)),
                              CLAN_PATTERNS[k["clans"].index(clan) % len(CLAN_PATTERNS)]),
                   clan.get("color", k["color"]), clan.get("color2", k["color2"]), k["culture"],
                   # короткое имя у знатных кланов то же самое: у нас они и так названы коротко,
                   # но без short_name подпись отряда осталась бы пустой
                   lang.loc(clan["id"], clan["name"]), lang.loc(clan["id"], clan["name"]),
                   clan["tier"]))

    # Кланы, которые мы не трогаем (разбойники, наёмники, клан игрока), ссылаются на ванильные
    # поселения — а те удалены. Повисшая ссылка роняет кампанию, поэтому переселяем их к себе:
    # по тому же id слияние перезапишет только этот атрибут. Раздаём по всем городам по кругу —
    # отряды клана появляются у его дома, и когда домом у всех был Кантерлот, у его ворот стояла
    # толпа из двух десятков отрядов, которые тут же сцеплялись друг с другом.
    import math
    capital = capital_id(KINGDOMS[0])
    all_towns = [t for k in KINGDOMS for t in layout()[k["kingdom"]]["town"]]
    towns = [t["sid"] for t in all_towns]

    def home_near(point):
        return min(all_towns, key=lambda t: math.hypot(t["x"] - point[0], t["y"] - point[1]))["sid"]
    kept = 0
    for node in ET.parse(os.path.join(VANILLA, "spclans.xml")).getroot():
        if node.get("super_faction"):
            continue  # знатный клан, он удаляется преобразованием
        cid = node.get("id")
        home = capital if cid == "player_faction" else (
            home_near(MINOR_HOMES[cid]) if cid in MINOR_HOMES else towns[kept % len(towns)])
        # Имя и описание перекрываем своими: иначе в энциклопедии остаётся кальрадийский текст
        # про гулямов и Нахазу (замечено в игре 2026-09-22).
        own = MINOR_CLANS.get(cid)
        rename = ""
        if own:
            name, ru, en = own
            # short_name перекрываем обязательно: именно его игра ставит в подпись отряда
            # ("Отряд ... из клана X"), и ванильное короткое имя пережило бы переименование.
            rename = ' name="%s" short_name="%s" text="%s"' % (
                lang.loc(cid + "_name", name),
                lang.loc(cid + "_short", MINOR_SHORT.get(cid, name)),
                lang.loc(cid + "_text", ru, en))
        # tier (и name, если не перекрыто своим) обязательны по схеме Factions.xsd: без них
        # rgl_log сыпал «required attribute 'tier' is missing». Значения ванильные, как и были.
        if " name=" not in rename and node.get("name"):
            rename = ' name="%s"' % esc(node.get("name")) + rename
        rename += ' tier="%s"' % node.get("tier", "1")
        body.append('\t<Faction id="%s" initial_home_settlement="Settlement.%s"%s />'
                    % (cid, home, rename))
        kept += 1
    log("чужих кланов переселено: %d, по %d городам" % (kept, len(towns)))

    body.append("</Factions>\n")
    write("equestria_clans.xml", "\n".join(body),
          "Кланы пяти держав. Ванильные знатные кланы убираются преобразованием\n"
          "     equestria_clans.xslt; разбойничьи и наёмничьи остаются — на них завязаны логова.")
    # Ванильные знатные кланы узнаются по ссылке на королевство. Разбойники её не имеют,
    # поэтому остаются на месте вместе со своими логовами.
    write_xslt("equestria_clans.xslt", ["Faction[@super_faction]"],
               "Удаляем все ванильные знатные кланы (у них есть super_faction). "
               "Разбойничьи и наёмничьи кланы сохраняются.")


# ---------------------------------------------------------------- лорды и семьи
def build_lords_and_heroes():
    lords = ["<NPCCharacters>"]
    heroes = ["<Heroes>"]
    count = 0
    for k in KINGDOMS:
        for clan in k["clans"]:
            spouse_of = {}
            for a, b in clan.get("marriages", []):
                spouse_of[a] = b
                spouse_of[b] = a
            parents = {c[0]: (c[1], c[2]) for c in clan.get("children", [])}
            dead = set(clan.get("dead", []))

            culture_gear = gear_for(k["culture"])
            for hid, name, sex, age, text in clan["heroes"]:
                cid = "eq_" + hid
                # Описания дописанных героев приходят парой (русский, английский): они собраны
                # из шаблона с именами, словарю такое не перевести (tools/world_fill.py)
                text_en = None
                if isinstance(text, tuple):
                    text, text_en = text
                count += 1
                # у именованных героев бывает своя вещь (рог с короной у Кризалис)
                gear = dict(culture_gear, **HERO_GEAR.get(hid, {}))
                lords.append(
                    '\t<NPCCharacter\n'
                    '\t\tid="%s"\n'
                    '\t\tdefault_group="Cavalry"\n'
                    '\t\tis_hero="true"\n'
                    '\t\tage="%d"\n'
                    '\t\tis_female="%s"\n'
                    '\t\trace="%s"\n'
                    '\t\tculture="Culture.%s"\n'
                    '\t\toccupation="Lord"\n'
                    '\t\tname="%s"\n'
                    '\t\tvoice="%s">\n'
                    '\t\t<face>\n'
                    '%s%s'
                    '\t\t</face>\n'
                    '\t\t<skills>\n'
                    '\t\t\t<skill id="OneHanded" value="%d"/>\n'
                    '\t\t\t<skill id="Riding" value="%d"/>\n'
                    '\t\t\t<skill id="Leadership" value="%d"/>\n'
                    '\t\t\t<skill id="Tactics" value="%d"/>\n'
                    '\t\t</skills>\n'
                    '\t\t<Equipments>\n'
                    '\t\t\t<EquipmentRoster>\n'
                    '\t\t\t\t<equipment slot="Item0" id="%s"/>\n'
                    '\t\t\t\t<equipment slot="Item1" id="%s"/>\n'
                    '\t\t\t\t<equipment slot="Head" id="%s"/>\n'
                    '\t\t\t\t<equipment slot="Body" id="%s"/>\n'
                    '\t\t\t\t<equipment slot="Gloves" id="%s"/>\n'
                    '\t\t\t\t<equipment slot="Leg" id="%s"/>\n'
                    '\t\t\t\t<equipment slot="Cape" id="%s"/>\n'
                    '\t\t\t\t<equipment slot="Horse" id="%s"/>\n'
                    '\t\t\t</EquipmentRoster>\n'
                    '\t\t\t<EquipmentRoster civilian="true">\n'
                    '\t\t\t\t<equipment slot="Item0" id="%s"/>\n'
                    '\t\t\t\t<equipment slot="Head" id="%s"/>\n'
                    '\t\t\t\t<equipment slot="Cape" id="%s"/>\n'
                    '\t\t\t</EquipmentRoster>\n'
                    '\t\t</Equipments>\n'
                    '\t</NPCCharacter>'
                    % (cid, age, "true" if sex == "f" else "false", race_for(k["culture"]), k["culture"],
                       lang.loc(cid, name), "curt" if sex == "f" else "earnest", face_xml(hid, age), hair_tags_xml(k["culture"]),
                       90 + (age % 40), 80 + (age % 50), 100 + (age % 60), 80 + (age % 55),
                       gear["sword"], gear["shield"], gear["helmet"], gear["body"],
                       gear["gloves"], gear["leg"], gear["tail"], gear["horse"],
                       gear["sword"], gear["mane"], gear["tail"]))

                links = ""
                if hid in dead:
                    links += '\n\t\talive="false"'
                if hid in spouse_of:
                    links += '\n\t\tspouse="Hero.eq_%s"' % spouse_of[hid]
                if hid in parents:
                    father, mother = parents[hid]
                    if father:
                        links += '\n\t\tfather="Hero.eq_%s"' % father
                    if mother:
                        links += '\n\t\tmother="Hero.eq_%s"' % mother
                heroes.append(
                    '\t<Hero\n\t\tid="%s"\n\t\tfaction="Faction.%s"%s\n\t\ttext="%s" />'
                    % (cid, clan["id"], links, lang.loc(cid + "_text", text, text_en)))

    lords.append("</NPCCharacters>\n")
    heroes.append("</Heroes>\n")
    write("equestria_lords.xml", "\n".join(lords),
          "Лорды пяти держав: раса pony, снаряжение боевое и гражданское (оба обязательны —\n"
          "     без гражданского игра падает при выдаче снаряжения).")
    # В мире не должно остаться людей. Раса прописана у каждого персонажа отдельно, и ванильных
    # записей сотни: бойцы, горожане, крестьяне, наёмники, разбойники, турнирные бойцы. Перебирать
    # их по одной бессмысленно — преобразование проставляет расу всем разом.
    #
    # Файл лордов в SubModule.xml идёт последним среди NPCCharacters, поэтому его преобразование
    # видит уже собранный список: и ванильный, и наших спутников.
    write_file("equestria_lords.xslt",
               '<?xml version="1.0" encoding="utf-8"?>\n'
               '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n'
               '  <!-- Все персонажи игры становятся пони: людей в Эквусе нет.\n'
               '       Своя раса — по культуре (RACE_BY_CULTURE в tools/make_world.py). -->\n'
               '  <xsl:template match="@*|node()">\n'
               '    <xsl:copy><xsl:apply-templates select="@*|node()"/></xsl:copy>\n'
               '  </xsl:template>\n'
               '  <xsl:template match="NPCCharacter">\n'
               '    <xsl:copy>\n'
               '      <xsl:apply-templates select="@*[name()!=\'race\']"/>\n'
               '      <xsl:attribute name="race">\n'
               '        <xsl:choose>\n'
               + "".join('          <xsl:when test="@culture=\'Culture.%s\'">%s</xsl:when>\n' % item
                         for item in sorted(RACE_BY_CULTURE.items())) +
               '          <xsl:otherwise>pony</xsl:otherwise>\n'
               '        </xsl:choose>\n'
               '      </xsl:attribute>\n'
               '      <xsl:apply-templates select="node()"/>\n'
               '    </xsl:copy>\n'
               '  </xsl:template>\n'
               '</xsl:stylesheet>\n')

    write("equestria_heroes.xml", "\n".join(heroes),
          "Кто в каком клане и кто кому родня. Ванильные герои удаляются преобразованием:\n"
          "     их кланов больше нет, и ссылки повисли бы в пустоте.")
    # main_hero трогать нельзя: это герой игрока. Он объявлен в том же ванильном heroes.xml,
    # и без него Campaign.InitializeGamePlayReferences падает на пустой ссылке ещё до карты.
    write_xslt("equestria_heroes.xslt", ["Hero[@id!='main_hero']"],
               "Удаляем всех ванильных героев, кроме main_hero (герой игрока) — "
               "их знатные кланы тоже удалены.")
    return count


# ---------------------------------------------------------------- дружба и вражда
# Отношения между героями игра из XML не читает. Пишем свой файл, а при создании новой кампании
# его применяет EquestriaRelationsBehavior (src/EquestriaRelations.cs).
def build_relations():
    body = ['<?xml version="1.0" encoding="utf-8"?>',
            "<!-- Отношения между героями (-100..100). Собрано tools/make_world.py из world_data.py;",
            "     применяется src/EquestriaRelations.cs при создании новой кампании. -->",
            "<Relations>"]
    known = {h[0] for k in KINGDOMS for c in k["clans"] for h in c["heroes"]}
    count = 0
    for k in KINGDOMS:
        for a, b, value in k.get("relations", []):
            missing = [h for h in (a, b) if h not in known]
            if missing:
                raise SystemExit("отношение с неизвестным героем: " + ", ".join(missing))
            body.append('\t<Relation hero1="eq_%s" hero2="eq_%s" value="%d" />' % (a, b, value))
            count += 1
    body.append("</Relations>\n")
    write_file("equestria_relations.xml", "\n".join(body))
    return count


# ---------------------------------------------------------------- сцены и кварталы
# Внутренние сцены поселения (центр, арена, таверна, зал лорда, тюрьма, дома) перечислены в
# <Locations>. Придумывать их имена нельзя — это реальные сцены игры, и у каждой культуры свои.
# Поэтому берём готовый блок у ванильного поселения той же культуры и того же вида.
LOCATIONS = {}


def load_locations():
    for node in ET.parse(os.path.join(VANILLA, "settlements.xml")).getroot():
        culture = (node.get("culture") or "").replace("Culture.", "")
        comp = node.find("Components")
        locations = node.find("Locations")
        if comp is None or locations is None:
            continue
        if comp.find("Village") is not None:
            kind = "village"
        elif comp.find("Town") is not None:
            kind = "castle" if comp.find("Town").get("is_castle") == "true" else "town"
        else:
            continue
        LOCATIONS.setdefault((culture, kind), ET.tostring(locations, encoding="unicode").strip())
    missing = [(k["culture"], kind) for k in KINGDOMS
               for kind in ("town", "castle", "village") if (donor_culture(k["culture"]), kind) not in LOCATIONS]
    if missing:
        raise SystemExit("не нашлось ванильных сцен для: " + str(missing))
    log("сцены поселений взяты у ванильных: %d наборов" % len(LOCATIONS))


def locations_xml(culture, kind):
    body = LOCATIONS[(donor_culture(culture), kind)]
    return "\n".join("\t\t" + line.strip() for line in body.splitlines() if line.strip())


# Общие кварталы. У города это притоны (Alley) — без них AlleyCampaignBehavior делит на ноль,
# раздавая их главарям банд. У деревни это угодья.
COMMON_AREAS = {
    "town": [("Backstreet", "Закоулок"), ("Clearing", "Пустырь"), ("Waterfront", "Набережная")],
    "village": [("Pasture", "Выгон"), ("Thicket", "Чаща"), ("Bog", "Топь")],
}


def common_areas_xml(sid, kind):
    areas = COMMON_AREAS.get(kind)
    if not areas:
        return ""
    rows = "\n".join('\t\t\t<Area type="%s" name="%s" />'
                     % (kind_name, lang.loc("%s_area_%s" % (sid, kind_name), title))
                     for kind_name, title in areas)
    return "\n\t\t<CommonAreas>\n%s\n\t\t</CommonAreas>" % rows


# ---------------------------------------------------------------- поселения
def build_settlements():
    body = ["<Settlements>"]
    towns = castles = villages = 0
    for k in KINGDOMS:
        spots = layout()[k["kingdom"]]
        culture = k["culture"]
        owners = fief_owners(k)
        for kind in ("town", "castle"):
            for i, fort in enumerate(spots[kind]):
                sid = fort["sid"]
                body.append(settlement_xml(sid, fort["name"], fort["text"], fort.get("text_en"),
                                           fort["x"], fort["y"],
                                           culture, owners[sid], kind, i))
                if kind == "town":
                    towns += 1
                else:
                    castles += 1
        for i, v in enumerate(spots["village"]):
            body.append(village_xml(v["sid"], v["name"], v["x"], v["y"], culture, v["bound"],
                                    village_type(v["x"], v["y"], i)))
            villages += 1

    # Логова разбойников остаются ванильные (на них завязаны разбойничьи кланы), но лежат они
    # в координатах Кальрадии. Переносим их к себе, задав новые координаты по тому же id:
    # слияние XML перезапишет только эти атрибуты.
    hideouts = layout()["hideouts"]
    for hid, (name, x, y) in hideouts.items():
        # name обязателен по схеме игры, даже когда узел только переопределяет координаты
        body.append('\t<Settlement id="%s" name="%s" posX="%.3f" posY="%.3f" />' % (hid, name, x, y))
    log("логовищ перенесено на нашу карту:", len(hideouts))

    # Скит отшельника (уход игрока на покой). RetirementCampaignBehavior ищет его по id каждый
    # игровой час и без него падает — поэтому оставляем ванильный и переносим к себе.
    rx, ry = retreat_position()
    body.append('\t<Settlement id="%s" name="%s" posX="%.3f" posY="%.3f" />'
                % (RETREAT_ID, lang.loc("eq_retreat", "Обитель отшельника"), rx, ry))

    body.append("</Settlements>\n")
    write("equestria_settlements.xml", "\n".join(body),
          "Города, замки и деревни держав Эквуса по карте Equestria at War. Ванильные поселения\n"
          "     удаляются преобразованием, кроме логовищ разбойников: на них завязаны разбойничьи кланы.")
    # Логова оставляем: их дома прописаны у разбойничьих кланов, а на карте они не видны,
    # пока игрок их не отыщет.
    write_xslt("equestria_settlements.xslt",
               ["Settlement[not(Components/Hideout) and @id!='%s']" % RETREAT_ID],
               "Удаляем все ванильные поселения, кроме логовищ разбойников и скита отшельника.")
    # Редактор сцены при сохранении карты мира читает и переписывает ModuleData/settlements.xml
    # (ищет его именно под этим именем и без него падает). Игра этот файл не грузит — его нет в
    # SubModule.xml, — поэтому кладём копию только для редактора.
    import shutil
    shutil.copyfile(os.path.join(DATA, "equestria_settlements.xml"), os.path.join(DATA, "settlements.xml"))
    return towns, castles, villages


RETREAT_ID = "retirement_retreat"


def retreat_position():
    """Скит — в горах недалеко от Кантерлота, на твёрдой земле и не вплотную к поселениям."""
    capital = layout()[KINGDOMS[0]["kingdom"]]["town"][0]
    for r in range(25, 120, 5):
        for step in range(24):
            import math
            a = step * math.pi / 12
            x, y = capital["x"] + r * math.cos(a), capital["y"] + r * math.sin(a)
            if equus_map.terrain(x, y) != equus_map.MOUNTAIN or not equus_map.solid_ground(x, y):
                continue
            near = [p for sp in layout().values() if isinstance(sp, dict) and "town" in sp
                    for kind in ("town", "castle", "village") for p in sp[kind]]
            if all((p["x"] - x) ** 2 + (p["y"] - y) ** 2 > 100 for p in near):
                return round(x, 1), round(y, 1)
    return capital["x"] + 20, capital["y"] + 20


# Картинки меню поселений. Имена ванильные и неровные (у вландии «vlanda» — опечатка самой игры,
# у империи и асераи города берут menu_*, у остальных — gui_bg_town_*), поэтому не угадываем их,
# а берём самые частые у ванильных поселений той же культуры и вида.
MENU_MESHES = {}


def load_menu_meshes():
    import collections
    seen = collections.defaultdict(collections.Counter)
    for node in ET.parse(os.path.join(VANILLA, "settlements.xml")).getroot():
        culture = (node.get("culture") or "").replace("Culture.", "")
        comp = node.find("Components")
        if comp is None:
            continue
        for part in comp:
            if part.tag == "Village":
                kind = "village"
            elif part.tag == "Town":
                kind = "castle" if part.get("is_castle") == "true" else "town"
            else:
                continue
            seen[(culture, kind)][(part.get("background_mesh"), part.get("wait_mesh"),
                                   part.get("castle_background_mesh"))] += 1
    for key, counter in seen.items():
        MENU_MESHES[key] = counter.most_common(1)[0][0]
    missing = [(k["culture"], kind) for k in KINGDOMS
               for kind in ("town", "castle", "village") if (donor_culture(k["culture"]), kind) not in MENU_MESHES]
    if missing:
        raise SystemExit("не нашлось ванильных картинок меню для: " + str(missing))


def gate_of(sid, x, y):
    # Ворота — там же, где у ванильного поселения-донора: его модель встанет на это место.
    # К центру города отряд подойти не может, войти он может только через ворота.
    return settlement_visuals.gate_position(settlement_visuals.pick(*DONORS, sid), x, y)


def settlement_xml(sid, name, text, text_en, x, y, culture, owner_clan, kind, index):
    is_castle = "true" if kind == "castle" else "false"
    mesh, wait, _castle = MENU_MESHES[(donor_culture(culture), kind)]
    return (
        '\t<Settlement\n'
        '\t\tid="%s"\n'
        '\t\tname="%s"\n'
        '\t\towner="Faction.%s"\n'
        '\t\tposX="%.3f"\n'
        '\t\tposY="%.3f"\n'
        '\t\tculture="Culture.%s"\n'
        '\t\tgate_posX="%.3f"\n'
        '\t\tgate_posY="%.3f"\n'
        '\t\ttext="%s">\n'
        '\t\t<Components>\n'
        '\t\t\t<Town\n'
        '\t\t\t\tid="comp_%s"\n'
        '\t\t\t\tis_castle="%s"\n'
        '\t\t\t\tbackground_crop_position="0.0"\n'
        '\t\t\t\tbackground_mesh="%s"\n'
        '\t\t\t\twait_mesh="%s"\n'
        '\t\t\t\tgate_rotation="0.0"\n'
        '\t\t\t\tprosperity="%d" />\n'
        '\t\t</Components>\n'
        '%s%s\n'
        '\t</Settlement>'
        % (sid, lang.loc(sid, name), owner_clan, x, y, culture, *gate_of(sid, x, y),
           lang.loc(sid + "_text", text, text_en), sid, is_castle, mesh, wait,
           2500 if kind == "castle" else 4500,
           locations_xml(culture, kind), common_areas_xml(sid, kind)))


# Промыслы деревень. Идентификаторы должны существовать в игре: если написать несуществующий,
# VillageType у деревни окажется пустым и игра упадёт на первом же подсчёте производства
# (Village.GetWarehouseCapacity). Список сверяется с ванильным ниже.
VILLAGE_TYPES = [
    "VillageType.wheat_farm", "VillageType.cattle_farm", "VillageType.sheep_farm",
    "VillageType.lumberjack", "VillageType.iron_mine", "VillageType.clay_mine",
    "VillageType.flax_plant", "VillageType.fisherman",
]


def check_village_types():
    known = set()
    for node in ET.parse(os.path.join(VANILLA, "settlements.xml")).getroot():
        comp = node.find("Components")
        village = comp.find("Village") if comp is not None else None
        if village is not None and village.get("village_type"):
            known.add(village.get("village_type"))
    unknown = [t for t in VILLAGE_TYPES if t not in known]
    if unknown:
        raise SystemExit("нет таких промыслов деревень в игре: " + ", ".join(unknown))
    log("промыслы деревень сверены с ванильными: %d видов" % len(VILLAGE_TYPES))


# Промысел по местности вокруг деревни: у воды рыбаки, в лесу лесорубы, в горах рудники.
TERRAIN_TRADES = {
    "water": ["VillageType.fisherman"],
    equus_map.FOREST: ["VillageType.lumberjack", "VillageType.sheep_farm"],
    equus_map.MOUNTAIN: ["VillageType.iron_mine", "VillageType.clay_mine"],
    equus_map.STEPPE: ["VillageType.cattle_farm", "VillageType.sheep_farm", "VillageType.clay_mine"],
    equus_map.DESERT: ["VillageType.clay_mine", "VillageType.sheep_farm"],
    equus_map.SNOW: ["VillageType.iron_mine", "VillageType.lumberjack"],
    equus_map.SWAMP: ["VillageType.flax_plant", "VillageType.fisherman"],
    equus_map.PLAIN: ["VillageType.wheat_farm", "VillageType.cattle_farm", "VillageType.flax_plant",
                      "VillageType.wheat_farm"],
}


def village_type(x, y, index):
    near_water = any(not equus_map.is_land(x + dx, y + dy)
                     for dx, dy in ((8, 0), (-8, 0), (0, 8), (0, -8)))
    trades = TERRAIN_TRADES["water"] if near_water and index % 2 == 0 else \
        TERRAIN_TRADES.get(equus_map.terrain(x, y), TERRAIN_TRADES[equus_map.PLAIN])
    return trades[index % len(trades)]


def village_xml(sid, name, x, y, culture, bound, trade):
    return (
        '\t<Settlement\n'
        '\t\tid="%s"\n'
        '\t\tname="%s"\n'
        '\t\tposX="%.3f"\n'
        '\t\tposY="%.3f"\n'
        '\t\tculture="Culture.%s">\n'
        '\t\t<Components>\n'
        '\t\t\t<Village\n'
        '\t\t\t\tid="comp_%s"\n'
        '\t\t\t\tvillage_type="%s"\n'
        '\t\t\t\thearth="300"\n'
        '\t\t\t\tbound="Settlement.%s"\n'
        '\t\t\t\tbackground_crop_position="0.0"\n'
        '\t\t\t\tbackground_mesh="%s"\n'
        '\t\t\t\twait_mesh="%s"\n'
        '\t\t\t\tcastle_background_mesh="%s" />\n'
        '\t\t</Components>\n'
        '%s%s\n'
        '\t</Settlement>'
        % (sid, lang.loc(sid, name), x, y, culture,
           sid, trade, bound,
           *MENU_MESHES[(donor_culture(culture), "village")],
           locations_xml(culture, "village"), common_areas_xml(sid, "village")))


# ---------------------------------------------------------------- снаряжение по культурам
def build_equipment():
    combos = [
        ("king", "IsKingdomRulerTemplate", False, True),
        ("king_f", "IsFemaleTemplate=\"true\" IsKingdomRulerTemplate", True, True),
        ("lord", "IsLordTemplate", False, True),
        ("lord_f", "IsFemaleTemplate=\"true\" IsLordTemplate", True, True),
        ("child", "IsChildEquipmentTemplate=\"true\" IsLordTemplate", False, False),
        ("child_f", "IsChildEquipmentTemplate=\"true\" IsFemaleTemplate=\"true\" IsLordTemplate", True, False),
        ("teen", "IsLordTemplate=\"true\" IsTeenagerEquipmentTemplate", False, False),
        ("teen_f", "IsFemaleTemplate=\"true\" IsLordTemplate=\"true\" IsTeenagerEquipmentTemplate", True, False),
    ]
    body = ["<EquipmentRosters>"]
    for culture in unique_cultures():
        gear = gear_for(culture)
        for suffix, flags, _female, with_battle in combos:
            sets = []
            if with_battle:
                sets.append(
                    '\t\t<EquipmentSet>\n'
                    '\t\t\t<Equipment slot="Item0" id="%s" />\n'
                    '\t\t\t<Equipment slot="Item1" id="%s" />\n'
                    '\t\t\t<Equipment slot="Head" id="%s" />\n'
                    '\t\t\t<Equipment slot="Body" id="%s" />\n'
                    '\t\t\t<Equipment slot="Gloves" id="%s" />\n'
                    '\t\t\t<Equipment slot="Leg" id="%s" />\n'
                    '\t\t\t<Equipment slot="Cape" id="%s" />\n'
                    '\t\t\t<Equipment slot="Horse" id="%s" />\n'
                    '\t\t</EquipmentSet>'
                    % (gear["sword"], gear["shield"], gear["helmet"], gear["body"],
                       gear["gloves"], gear["leg"], gear["tail"], gear["horse"]))
                civilian = ('\t\t<EquipmentSet equipmentType="Civilian">\n'
                            '\t\t\t<Equipment slot="Item0" id="%s" />\n'
                            '\t\t\t<Equipment slot="Head" id="%s" />\n'
                            '\t\t\t<Equipment slot="Cape" id="%s" />\n'
                            '\t\t</EquipmentSet>' % (gear["sword"], gear["mane"], gear["tail"]))
            else:
                civilian = ('\t\t<EquipmentSet equipmentType="Civilian">\n'
                            '\t\t\t<Equipment slot="Head" id="%s" />\n'
                            '\t\t\t<Equipment slot="Cape" id="%s" />\n'
                            '\t\t</EquipmentSet>' % (gear["mane"], gear["tail"]))
            sets.append(civilian)
            body.append('\t<EquipmentRoster id="eq_%s_%s" culture="Culture.%s">\n%s\n\t\t<Flags %s="true" />\n\t</EquipmentRoster>'
                        % (culture, suffix, culture, "\n".join(sets), flags))
    body.append("</EquipmentRosters>\n")
    write("equestria_equipment_sets.xml", "\n".join(body),
          "Шаблоны снаряжения для каждой культуры. Игра ищет их по ТОЧНОМУ совпадению культуры\n"
          "     и набора флагов и не проверяет результат на пустоту — не хватит одного сочетания,\n"
          "     и кампания упадёт при одевании героя.")


# ---------------------------------------------------------------- дипломатия на старте
# Войны, союзы, торговля и дань между державами — из таблицы DIPLOMACY. Игра из XML такого не
# читает, поэтому файл свой, а применяет его src/EquestriaDiplomacy.cs при создании кампании.
def build_diplomacy():
    known = set(k["kingdom"] for k in KINGDOMS)
    body = ['<?xml version="1.0" encoding="utf-8"?>',
            "<!-- Дипломатия на старте кампании. Собран tools/make_world.py из world_data.DIPLOMACY —",
            "     правьте таблицу, не этот файл. Применяет src/EquestriaDiplomacy.cs. -->",
            "<Diplomacy>"]
    count = 0
    for row in DIPLOMACY:
        kind, a, b = row[0], row[1], row[2]
        if a not in known or b not in known:
            log("дипломатия: пропущено %s %s — %s (держава выключена)" % (kind, a, b))
            continue
        gold = ' gold="%d"' % row[3] if kind == "tribute" else ""
        body.append('\t<Stance kind="%s" a="%s" b="%s"%s />' % (kind, a, b, gold))
        count += 1
    body.append("</Diplomacy>\n")
    write_file("equestria_diplomacy.xml", "\n".join(body))
    log("дипломатия: записей %d" % count)


# ---------------------------------------------------------------- запуск
os.makedirs(DATA, exist_ok=True)
check_village_types()
load_locations()
load_menu_meshes()
# Кланы и лорды сверх написанных руками — до ванильной плотности (по числу крепостей державы)
import world_fill  # noqa: E402
world_fill.fill(KINGDOMS, {k["kingdom"]: len(layout()[k["kingdom"]]["town"])
                           + len(layout()[k["kingdom"]]["castle"]) for k in KINGDOMS}, log)
build_cultures()
build_kingdoms()
build_clans()
build_companions()
lord_count = build_lords_and_heroes()
towns, castles, villages = build_settlements()
build_equipment()
relation_count = build_relations()
build_diplomacy()
log("держав %d, кланов %d, лордов %d" % (len(KINGDOMS), sum(len(k["clans"]) for k in KINGDOMS), lord_count))
log("поселений: городов %d, замков %d, деревень %d" % (towns, castles, villages))
log("отношений между героями: %d" % relation_count)
# Строки, написанные руками, а не собранные скриптом: в самих файлах (equestria_strings.xml,
# equestria_characters.xml) и в коде мода (src/*.cs) стоит английский текст, а русский нужно
# донести до языковых файлов — иначе игрок увидит английский. Ключи те же, что в {=...}.
HAND_WRITTEN = {
    "eq_culture_rich_name": "Пони",
    "eq_culture_description":
        "Вы родились пони — единорогом, пегасом или земным пони. Судьба привела вашу семью в земли "
        "Империи, где вы и выросли: ваше детство и юность пройдут по имперскому укладу.",
    "eq_royal_guard": "Королевский гвардеец Эквестрии",
    # народности в окне внешности (src/EquestriaRaceSelector.cs)
    "eq_race_pony": "Пони",
    "eq_race_changeling": "Чейнджлинг",
    "eq_race_deer": "Олень",
    "eq_race_griffon": "Грифон",
    "eq_race_yak": "Як",
    "eq_race_dragon": "Дракон",
    "eq_race_hippogriff": "Гиппогриф",
    # главное меню (src/EquestriaStoryMode.cs): сюжетная кампания отключена
    "eq_story_disabled": "Сюжетная кампания в Эквестрии недоступна — начните игру в песочнице.",
    # главное меню и сообщения при старте (src/EquestriaQuickStart.cs, SubModule.cs, EquestriaShaderWarmup.cs)
    "eq_menu_start": "Начать приключение",
    "eq_note_loaded": "Мод Equestria загружен!",
    "eq_note_quick_start": "Эквестрия: быстрый старт, персонаж по умолчанию",
    "eq_note_shaders": "Эквестрия: шейдеры брони улья собраны за {SECONDS} с",
    "eq_load_preparing": "Эквестрия: готовим шейдеры — {NOTE}",
    "eq_load_compiling": "Эквестрия: сборка шейдеров — осталось {LEFT} из {PEAK}{NOTE}",
    "eq_load_hive": "броня улья",
    # разбор скорости отряда (src/EquestriaPartySpeed.cs)
    "eq_speed_rough": "Тяжёлая местность",
    "eq_speed_ford": "Переход реки вброд",
}
HAND_WRITTEN_EN = {
    "eq_menu_start": "Start the adventure",
    "eq_note_loaded": "Equestria mod loaded!",
    "eq_note_quick_start": "Equestria: quick start, default character",
    "eq_note_shaders": "Equestria: hive armour shaders built in {SECONDS} s",
    "eq_load_preparing": "Equestria: preparing shaders - {NOTE}",
    "eq_load_compiling": "Equestria: compiling shaders - {LEFT} of {PEAK} left{NOTE}",
    "eq_load_hive": "hive armour",
}
for _key, _text in HAND_WRITTEN.items():
    lang.loc(_key, _text, HAND_WRITTEN_EN.get(_key))

# Языковые файлы: в XML выше ушёл английский, русский собрался здесь
lang.write(DATA, "eq_world", log)
lang.report(log)
