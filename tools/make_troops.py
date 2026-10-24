# Troops for ponies: the vanilla imperial tree (the Equestrian army), all bandits
# and the Aserai tree - the changeling swarm (its own race).
#
#   py -3 tools\make_troops.py [Module folder] [game folder]
#
# Troop ids stay vanilla (imperial_recruit etc.): lord party templates, militia, caravans and the
# upgrade tree refer to them. Each entry is rewritten in full - the attribute
# _replaceWhileMerging="true" makes the game drop the vanilla entry with the same id
# (MBObjectManager.MergeElementAttributes) and take ours.
#
# What changes:
#   - the name follows the lore (Solar Guard, unicorn archers, pegasi, Luna's Night Guard);
#   - the race is pony;
#   - armour: a vanilla item stays as is; if the slot is empty, an item by troop tier is filled in.
#     Pony versions (eq_pony_<id>) used to be substituted here - the mod no longer has its own armour,
#     all races are fitted to the vanilla human and wear the game's ordinary items;
#   - without a helmet the head has the mane, the cape slot has the tail.
# Weapons, horses, skills and upgrades are vanilla.
import copy
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lang  # noqa: E402

# Arguments are read only when run directly: the module is also imported from Blender
# (adapt_armor.py -> armor_catalog.py), and there sys.argv holds something else entirely.
ARGS = sys.argv[1:] if __name__ == "__main__" else []
MODULE = ARGS[0] if ARGS else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
GAME = ARGS[1] if len(ARGS) > 1 else \
    r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
VANILLA = os.path.join(GAME, "Modules", "SandBoxCore", "ModuleData")
# Run tools/replace_mounts.py AFTER this script: horses in the Horse slot → flight scrolls by level
# (10.10.2026).
OUT = os.path.join(MODULE, "ModuleData", "equestria_troops.xml")

CULTURE = "empire"
MANE = None  # mane and horn are a hairstyle (make_pony_manes.py), the pony helmet slot is free
TAIL = None  # the tail is a body part attached by code (src/EquestriaBodyParts.cs), the cape slot is free

# The group's race and its body-part items (crest in the helmet slot, wings with tail in the cape slot).
# Changelings do not wear helmets: the horn and crest are their face. Groups without an entry are ponies.
# bare_tier - up to which tier the troop goes barefoot (changelings have holes in their legs - they show).
# hair_tag - which race hairstyles the troop may have (Bald - bald drones: they have a crest item).
# The crest item (eq_changeling_crest) no longer exists: it belonged to the old model, and in the new one
# (tools/make_changeling_model.py) the horn and ears are part of the head. The helmet slot stays empty,
# drones go bare-headed, as before.
RACES = {
    "Чейнджлинги": {"race": "changeling", "mane": None,
                    "tail": None, "no_helmet": True, "bare_tier": 1,
                    "hair_tag": "Bald"},
    # Other kingdoms: their own race and their own hairstyle (crest, antlers, mane). Without an entry the troop
    # would get the pony mane: the skins have no such hairstyle for another race, and the head would stay bare.
    "Грифоны": {"race": "griffon", "mane": None, "tail": None, "no_helmet": False,
                "bare_tier": 0, "hair_tag": "GriffonCrest"},
    "Гиппогрифы": {"race": "hippogriff", "mane": None, "tail": None, "no_helmet": False,
                   "bare_tier": 0, "hair_tag": "HippogriffCrest"},
    "Драконы": {"race": "dragon", "mane": None, "tail": None, "no_helmet": False,
                "bare_tier": 0, "hair_tag": "DragonCrest"},
    "Яки": {"race": "yak", "mane": None, "tail": None, "no_helmet": False,
            "bare_tier": 0, "hair_tag": "YakMane"},
    "Олени": {"race": "deer", "mane": None, "tail": None, "no_helmet": False,
              "bare_tier": 0, "hair_tag": "DeerAntlers"},
}
PONY = {"race": "pony", "mane": MANE, "tail": TAIL, "no_helmet": False, "bare_tier": 0, "hair_tag": "PonyMane"}

# Names from the lore. Infantry - Celestia's Royal Guard, archers - unicorns, the noble branch -
# flight academy pegasi and the Wonderbolts, horse archers - Luna's Night Guard.
NAMES = {
    "imperial_recruit": "Эквестрийский новобранец",
    "imperial_infantryman": "Стражник Эквестрии",
    "imperial_trained_infantryman": "Королевский стражник",
    "imperial_veteran_infantryman": "Ветеран Королевской стражи",
    "imperial_legionary": "Солнечный гвардеец",
    "imperial_menavliaton": "Алебардщик Кантерлота",
    "imperial_elite_menavliaton": "Страж Кантерлотских врат",
    "imperial_archer": "Единорог-стрелок",
    "imperial_trained_archer": "Опытный единорог-стрелок",
    "imperial_veteran_archer": "Единорог-чародей",
    "imperial_palatine_guard": "Магическая стража принцессы",
    "bucellarii": "Ночной страж Луны",
    "imperial_crossbowman": "Арбалетчик Мейнхэттена",
    "imperial_sergeant_crossbowman": "Сержант-арбалетчик Мейнхэттена",
    "imperial_vigla_recruit": "Кадет лётной академии",
    "imperial_equite": "Пегас-разведчик",
    "imperial_heavy_horseman": "Пегас-штурмовик",
    "imperial_cataphract": "Вандерболт",
    "imperial_elite_cataphract": "Ас Вандерболтов",
    "imperial_militia_spearman": "Ополченец Понивилля",
    "imperial_militia_archer": "Ополченец-стрелок",
    "imperial_militia_veteran_spearman": "Бывалый ополченец",
    "imperial_militia_veteran_archer": "Бывалый ополченец-стрелок",
}

# Bandits - by the gangs from world_data.MINOR_CLANS. All are ponies for now: diamond dogs, yaks and other
# peoples will come along with their races.
# Queen Chrysalis's swarm: drones, hunters, hive guards.
CHANGELING_NAMES = {
    "aserai_recruit": "Молодой трутень",
    "aserai_tribesman": "Трутень роя",
    "aserai_skirmisher": "Плевун",
    "aserai_archer": "Стрелок улья",
    "aserai_master_archer": "Меткий плевун королевы",
    "aserai_footman": "Боец роя",
    "aserai_infantry": "Воин улья",
    "aserai_veteran_infantry": "Ветеран улья",
    "aserai_mameluke_soldier": "Оборотень-лазутчик",
    "aserai_mameluke_regular": "Оборотень-наездник",
    "aserai_mameluke_cavalry": "Крылатый охотник",
    "aserai_mameluke_heavy_cavalry": "Крылатый ловчий королевы",
    "aserai_mameluke_axeman": "Лазутчик-рубака",
    "aserai_mameluke_guard": "Страж улья",
    "mamluke_palace_guard": "Страж тронного зала",
    "aserai_youth": "Личинка-гонец",
    "aserai_tribal_horseman": "Роевой всадник",
    "aserai_faris": "Всадник улья",
    "aserai_veteran_faris": "Старший всадник улья",
    "aserai_vanguard_faris": "Авангард королевы",
    "aserai_militia_spearman": "Ополченец улья",
    "aserai_militia_archer": "Ополченец-плевун",
    "aserai_militia_veteran_spearman": "Опытный ополченец улья",
    "aserai_militia_veteran_archer": "Опытный ополченец-плевун",
}

# Griffons of Griffonstone (vanilla KHUZAITS - the horse archer and cavalry branch: griffons fly,
# and a mounted kingdom suits them better than the foot Vlandian one; swapped with the yaks 10.10.2026, see
# ROSTER_OF): cliffs, nests and the Idol of Boreas. The mounted branches are flying.
GRIFFON_NAMES = {
    "khuzait_nomad": "Птенец Грифонстоуна",
    "khuzait_tribal_warrior": "Грифон-боец",
    "khuzait_raider": "Грифон-налётчик",
    "khuzait_horse_archer": "Небесный стрелок Грифонстоуна",
    "khuzait_heavy_horse_archer": "Тяжёлый небесный стрелок",
    "khuzait_horseman": "Небесный дозорный",
    "khuzait_lancer": "Крылатый копейщик Грифонстоуна",
    "khuzait_heavy_lancer": "Крылатый налётчик",
    "khuzait_footman": "Страж гнезда",
    "khuzait_hunter": "Охотник утёсов",
    "khuzait_archer": "Лучник Грифонстоуна",
    "khuzait_marksman": "Меткий глаз Бориаса",
    "khuzait_spearman": "Копейщик гнезда",
    "khuzait_spear_infantry": "Опытный копейщик гнезда",
    "khuzait_darkhan": "Секироносец Грифонстоуна",
    "khuzait_noble_son": "Сын знатного гнезда",
    "khuzait_qanqli": "Оруженосец Идола",
    "khuzait_torguud": "Молодой когтеносец",
    "khuzait_kheshig": "Когтеносец Грифонстоуна",
    "khuzait_khans_guard": "Стража Идола Бориаса",
    "khuzait_militia_spearman": "Ополченец Грифонстоуна",
    "khuzait_militia_archer": "Ополченец-лучник Грифонстоуна",
    "khuzait_militia_veteran_spearman": "Бывалый ополченец Грифонстоуна",
    "khuzait_militia_veteran_archer": "Бывалый ополченец-лучник Грифонстоуна",
}

# Hippogriffs of Mount Aris and sea ponies of Seaquestria: COPIES of the Sturgian entries (COPY_PREFIX
# prefix, see the "copies of the Sturgian branch" section below) - the foot northern branch; swapped with
# the deer 10.10.2026 (ROSTER_OF). Harpoons, reefs and the Pearl; the mounted branch is flying.
HIPPOGRIFF_NAMES = {
    "sturgian_recruit": "Доброволец горы Арис",
    "sturgian_warrior": "Воин горы Арис",
    "sturgian_soldier": "Обученный воин Ариса",
    "sturgian_spearman": "Гарпунщик прибоя",
    "sturgian_shock_troop": "Тяжёлый гарпунщик Ариса",
    "sturgian_veteran_warrior": "Ветеран прибоя",
    "sturgian_berzerker": "Рифовый буян",
    "sturgian_ulfhednar": "Ярость прибоя",
    "sturgian_woodsman": "Бегун по рифам",
    "sturgian_brigand": "Налётчик Сиквестрии",
    "sturgian_hardened_brigand": "Бывалый налётчик Сиквестрии",
    "sturgian_horse_raider": "Летучий гарпунщик",
    "sturgian_hunter": "Небесный разведчик",
    "sturgian_archer": "Лучник горы Арис",
    "sturgian_veteran_bowman": "Меткий лучник Ариса",
    "sturgian_warrior_son": "Птенец знатного гнезда",
    "varyag": "Знатный воин Ариса",
    "varyag_veteran": "Герой горы Арис",
    "druzhinnik": "Страж Жемчужины",
    "druzhinnik_champion": "Поборник Жемчужины",
    "sturgian_militia_spearman": "Ополченец горы Арис",
    "sturgian_militia_archer": "Ополченец-лучник горы Арис",
    "sturgian_militia_veteran_spearman": "Бывалый ополченец горы Арис",
    "sturgian_militia_veteran_archer": "Бывалый ополченец-лучник горы Арис",
}

# Dragons of the volcanic lands (vanilla VLANDIA - the branch with crossbows and knights; swapped
# with the yaks 10.10.2026, ROSTER_OF): the Sceptre, the Gauntlet and the Dragon Lord. The mounted
# branches are flying.
DRAGON_NAMES = {
    "vlandian_recruit": "Юный дракон",
    "vlandian_levy_crossbowman": "Дракон с арбалетом",
    "vlandian_crossbowman": "Арбалетчик пепла",
    "vlandian_hardened_crossbowman": "Бывалый арбалетчик пепла",
    "vlandian_sharpshooter": "Меткий стрелок вулкана",
    "vlandian_footman": "Драконий боец",
    "vlandian_spearman": "Копейщик пепла",
    "vlandian_billman": "Крюкастый дракон",
    "vlandian_voulgier": "Секироносец лавы",
    "vlandian_pikeman": "Пикинёр вулкана",
    "vlandian_swordsman": "Клинок Драконьих Земель",
    "vlandian_sergeant": "Драконий воин",
    "vlandian_light_cavalry": "Лазутчик ущелий",
    "vlandian_cavalry": "Летучий налётчик",
    "vlandian_vanguard": "Авангард Состязания",
    "vlandian_squire": "Отпрыск драконьего рода",
    "vlandian_gallant": "Молодой страж Скипетра",
    "vlandian_knight": "Страж Скипетра",
    "vlandian_champion": "Поборник Состязания",
    "vlandian_banner_knight": "Дружинник лорда драконов",
    "vlandian_militia_spearman": "Ополченец Драконьих Земель",
    "vlandian_militia_archer": "Ополченец-арбалетчик Драконьих Земель",
    "vlandian_militia_veteran_spearman": "Бывалый ополченец Драконьих Земель",
    "vlandian_militia_veteran_archer": "Бывалый ополченец-арбалетчик Драконьих Земель",
    "vlandian_infantry": "Пехотинец Драконьих Земель",   # not part of the upgrade tree, but exists in the game
}

# Yaks of Yakyakistan (vanilla STURGIA - the foot northern branch; swapped with the dragons 10.10.2026,
# ROSTER_OF): glaciers, bluntness and the knack for smashing.
YAK_NAMES = {
    "sturgian_recruit": "Молодой як",
    "sturgian_warrior": "Як-боец",
    "sturgian_soldier": "Пеший як",
    "sturgian_spearman": "Копейщик Яктауна",
    "sturgian_shock_troop": "Опытный копейщик Яктауна",
    "sturgian_veteran_warrior": "Секироносец Якьякистана",
    "sturgian_berzerker": "Крушитель",
    "sturgian_ulfhednar": "Ярость ледника",
    "sturgian_woodsman": "Охотник ледника",
    "sturgian_brigand": "Як-налётчик",
    "sturgian_hardened_brigand": "Бывалый налётчик ледника",
    "sturgian_horse_raider": "Налётчик тундры",     # yaks are on foot: a former horseman
    "sturgian_hunter": "Следопыт тундры",
    "sturgian_archer": "Лучник Якьякистана",
    "sturgian_veteran_bowman": "Меткий лучник ледника",
    "sturgian_warrior_son": "Сын знатного яка",
    "varyag": "Гвардеец Яктауна",
    "varyag_veteran": "Старший гвардеец Яктауна",
    "druzhinnik": "Телохранитель принца",
    "druzhinnik_champion": "Стража принца Резерфорда",
    "sturgian_militia_spearman": "Ополченец Якьякистана",
    "sturgian_militia_archer": "Ополченец-лучник Якьякистана",
    "sturgian_militia_veteran_spearman": "Бывалый ополченец Якьякистана",
    "sturgian_militia_veteran_archer": "Бывалый ополченец-лучник Якьякистана",
}

# Deer of Olenia (vanilla BATTANIA - the foot forest branch; the Nords have no troops in vanilla,
# previously Olenia took copies of the Sturgian entries, since 10.10.2026 the copies went to the
# hippogriffs, see ROSTER_OF).
# Forest, bow and the Council of Seven; the mounted branch rides, deer do not fly.
DEER_NAMES = {
    "battanian_volunteer": "Молодой олень",
    "battanian_clanwarrior": "Лесной боец",
    "battanian_trained_warrior": "Оленийский воин",
    "battanian_picked_warrior": "Отборный воин Олении",
    "battanian_oathsworn": "Гвардеец Оленьей Рощи",
    "battanian_scout": "Оленийский разведчик",
    "battanian_horseman": "Рогатый налётчик",          # deer are on foot: a former horseman
    "battanian_woodrunner": "Лесовик",
    "battanian_raider": "Оленийский разбойник",
    "battanian_falxman": "Копейщик чащи",
    "battanian_veteran_falxman": "Тяжёлый копейщик Олении",
    "battanian_skirmisher": "Метатель дротиков Олении",
    "battanian_veteran_skirmisher": "Бывалый метатель дротиков Олении",
    "battanian_wildling": "Рогатый таран",
    "battanian_mounted_skirmisher": "Застрельщик Олении",  # deer are on foot: a former mounted troop
    "battanian_highborn_youth": "Сын оленьего дома",
    "battanian_highborn_warrior": "Знатный воин Олении",
    "battanian_hero": "Дружинник короля Олении",
    "battanian_fian": "Лучник Совета Семи",
    "battanian_fian_champion": "Поборник Совета Семи",
    "battanian_militia_spearman": "Ополченец Олении",
    "battanian_militia_archer": "Ополченец-лучник Олении",
    "battanian_militia_veteran_spearman": "Бывалый ополченец Олении",
    "battanian_militia_veteran_archer": "Бывалый ополченец-лучник Олении",
}

# Gang race. The vanilla game already tied each gang to a kingdom: its bandits upgrade into
# troops of that culture (forest ones into Battanian, mountain ones into Vlandian and so on). We take the same
# link - otherwise on upgrade a bandit would change nationality right in the party.
# Looters and deserters (culture looters) are the exception: they are riff-raff from all over the map, and are
# drawn from all peoples at once (see LOOTER_RACES below).
COPY_PREFIX = "eq_hg_"     # id prefix of the Sturgian branch copies - they belong to the hippogriffs (see below)

BANDIT_RACE = {
    "sea_raiders": "Драконы",        # upgrade into Sturgian troops
    "mountain_bandits": "Грифоны",   # into Vlandian
    "forest_bandits": "Гиппогрифы",  # into Battanian
    "desert_bandits": "Чейнджлинги",  # into Aserai
    "steppe_bandits": "Яки",         # into Khuzait
}

# Looters come in all kinds: each race has its own copy of the entry, and in the party template (equestria_party
# _templates.xml) they stand side by side - one band can have ponies, griffons, yaks and others.
# Ponies stay on the vanilla ids, the others get a prefix.
# The value is what the bandit upgrades into: the vanilla looter goes into imperial infantry, and the copy
# must go into the same infantry of ITS OWN culture, otherwise the race changes on upgrade.
LOOTER_RACES = {
    "pony": {},
    # branches by ROSTER_OF: griffons - Khuzaits, dragons - Vlandians, yaks - Sturgians,
    # deer - Battanians, hippogriffs - copies of the Sturgians
    "griffon": {"imperial_infantryman": "khuzait_tribal_warrior",
                "imperial_trained_infantryman": "khuzait_raider"},
    "hippogriff": {"imperial_infantryman": COPY_PREFIX + "sturgian_warrior",
                   "imperial_trained_infantryman": COPY_PREFIX + "sturgian_soldier"},
    "dragon": {"imperial_infantryman": "vlandian_footman",
               "imperial_trained_infantryman": "vlandian_spearman"},
    "yak": {"imperial_infantryman": "sturgian_warrior",
            "imperial_trained_infantryman": "sturgian_soldier"},
    "changeling": {"imperial_infantryman": "aserai_tribesman",
                   "imperial_trained_infantryman": "aserai_footman"},
    "deer": {"imperial_infantryman": "battanian_clanwarrior",
             "imperial_trained_infantryman": "battanian_trained_warrior"},
}
LOOTER_TROOPS = ("looter", "deserter", "mounted_pillager", "mounted_ransacker")
LOOTER_HAIR = {"pony": "PonyMane", "griffon": "GriffonCrest", "hippogriff": "HippogriffCrest",
               "dragon": "DragonCrest", "yak": "YakMane", "changeling": "Bald",
               "deer": "DeerAntlers"}

BANDIT_NAMES = {
    # Looters
    "looter": "Мародёр",
    "deserter": "Дезертир",
    "mounted_pillager": "Конный грабитель",
    "mounted_ransacker": "Конный налётчик",
    # The Storm King's army (sea raiders)
    "sea_raiders_bandit": "Пират Короля Шторма",
    "sea_raiders_raider": "Абордажник Короля Шторма",
    "sea_raiders_chief": "Капитан Короля Шторма",
    "sea_raiders_boss": "Адмирал Короля Шторма",
    # Diamond Dogs (mountain bandits)
    "mountain_bandits_bandit": "Горный старатель",
    "mountain_bandits_raider": "Громила Алмазных Псов",
    "mountain_bandits_chief": "Вожак Алмазных Псов",
    "mountain_bandits_boss": "Король Алмазных Псов",
    # Timberwolves (forest bandits)
    "forest_bandits_bandit": "Лесной бродяга",
    "forest_bandits_raider": "Вольный стрелок Вечнодикого леса",
    "forest_bandits_chief": "Атаман Тимбервульфов",
    "forest_bandits_boss": "Хозяин Вечнодикого леса",
    # Vultures of the Badlands (desert bandits)
    "desert_bandits_bandit": "Бродяга Бесплодных Земель",
    "desert_bandits_raider": "Пустынный налётчик",
    "desert_bandits_chief": "Стервятник",
    "desert_bandits_boss": "Главарь Стервятников",
    # Buffalo Raids (steppe bandits)
    "steppe_bandits_bandit": "Степной разбойник",
    "steppe_bandits_raider": "Бизоний налётчик",
    "steppe_bandits_chief": "Вожак набега",
    "steppe_bandits_boss": "Вождь Бизоньих Набегов",
}


# Common folk: caravan masters, traders and peasants. They are not in the troop trees, but they show in
# the encyclopedia and in parties - and were still called the vanilla way
# ("Aserai Peasant"). The name is built from role and kingdom, the English is
# written next to it: such pairs cannot be built from the dictionary.
CIVIL_ROLES = {
    "caravan_master": ("Караванщик", "Caravan Master"),
    "armed_trader": ("Вооружённый торговец", "Armed Trader"),
    "caravan_guard": ("Охранник каравана", "Caravan Guard"),
    "veteran_caravan_guard": ("Бывалый охранник каравана", "Veteran Caravan Guard"),
    "village_woman": ("Крестьянка", "Peasant Woman"),
    "villager": ("Крестьянин", "Peasant"),
    "fighter": ("Деревенский боец", "Village Fighter"),
}
# Whose kingdom it is - by the entry's culture
CIVIL_OF = {
    "empire": ("Эквестрии", "of Equestria"),
    "vlandia": ("Грифонстоуна", "of Griffonstone"),
    "battania": ("горы Арис", "of Mount Aris"),
    "sturgia": ("Драконьих Земель", "of the Dragon Lands"),
    "khuzait": ("Якьякистана", "of Yakyakistan"),
    "aserai": ("улья", "of the Hive"),
    "nord": ("Олении", "of Olenia"),
}
# Race and hairstyle by culture - for civilians, where the group is shared by all kingdoms
CULTURE_RACE = {"aserai": "Чейнджлинги", "vlandia": "Грифоны", "battania": "Гиппогрифы",
                "sturgia": "Драконы", "khuzait": "Яки", "nord": "Олени"}


# Settlement notables: appearance presets for merchants, headmen and gang leaders. They show in the
# encyclopedia, and were named after vanilla factions
# ("Cautious Imperial Merchant").
# The personality from the vanilla name (cautious, sly, rebellious) is not carried over: in game a notable has
# their own name, and there are several presets per role - the player has no reason to tell them apart.
NOTABLE_ROLES = {
    "Merchant": ("Торговец", "Merchant"),
    "Preacher": ("Проповедник", "Preacher"),
    "Artisan": ("Ремесленник", "Artisan"),
    "GangLeader": ("Главарь банды", "Gang Leader"),
    "RuralNotable": ("Сельский староста", "Rural Notable"),
    "Headman": ("Деревенский голова", "Headman"),
}


def notable_names(characters):
    """{id: (Russian, English)} for settlement notables of all cultures."""
    result = {}
    for cid, node in characters.items():
        role = NOTABLE_ROLES.get(node.get("occupation"))
        culture = (node.get("culture") or "").replace("Culture.", "")
        if role and culture in CIVIL_OF:
            ru_of, en_of = CIVIL_OF[culture]
            result[cid] = ("%s %s" % (role[0], ru_of), "%s %s" % (role[1], en_of))
    return result


# Mercenary company troops: each minor clan has its own little tree <clan>_tier_1..3. We renamed the leaders
# long ago (leader_names), but the troops stayed Calradian: the company that became our
# Sky Pirates recruited "Boar Novices" (seen in game 25.09.2026). Names follow the lore
# of the company itself - it is in world_data.MINOR_CLANS - three tiers per company.
MERC_NAMES = {
    "jawwal": (("Верный трутень", "Loyal Drone"),
               ("Мститель Хризалиды", "Chrysalis Avenger"),
               ("Клинок Хризалиды", "Chrysalis Blade")),
    "eleftheroi": (("Равный ополченец", "Equal Militiaman"),
                   ("Равный копейщик", "Equal Spearpony"),
                   ("Старший равный", "Senior Equal")),
    "hidden_hand": (("Ярмарочный зазывала", "Fairground Barker"),
                    ("Охранник повозки", "Wagon Guard"),
                    ("Вышибала братьев", "Brothers' Enforcer")),
    "lakepike": (("Юный огнедышец", "Young Firebreather"),
                 ("Дракон-наёмник", "Dragon Hireling"),
                 ("Ветеран Драконьего Пламени", "Dragonflame Veteran")),
    "legion_of_the_betrayed": (("Ночной дозорный", "Night Watchpony"),
                               ("Лунный волк", "Moon Wolf"),
                               ("Клинок полуночи", "Midnight Blade")),
    "ghilman": (("Наёмник из Клюгтауна", "Klugetown Hireling"),
                ("Абиссинский клинок", "Abyssinian Blade"),
                ("Ветеран абиссинцев", "Abyssinian Veteran")),
    "skolderbrotva": (("Портовый задира", "Harbour Brawler"),
                      ("Вольный клинок", "Free Blade"),
                      ("Чешуйчатый ветеран", "Scaled Veteran")),
    "beni_zilal": (("Молодая тень", "Young Shadow"),
                   ("Тень улья", "Hive Shadow"),
                   ("Старшая тень", "Elder Shadow")),
    "embers_of_flame": (("Новобранец Золотой Подковы", "Golden Horseshoe Recruit"),
                        ("Солдат Золотой Подковы", "Golden Horseshoe Soldier"),
                        ("Ветеран Золотой Подковы", "Golden Horseshoe Veteran")),
    "karakhuzaits": (("Молодой чёрный як", "Young Black Yak"),
                     ("Чёрный як", "Black Yak"),
                     ("Крушитель Чёрных Яков", "Black Yak Smasher")),
    "company_of_the_boar": (("Юнга небесного корабля", "Skyship Deckhand"),
                            ("Небесный пират", "Sky Pirate"),
                            ("Старший канонир Келено", "Celaeno's Master Gunner")),
    "wolfskins": (("Юный клинок Ариса", "Young Aris Blade"),
                  ("Клинок Горы Арис", "Mount Aris Blade"),
                  ("Морской ветеран Ариса", "Aris Sea Veteran")),
    "brotherhood_of_woods": (("Следопыт-послушник", "Novice Ranger"),
                             ("Следопыт Братства", "Brotherhood Ranger"),
                             ("Старший следопыт Братства", "Brotherhood Elder Ranger")),
    "forest_people": (("Шпана Гарбла", "Garble's Punk"),
                      ("Задира из ватаги", "Gang Bully"),
                      ("Правая лапа Гарбла", "Garble's Right Claw")),
}


def merc_clan(cid):
    """Clan by mercenary troop id (skolderbrotva_tier_2 -> skolderbrotva); otherwise None."""
    if "_tier_" not in cid:
        return None
    clan = cid[:cid.index("_tier_")]
    return clan if clan in MERC_NAMES else None


def merc_names(characters):
    """{id: (Russian, English)} for mercenary company troops."""
    result = {}
    for cid in characters:
        clan = merc_clan(cid)
        if clan is None:
            continue
        try:
            tier = int(cid.rsplit("_", 1)[-1])
        except ValueError:
            continue
        rows = MERC_NAMES[clan]
        if 1 <= tier <= len(rows):
            result[cid] = rows[tier - 1]
    return result


def merc_race(clan, leaders):
    """The company's race is the same as its leader's.

    In a third of the companies the troop culture and the leader culture DIFFER: the Klugetown free blades
    are on the Nord culture (Olenia for us), while their leader is Sturgian, i.e. a dragon. Taking the race
    from the troop's own culture is not an option: a dragon company would be full of deer.
    """
    for cid, node in leaders.items():
        if cid.startswith("spc_" + clan + "_leader_"):
            culture = (node.get("culture") or "").replace("Culture.", "")
            return RACES.get(CULTURE_RACE.get(culture, ""), None)
    return None


def leader_names(characters):
    """{id: (Russian, English)} for leaders of mercenary parties and gangs (spc_<clan>_leader_N)."""
    import world_data  # noqa: E402 - the mercenary clan table, their names in the mod are there too
    result = {}
    for cid, node in characters.items():
        if node.get("occupation") != "Lord" or "_leader_" not in cid or not cid.startswith("spc_"):
            continue
        clan = cid[len("spc_"):cid.index("_leader_")]
        row = world_data.MINOR_CLANS.get(clan)
        if row:
            result[cid] = ("Вождь «%s»" % row[0], "Chief of the %s" % lang.en(row[0]))
    return result


def civil_role(cid):
    """(role, culture) for an entry like villager_empire; otherwise None.

    The suffix must be exactly a culture name: ids like villager_child_sturgia are a teenager
    and a child, they have their own vanilla name ("Villager child"), no need to attach a kingdom to it.
    """
    for role in CIVIL_ROLES:
        if cid.startswith(role + "_") and cid[len(role) + 1:] in CIVIL_OF:
            culture = cid[len(role) + 1:]
            return role, swapped_culture(cid, culture)   # villager_vlandia now belongs to the dragons
    return None


def civil_names(characters):
    """{id: (Russian name, English)} for civilian entries of all cultures."""
    result = {}
    for cid in characters:
        found = civil_role(cid)
        if not found:
            continue
        role, culture = found
        ru_role, en_role = CIVIL_ROLES[role]
        ru_of, en_of = CIVIL_OF[culture]
        result[cid] = ("%s %s" % (ru_role, ru_of), "%s %s" % (en_role, en_of))
    return result


# ---------------------------------------------------------------- branch swap
# Kingdoms keep their cultures (vlandia = Griffonstone, khuzait = Yakyakistan, sturgia =
# Dragon Lands, battania = Mount Aris, nord = Olenia; make_world.RACE_BY_CULTURE), but each takes the vanilla
# BRANCH - troops, militia, townsfolk, peasants, notables and their clothes - from another one
# (10.10.2026): the flying griffons and dragons get the mounted Khuzaits and Vlandians, the foot yaks
# and deer get the Sturgians and Battanians, the hippogriffs get copies of the Sturgian branch (the Nords
# have no troops in vanilla, so copies are needed in any case). For this the culture of the branch's vanilla entries is rewritten
# (khuzait_nomad → Culture.vlandia), and make_world (FULL_CULTURE_FROM) gives the culture
# its donor's references. Mercenary companies (company_of_the_boar and others not in a culture tree)
# are left alone: their race follows the leader.
ROSTER_OF = {"vlandia": "khuzait", "khuzait": "sturgia", "sturgia": "vlandia",
             "nord": "battania", "battania": "sturgia"}
# The culture that takes COPIES of the branch (COPY_PREFIX): the Sturgian branch has two owners.
COPY_CULTURE = "battania"
# Where the vanilla branch entries go: {vanilla branch culture: our culture}
RECORD_CULTURE = {roster: culture for culture, roster in ROSTER_OF.items() if culture != COPY_CULTURE}


def swapped_culture(cid, culture, roster_ids=None):
    """The entry's culture after the swap (khuzait_nomad → vlandia); other entries do not change."""
    new = RECORD_CULTURE.get(culture)
    if not new:
        return culture
    if culture in cid or (roster_ids is not None and cid in roster_ids.get(culture, ())):
        return new
    return culture


def swap_cultures(characters, game=None):
    """Rewrites the culture of the entries of the swapped branches (in place).

    An entry belongs to a branch if its id contains the culture word (vlandian_*, villager_khuzait)
    or it is part of the culture's upgrade tree (varyag, druzhinnik - without the word in the id).
    """
    base = os.path.join(game or GAME, "Modules")
    cultures = {c.get("id"): c for c in ET.parse(
        os.path.join(base, "SandBoxCore", "ModuleData", "spcultures.xml")).getroot()}
    roster_ids = {roster: set(tree(characters, cultures[roster])) for roster in RECORD_CULTURE
                  if roster in cultures}
    for cid, node in characters.items():
        culture = (node.get("culture") or "").replace("Culture.", "")
        new = swapped_culture(cid, culture, roster_ids)
        if new != culture:
            node.set("culture", "Culture." + new)


# ---------------------------------------------------------------- copies of the Sturgian branch
# The Sturgian branch is needed by two kingdoms: the yaks (vanilla entries, culture khuzait) and the hippogriffs
# (COPY_CULTURE). So for the hippogriffs their OWN copies are made of all entries the donor culture
# looks at: ids with the COPY_PREFIX prefix, culture battania, race hippogriff. The references in the
# culture are rewritten by make_world using the same map (copy_map). Olenia used to live like this (the Nords
# have neither troops nor townsfolk in vanilla); since 10.10.2026 the deer are on the Battanian branch.
DONOR_CULTURE = "sturgia"


# Where the entries the culture looks at are: troops and townsfolk in one file, peasant and
# townswoman templates in the second, guards in the third, notables and village heads in the fourth.
DONOR_FILES = [
    ("SandBoxCore", "spnpccharacters.xml"),
    ("SandBoxCore", "spnpccharactertemplates.xml"),
    ("SandBox", "spgenericcharacters.xml"),
    ("SandBox", "spspecialcharacters.xml"),
]


def donor_characters(game=None):
    """{id: entry} from all files where the game keeps the culture's characters."""
    base = os.path.join(game or GAME, "Modules")
    result = {}
    for module, filename in DONOR_FILES:
        path = os.path.join(base, module, "ModuleData", filename)
        if not os.path.exists(path):
            continue
        for node in ET.parse(path).getroot().iter("NPCCharacter"):
            if node.get("id") and node.get("id") not in result:
                result[node.get("id")] = node
    swap_cultures(result, game)
    return result


def copy_map(game=None):
    """{vanilla id: copy id} - all Sturgian branch entries the hippogriffs need."""
    base = os.path.join(game or GAME, "Modules")
    characters = donor_characters(game)
    culture = next(c for c in ET.parse(
        os.path.join(base, "SandBoxCore", "ModuleData", "spcultures.xml")).getroot()
        if c.get("id") == DONOR_CULTURE)

    wanted = set()
    for value in culture.attrib.values():
        if str(value).startswith("NPCCharacter."):
            wanted.add(str(value).replace("NPCCharacter.", ""))
    for node in culture.iter("template"):
        name = node.get("name") or ""
        if name.startswith("NPCCharacter."):
            wanted.add(name.replace("NPCCharacter.", ""))
    # upgrade tree: from the recruit the references lead to the other troops, duplicate them too
    queue = list(wanted)
    while queue:
        tid = queue.pop()
        node = characters.get(tid)
        if node is None:
            continue
        for up in node.findall("upgrade_targets/upgrade_target"):
            nxt = up.get("id").replace("NPCCharacter.", "")
            if nxt not in wanted:
                wanted.add(nxt)
                queue.append(nxt)
    # Take only entries of the donor culture itself: mercenaries and other outsiders stay shared.
    # The entries' culture has already been rewritten by the swap (swap_cultures), check against the new one.
    owner = "Culture." + RECORD_CULTURE.get(DONOR_CULTURE, DONOR_CULTURE)
    ours = [tid for tid in sorted(wanted)
            if tid in characters and (characters[tid].get("culture") or "") == owner]
    return {tid: COPY_PREFIX + tid for tid in ours}


def groups(game=None):
    """Troop groups: (title, {id: vanilla entry}, [ids in order], {id: name})."""
    base = os.path.join(game or GAME, "Modules")
    characters = {c.get("id"): c for c in ET.parse(
        os.path.join(base, "SandBoxCore", "ModuleData", "spnpccharacters.xml")).getroot() if c.get("id")}
    cultures = {c.get("id"): c for c in ET.parse(
        os.path.join(base, "SandBoxCore", "ModuleData", "spcultures.xml")).getroot()}
    # bandits are described in the SandBox module, in a separate file
    bandits = {c.get("id"): c for c in ET.parse(
        os.path.join(base, "SandBox", "ModuleData", "bandits.xml")).getroot()
        if c.tag == "NPCCharacter" and c.get("id")}
    civilians = donor_characters(game)
    swap_cultures(characters, game)
    return [
        ("Эквестрия", characters, tree(characters, cultures[CULTURE]), NAMES),
        ("разбойники", bandits, list(bandits), BANDIT_NAMES),
        ("Чейнджлинги", characters, tree(characters, cultures["aserai"]), CHANGELING_NAMES),
        # Branches by ROSTER_OF: the tree is taken from the donor culture, the entries' culture has already
        # been rewritten at load time (swap_cultures).
        ("Грифоны", characters, tree(characters, cultures[ROSTER_OF["vlandia"]]), GRIFFON_NAMES),
        ("Олени", characters, tree(characters, cultures[ROSTER_OF["nord"]]), DEER_NAMES),
        ("Драконы", characters, tree(characters, cultures[ROSTER_OF["sturgia"]]) + ["vlandian_infantry"],
         DRAGON_NAMES),
        ("Яки", characters, tree(characters, cultures[ROSTER_OF["khuzait"]]), YAK_NAMES),
        # hippogriffs are copies of the Sturgian branch, built separately in main()
        # Civilians are searched across ALL game files: peasants and village fighters are described not in
        # spnpccharacters.xml but in templates, and until 24.09.2026 remained
        # "Aserai Peasants".
        ("мирные", civilians, sorted(civil_names(civilians)), civil_names(civilians)),
        ("знать", civilians, sorted(notable_names(civilians)), notable_names(civilians)),
        ("вожаки", civilians, sorted(leader_names(civilians)), leader_names(civilians)),
        ("наёмники", characters, sorted(merc_names(characters)), merc_names(characters)),
    ]


# These groups get no armour by tier: a trader would end up with lamellar in an empty slot.
# Mercenaries are a separate case: companies have their own vanilla look (each its own), and re-dressing them by
# our tiers would erase that difference. Only the name and race change.
NO_ARMOR_GROUPS = {"мирные", "знать", "вожаки", "наёмники"}


def troop_armor(game=None):
    """Armour of all reworked troops in order of appearance: {group: [item ids]}."""
    result = {}
    for title, characters, ids, _names in groups(game):
        ordered = []
        for tid in ids:
            for eq in characters[tid].iter("equipment"):
                if eq.get("slot") in ARMOR_SLOTS:
                    item = eq.get("id").replace("Item.", "")
                    if item not in ordered:
                        ordered.append(item)
        result[title] = ordered
    return result


# Vanilla imperial armour from weak to strong (by protection)
ARMOR = {
    "Body": ["empire_legion_b", "empire_plate_vest_armor", "imperial_lamellar",
             "lamellar_with_scale_skirt", "imperial_scale_armor"],
    "Leg": ["strapped_leather_boots", "empire_horseman_boots", "lamellar_plate_boots",
            "decorated_imperial_boots", "plated_strip_boots"],
    "Gloves": ["lordly_padded_mitten", "reinforced_padded_mitten",
               "decorated_imperial_gauntlets", "plated_strip_gauntlets",
               "lamellar_plate_gauntlets"],
    "Head": ["ironlame_nasalhelm_over_imperial_coif", "ironlame_nasalhelm_over_imperial_mail",
             "heavy_nasalhelm_over_imperial_mail", "empire_guarded_lord_helmet",
             "imperial_goggled_helmet"],
}
# Troop tier (level 6/11/16/21/26/31) -> item index in ARMOR; None - the slot is empty.
BY_TIER = {
    1: {"Body": None, "Leg": 0, "Gloves": None, "Head": None},
    2: {"Body": 0, "Leg": 1, "Gloves": 0, "Head": None},
    3: {"Body": 1, "Leg": 2, "Gloves": 1, "Head": 0},
    4: {"Body": 2, "Leg": 3, "Gloves": 2, "Head": 1},
    5: {"Body": 3, "Leg": 3, "Gloves": 3, "Head": 2},
    6: {"Body": 4, "Leg": 4, "Gloves": 4, "Head": 3},
}
ARMOR_SLOTS = ("Head", "Body", "Leg", "Gloves")


def log(*a):
    print("[troops]", *a, flush=True)


def tier_of(character):
    level = int(character.get("level") or 1)
    # troop levels 6, 11, 16, 21, 26, 31 are tiers 1..6
    return max(1, min(6, level // 5))


def tree(characters, culture):
    """All troops of the culture tree: from recruits up through the upgrades, plus militia."""
    ids = []

    def walk(tid):
        if tid in ids or tid not in characters:
            return
        ids.append(tid)
        for up in characters[tid].findall("upgrade_targets/upgrade_target"):
            walk(up.get("id").replace("NPCCharacter.", ""))

    for attr in ("basic_troop", "elite_basic_troop"):
        walk(culture.get(attr).replace("NPCCharacter.", ""))
    for attr in ("melee_militia_troop", "ranged_militia_troop",
                 "melee_elite_militia_troop", "ranged_elite_militia_troop"):
        tid = culture.get(attr).replace("NPCCharacter.", "")
        if tid not in ids and tid in characters:
            ids.append(tid)
    return ids


def set_hair_tag(node, tag):
    """Leave the troop only hairstyles with tag tag (<face><hair_tags>)."""
    face = node.find("face")
    if face is None:
        face = ET.SubElement(node, "face")
    for old in face.findall("hair_tags"):
        face.remove(old)
    tags = ET.SubElement(face, "hair_tags")
    ET.SubElement(tags, "hair_tag", name=tag)


# A kingdom's own armour: the item prefix. For the hive these are vanilla Aserai meshes with chitin
# textures and glow (tools/hive_armor.py); the geometry is vanilla, only the materials change.
# If there is our copy of a vanilla item, we put it on.
OWN_ARMOR = {"Чейнджлинги": "eq_changeling_"}
OWN_ITEMS = set()      # ids of our items, read from the built equestria_items.xml
# A test on a single troop (it was: mamluke_palace_guard) showed that the hive armour renders -
# the trouble was the empty material of the vanilla mittens, see the fallback in tools/hive_material.ps1.
# Empty string - everyone entitled wears the armour; a troop name - only that one (for new tests).
OWN_ARMOR_ONLY = ""


def dress(roster, tier, ranged, race=PONY, own=None):
    """Changes the armour of one equipment set. own - the prefix of the kingdom's own items."""
    slots = {}
    for eq in list(roster.findall("equipment")):
        slot = eq.get("slot")
        if slot in ARMOR_SLOTS or slot == "Cape":
            slots[slot] = eq.get("id", "").replace("Item.", "")
            roster.remove(eq)

    # Archers are one tier lighter than infantry: unicorns need freedom for magic.
    plan = BY_TIER[max(1, tier - 1) if ranged else tier]
    for slot in ARMOR_SLOTS:
        vanilla = slots.get(slot)
        item = None
        if vanilla:
            item = vanilla          # whatever the vanilla troop wore, it still wears
            if own and own + vanilla in OWN_ITEMS:
                item = own + vanilla    # …but if the kingdom has its own version of the item, put that on
        elif plan[slot] is not None:
            item = ARMOR[slot][plan[slot]]
        if slot == "Leg" and tier <= race["bare_tier"]:
            item = None
        if slot == "Head" and (item is None or race["no_helmet"]):
            # mane = None: the head is free (for ponies the mane and horn are the race hairstyle)
            item = race["mane"].replace("Item.", "") if race["mane"] else None
        if item:
            ET.SubElement(roster, "equipment", {"slot": slot, "id": "Item." + item})
    if race["tail"]:
        ET.SubElement(roster, "equipment", {"slot": "Cape", "id": race["tail"]})


def looter_id(tid, race):
    """Id of the looter copy for a race; for ponies, the vanilla id."""
    return tid if race == "pony" else "eq_%s_%s" % (race, tid)


# Vanilla looter party templates: each has one stack of the vanilla "looter". We rewrite them with
# our own - one stack per people, so a band has ponies, griffons and yaks at once.
BANDIT_PARTY_TEMPLATES = {
    "looters_template": (4, 36),
    "looters_quest_template": (15, 15),
}


def write_bandit_party_templates():
    races = list(LOOTER_RACES)
    body = ['<?xml version="1.0" encoding="utf-8"?>',
            "<!-- Отряды мародёров: по стопке на народ, чтобы в ватаге встречались все расы.",
            "     Файл собран tools/make_troops.py — правьте скрипт, не его. -->",
            "<MBPartyTemplates>"]
    for template, (low, high) in BANDIT_PARTY_TEMPLATES.items():
        body.append('\t<MBPartyTemplate id="%s" _replaceWhileMerging="true">' % template)
        body.append("\t\t<stacks>")
        for number, race in enumerate(races):
            # The per-stack limit is divided by the number of peoples, the remainder goes to the first: the
            # total band size stays vanilla (for the quest template it is exactly 15 - that matters there).
            extra = 1 if number < low % len(races) else 0
            extra_high = 1 if number < high % len(races) else 0
            body.append('\t\t\t<PartyTemplateStack min_value="%d" max_value="%d" troop="NPCCharacter.%s" />'
                        % (max(1, low // len(races) + extra),
                           max(1, high // len(races) + extra_high),
                           looter_id("looter", race)))
        body.append("\t\t</stacks>")
        body.append("\t</MBPartyTemplate>")
    body.append("</MBPartyTemplates>\n")
    path = os.path.join(MODULE, "ModuleData", "equestria_party_templates.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(body))
    log("записан", path)


def main():
    # Our own items (hive armour) - from the already built equestria_items.xml: make_items.py runs
    # earlier, and this list decides whether a kingdom has its own version of a vanilla item.
    items_path = os.path.join(MODULE, "ModuleData", "equestria_items.xml")
    if os.path.exists(items_path):
        OWN_ITEMS.update(i.get("id") for i in ET.parse(items_path).getroot() if i.get("id"))
        log("своих вещей в моде: %d" % len(OWN_ITEMS))
    root = ET.Element("NPCCharacters")
    missing = []
    total = 0
    civil_records = donor_characters()   # the company leaders are in them: the mercenaries' race is taken from them
    for title, characters, ids, names in groups():
        group_race = RACES.get(title, PONY)
        log(f"== {title}: {len(ids)}, раса {group_race['race']}")
        for tid in ids:
            node = copy.deepcopy(characters[tid])
            # For civilians, notables and leaders the group is shared by all kingdoms, so the race follows
            # the culture of the entry itself.
            culture = (node.get("culture") or "").replace("Culture.", "")
            race = RACES.get(CULTURE_RACE.get(culture, title), group_race) \
                if title in NO_ARMOR_GROUPS else group_race
            # A gang is of its own race (see BANDIT_RACE); looters stay ponies, their mixed-race
            # copies are made below.
            if title == "разбойники" and culture in BANDIT_RACE:
                race = RACES[BANDIT_RACE[culture]]
            # A mercenary company is of its leader's race, not of its culture (see merc_race).
            if title == "наёмники":
                race = merc_race(merc_clan(tid), civil_records) or race
            name = names.get(tid)
            if name is None:
                missing.append(tid)
                name = node.get("name", tid)
            # _replaceWhileMerging wipes all attributes of the vanilla entry - rewrite them all.
            attrs = dict(node.attrib)
            node.attrib.clear()
            node.set("id", tid)
            node.set("_replaceWhileMerging", "true")
            for key, value in attrs.items():
                if key != "id":
                    node.set(key, value)
            # the name may be a pair (Russian, English): for civilians the English is built alongside
            node.set("name", lang.loc("eq_troop_" + tid, *name) if isinstance(name, tuple)
                     else lang.loc("eq_troop_" + tid, name))
            node.set("race", race["race"])
            if race["hair_tag"]:
                set_hair_tag(node, race["hair_tag"])
            ranged = node.get("default_group") in ("Ranged", "HorseArcher")
            tier = tier_of(node)
            if title not in NO_ARMOR_GROUPS:
                own = OWN_ARMOR.get(title)
                if own and OWN_ARMOR_ONLY and tid != OWN_ARMOR_ONLY:
                    own = None          # under test, only one troop gets its own armour
                for roster in node.iter("EquipmentRoster"):
                    dress(roster, tier, ranged, race, own)
            root.append(node)
            total += 1
            log(f"  {tid}: {name} (ступень {tier}{', стрелок' if ranged else ''})")

    # ---- Hippogriffs: copies of the Sturgian entries with their own race and names (see copy_map)
    characters = donor_characters()
    mapping = copy_map()
    deer = RACES[CULTURE_RACE[COPY_CULTURE]]
    log(f"== копии стургийской ветки ({COPY_CULTURE}): {len(mapping)} записей, раса {deer['race']}")
    for tid, new_id in mapping.items():
        node = copy.deepcopy(characters[tid])
        attrs = dict(node.attrib)
        node.attrib.clear()
        node.set("id", new_id)
        for key, value in attrs.items():
            if key != "id":
                node.set(key, value)
        node.set("culture", "Culture." + COPY_CULTURE)
        node.set("race", deer["race"])
        # Name: troops get a lore one, civilians - by role and kingdom, townsfolk keep the vanilla one
        # (it is shared by all cultures: "Townsman", "Tavern Keeper").
        if tid in HIPPOGRIFF_NAMES:
            node.set("name", lang.loc("eq_troop_" + new_id, HIPPOGRIFF_NAMES[tid]))
            set_hair_tag(node, deer["hair_tag"])
            ranged = node.get("default_group") in ("Ranged", "HorseArcher")
            for roster in node.iter("EquipmentRoster"):
                dress(roster, tier_of(node), ranged, deer)
        else:
            found = civil_role(tid)
            role = CIVIL_ROLES[found[0]] if found else NOTABLE_ROLES.get(node.get("occupation"))
            if role:
                ru_of, en_of = CIVIL_OF[COPY_CULTURE]
                node.set("name", lang.loc("eq_troop_" + new_id, "%s %s" % (role[0], ru_of),
                                          "%s %s" % (role[1], en_of)))
            set_hair_tag(node, deer["hair_tag"])
        # upgrade references lead to the same kind of copies, otherwise the tree goes off to the yaks
        for up in node.findall("upgrade_targets/upgrade_target"):
            target = up.get("id").replace("NPCCharacter.", "")
            if target in mapping:
                up.set("id", "NPCCharacter." + mapping[target])
        root.append(node)
        total += 1

    # ---- Looters of all peoples: each race has its own copy of the entry
    bandits = {c.get("id"): c for c in ET.parse(
        os.path.join(GAME, "Modules", "SandBox", "ModuleData", "bandits.xml")).getroot()
        if c.tag == "NPCCharacter" and c.get("id")}
    made = 0
    for race, upgrades in LOOTER_RACES.items():
        if race == "pony":
            continue          # ponies stay on the vanilla ids, their entries are already built above
        for tid in LOOTER_TROOPS:
            node = copy.deepcopy(bandits[tid])
            attrs = dict(node.attrib)
            node.attrib.clear()
            node.set("id", looter_id(tid, race))
            for key, value in attrs.items():
                if key != "id":
                    node.set(key, value)
            node.set("race", race)
            node.set("name", lang.loc("eq_troop_" + looter_id(tid, race), BANDIT_NAMES[tid]))
            set_hair_tag(node, LOOTER_HAIR[race])
            # upgrade into infantry of the same culture, otherwise the bandit changes nationality
            for up in node.findall("upgrade_targets/upgrade_target"):
                target = up.get("id").replace("NPCCharacter.", "")
                if target in upgrades:
                    up.set("id", "NPCCharacter." + upgrades[target])
            root.append(node)
            made += 1
            total += 1
    log(f"== мародёры: {made} копий на {len(LOOTER_RACES) - 1} народов")
    write_bandit_party_templates()

    if missing:
        log("!!! нет имени для:", ", ".join(missing))
    ET.indent(root, space="\t")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write("<!-- Войска под пони: армия Эквестрии, разбойники и рой чейнджлингов.\n"
                "     Файл собран tools/make_troops.py — правьте скрипт, не его. -->\n")
        f.write(ET.tostring(root, encoding="unicode"))
        f.write("\n")
    lang.write(os.path.join(MODULE, "ModuleData"), "eq_troops", log)
    lang.report(log)
    log(f"записан {OUT}: войск {total}")


if __name__ == "__main__":
    main()
