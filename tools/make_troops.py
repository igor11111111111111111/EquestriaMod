# Войска под пони: ванильное имперское дерево (армия Эквестрии), все разбойники
# и дерево асераев — рой чейнджлингов (своя раса).
#
#   py -3 tools\make_troops.py [папка Module] [папка игры]
#
# Id войск остаются ванильными (imperial_recruit и т.д.): на них ссылаются шаблоны отрядов лордов,
# ополчение, караваны и дерево улучшений. Каждая запись переписывается целиком — атрибут
# _replaceWhileMerging="true" заставляет игру выбросить ванильную запись с тем же id
# (MBObjectManager.MergeElementAttributes) и взять нашу.
#
# Что меняется:
#   - имя по лору (Солнечная гвардия, единороги-стрелки, пегасы, Ночная стража Луны);
#   - раса — пони;
#   - броня: ванильная вещь остаётся своей; если слот пуст, подставляется вещь по ступени войска.
#     Раньше тут подменялись пони-версии (eq_pony_<id>) — своей брони в моде больше нет, все расы
#     подогнаны под ванильного человека и носят обычные вещи игры;
#   - без шлема на голове грива, в слоте накидки хвост.
# Оружие, кони, навыки и улучшения — ванильные.
import copy
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lang  # noqa: E402

# Аргументы читаем только при прямом запуске: модуль импортируют и из Blender
# (adapt_armor.py -> armor_catalog.py), а там в sys.argv совсем другое.
ARGS = sys.argv[1:] if __name__ == "__main__" else []
MODULE = ARGS[0] if ARGS else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
GAME = ARGS[1] if len(ARGS) > 1 else \
    r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
VANILLA = os.path.join(GAME, "Modules", "SandBoxCore", "ModuleData")
# ПОСЛЕ этого скрипта запускать tools/replace_mounts.py: кони в слоте Horse → свитки полёта по уровню (10.10.2026).
OUT = os.path.join(MODULE, "ModuleData", "equestria_troops.xml")

CULTURE = "empire"
MANE = None  # грива и рог — причёска (make_pony_manes.py), слот шлема у пони свободен
TAIL = None  # хвост — часть тела, его вешает код (src/EquestriaBodyParts.cs), слот плаща свободен

# Раса группы и её части тела-предметы (гребень — в слот шлема, крылья с хвостом — в слот плаща).
# Чейнджлинги шлемов не носят: рог и гребень — их лицо. Группы без записи — пони.
# bare_tier — до какой ступени войско ходит босиком (у чейнджлингов дыры на ногах — их видно).
# hair_tag — какие причёски расы можно войску (Bald — лысые трутни: у них гребень-предмет).
# Предмета-гребня (eq_changeling_crest) больше нет: он был у старой модели, а у новой
# (tools/make_changeling_model.py) рог и уши — часть головы. Слот шлема остаётся пустым,
# трутни ходят с непокрытой головой, как и раньше.
RACES = {
    "Чейнджлинги": {"race": "changeling", "mane": None,
                    "tail": None, "no_helmet": True, "bare_tier": 1,
                    "hair_tag": "Bald"},
    # Остальные державы: раса своя, причёска — своя же (гребень, рога, грива). Без записи войско
    # получило бы гриву пони: в скинах такой причёски у чужой расы нет, и голова осталась бы голой.
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

# Имена по лору. Пехота — Королевская стража Селестии, стрелки — единороги, знатная ветка —
# пегасы лётной академии и Вандерболты, конные лучники — Ночная стража Луны.
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

# Разбойники — по бандам из world_data.MINOR_CLANS. Все пока пони: алмазные псы, яки и прочие
# народы появятся вместе со своими расами.
# Рой королевы Кризалис: трутни, охотники, стражи улья.
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

# Грифоны Грифонстоуна (ванильные ХУЗАИТЫ — ветка верховых стрелков и всадников: грифоны летают,
# и конная держава им подходит больше пешей вландийской; поменялись с яками 10.10.2026, см.
# ROSTER_OF): скалы, гнёзда и Идол Бориаса. Конные ветки — лётные.
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

# Гиппогрифы горы Арис и морские пони Сиквестрии: КОПИИ стургийских записей (приставка COPY_PREFIX,
# см. раздел «копии стургийской ветки» ниже) — пешая северная ветка; поменялись с оленями 10.10.2026
# (ROSTER_OF). Гарпуны, рифы и Жемчужина; конная ветка — лётная.
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

# Драконы вулканических земель (ванильная ВЛАНДИЯ — ветка с арбалетами и рыцарями; поменялись
# с яками 10.10.2026, ROSTER_OF): Скипетр, Состязание и лорд драконов. Конные ветки — лётные.
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
    "vlandian_infantry": "Пехотинец Драконьих Земель",   # в дерево улучшений не входит, но в игре есть
}

# Яки Якьякистана (ванильная СТУРГИЯ — пешая северная ветка; поменялись с драконами 10.10.2026,
# ROSTER_OF): ледники, прямота и умение крушить.
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
    "sturgian_horse_raider": "Налётчик тундры",     # яки пешие: бывший всадник
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

# Олени Олении (ванильная БАТТАНИЯ — пешая лесная ветка; у нордов в ванили войск нет, раньше
# Оления брала копии стургийских записей, с 10.10.2026 копии ушли гиппогрифам, см. ROSTER_OF).
# Лес, лук и Совет Семи; конная ветка — верховая, олени не летают.
DEER_NAMES = {
    "battanian_volunteer": "Молодой олень",
    "battanian_clanwarrior": "Лесной боец",
    "battanian_trained_warrior": "Оленийский воин",
    "battanian_picked_warrior": "Отборный воин Олении",
    "battanian_oathsworn": "Гвардеец Оленьей Рощи",
    "battanian_scout": "Оленийский разведчик",
    "battanian_horseman": "Рогатый налётчик",          # олени пешие: бывший всадник
    "battanian_woodrunner": "Лесовик",
    "battanian_raider": "Оленийский разбойник",
    "battanian_falxman": "Копейщик чащи",
    "battanian_veteran_falxman": "Тяжёлый копейщик Олении",
    "battanian_skirmisher": "Метатель дротиков Олении",
    "battanian_veteran_skirmisher": "Бывалый метатель дротиков Олении",
    "battanian_wildling": "Рогатый таран",
    "battanian_mounted_skirmisher": "Застрельщик Олении",  # олени пешие: бывший верховой
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

# Раса банды. Ванильная игра уже связала каждую банду с державой: её разбойники улучшаются в
# войска этой культуры (лесные — в баттанские, горные — во вландийские и так далее). Берём ту же
# связку — иначе при улучшении разбойник менял бы народность прямо в отряде.
# Мародёры и дезертиры (культура looters) — исключение: это сброд со всей карты, и они собраны
# из всех народов сразу (см. LOOTER_RACES ниже).
COPY_PREFIX = "eq_hg_"     # приставка id у копий стургийской ветки — они у гиппогрифов (см. ниже)

BANDIT_RACE = {
    "sea_raiders": "Драконы",        # улучшаются в стургийские войска
    "mountain_bandits": "Грифоны",   # во вландийские
    "forest_bandits": "Гиппогрифы",  # в баттанские
    "desert_bandits": "Чейнджлинги",  # в асерайские
    "steppe_bandits": "Яки",         # в хузаитские
}

# Мародёры бывают всякие: на каждую расу своя копия записи, а в шаблоне отряда (equestria_party
# _templates.xml) они стоят рядом — в одной ватаге встречаются пони, грифоны, яки и прочие.
# Пони остаются на ванильных id, остальным даётся приставка.
# Значение — во что разбойник улучшается: ванильный мародёр уходит в имперскую пехоту, и копия
# должна уходить в такую же пехоту СВОЕЙ культуры, иначе раса сменится при улучшении.
LOOTER_RACES = {
    "pony": {},
    # ветки по ROSTER_OF: грифоны — хузаиты, драконы — вландийцы, яки — стургийцы,
    # олени — баттанийцы, гиппогрифы — копии стургийцев
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
    # Мародёры
    "looter": "Мародёр",
    "deserter": "Дезертир",
    "mounted_pillager": "Конный грабитель",
    "mounted_ransacker": "Конный налётчик",
    # Воинство Короля Шторма (морские налётчики)
    "sea_raiders_bandit": "Пират Короля Шторма",
    "sea_raiders_raider": "Абордажник Короля Шторма",
    "sea_raiders_chief": "Капитан Короля Шторма",
    "sea_raiders_boss": "Адмирал Короля Шторма",
    # Алмазные Псы (горные разбойники)
    "mountain_bandits_bandit": "Горный старатель",
    "mountain_bandits_raider": "Громила Алмазных Псов",
    "mountain_bandits_chief": "Вожак Алмазных Псов",
    "mountain_bandits_boss": "Король Алмазных Псов",
    # Тимбервульфы (лесные разбойники)
    "forest_bandits_bandit": "Лесной бродяга",
    "forest_bandits_raider": "Вольный стрелок Вечнодикого леса",
    "forest_bandits_chief": "Атаман Тимбервульфов",
    "forest_bandits_boss": "Хозяин Вечнодикого леса",
    # Стервятники Бесплодных Земель (пустынные разбойники)
    "desert_bandits_bandit": "Бродяга Бесплодных Земель",
    "desert_bandits_raider": "Пустынный налётчик",
    "desert_bandits_chief": "Стервятник",
    "desert_bandits_boss": "Главарь Стервятников",
    # Бизоньи Набеги (степные разбойники)
    "steppe_bandits_bandit": "Степной разбойник",
    "steppe_bandits_raider": "Бизоний налётчик",
    "steppe_bandits_chief": "Вожак набега",
    "steppe_bandits_boss": "Вождь Бизоньих Набегов",
}


# Мирный люд: караванщики, торговцы и крестьяне. В деревьях войск их нет, но в энциклопедии и в
# отрядах они видны — и до сих пор звались по-ванильному («Асерайский крестьянин»). Имя строим
# из роли и державы, английский пишем рядом: по словарю такие связки не собрать.
CIVIL_ROLES = {
    "caravan_master": ("Караванщик", "Caravan Master"),
    "armed_trader": ("Вооружённый торговец", "Armed Trader"),
    "caravan_guard": ("Охранник каравана", "Caravan Guard"),
    "veteran_caravan_guard": ("Бывалый охранник каравана", "Veteran Caravan Guard"),
    "village_woman": ("Крестьянка", "Peasant Woman"),
    "villager": ("Крестьянин", "Peasant"),
    "fighter": ("Деревенский боец", "Village Fighter"),
}
# Чья это держава — по культуре записи
CIVIL_OF = {
    "empire": ("Эквестрии", "of Equestria"),
    "vlandia": ("Грифонстоуна", "of Griffonstone"),
    "battania": ("горы Арис", "of Mount Aris"),
    "sturgia": ("Драконьих Земель", "of the Dragon Lands"),
    "khuzait": ("Якьякистана", "of Yakyakistan"),
    "aserai": ("улья", "of the Hive"),
    "nord": ("Олении", "of Olenia"),
}
# Раса и причёска по культуре — для мирных, где группа общая на все державы
CULTURE_RACE = {"aserai": "Чейнджлинги", "vlandia": "Грифоны", "battania": "Гиппогрифы",
                "sturgia": "Драконы", "khuzait": "Яки", "nord": "Олени"}


# Знать поселений: заготовки внешности для торговцев, старост и главарей банд. В энциклопедии
# они видны, а звались по ванильным фракциям («Осторожный имперский торговец»). Личность из
# ванильного названия (осторожный, хитрый, мятежный) не переносим: в игре у нотабля своё имя,
# а заготовок на одну роль по нескольку — различать их игроку незачем.
NOTABLE_ROLES = {
    "Merchant": ("Торговец", "Merchant"),
    "Preacher": ("Проповедник", "Preacher"),
    "Artisan": ("Ремесленник", "Artisan"),
    "GangLeader": ("Главарь банды", "Gang Leader"),
    "RuralNotable": ("Сельский староста", "Rural Notable"),
    "Headman": ("Деревенский голова", "Headman"),
}


def notable_names(characters):
    """{id: (русское, английское)} для знати поселений всех культур."""
    result = {}
    for cid, node in characters.items():
        role = NOTABLE_ROLES.get(node.get("occupation"))
        culture = (node.get("culture") or "").replace("Culture.", "")
        if role and culture in CIVIL_OF:
            ru_of, en_of = CIVIL_OF[culture]
            result[cid] = ("%s %s" % (role[0], ru_of), "%s %s" % (role[1], en_of))
    return result


# Войска наёмных рот: у каждого мелкого клана своё деревце <клан>_tier_1..3. Вожаков мы
# переименовали давно (leader_names), а войска остались кальрадийскими: рота, ставшая у нас
# Небесными пиратами, набирала «Новичков „Кабанов“» (видно в игре 25.09.2026). Имена даём по лору
# самой роты — он в world_data.MINOR_CLANS, — по три ступени на роту.
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
    """Клан по id войска наёмников (skolderbrotva_tier_2 -> skolderbrotva); иначе None."""
    if "_tier_" not in cid:
        return None
    clan = cid[:cid.index("_tier_")]
    return clan if clan in MERC_NAMES else None


def merc_names(characters):
    """{id: (русское, английское)} для войск наёмных рот."""
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
    """Раса роты — та же, что у её вожака.

    У трети рот культура войск и культура вожака РАЗНЫЕ: вольные клинки Клюгтауна записаны на
    нордскую культуру (у нас это Оления), а их вожак — стургийский, то есть дракон. Брать расу по
    культуре самого войска нельзя: в роте драконов ходили бы олени.
    """
    for cid, node in leaders.items():
        if cid.startswith("spc_" + clan + "_leader_"):
            culture = (node.get("culture") or "").replace("Culture.", "")
            return RACES.get(CULTURE_RACE.get(culture, ""), None)
    return None


def leader_names(characters):
    """{id: (русское, английское)} для вожаков наёмных отрядов и банд (spc_<клан>_leader_N)."""
    import world_data  # noqa: E402 — таблица кланов наёмников, там же их названия в моде
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
    """(роль, культура) для записи вида villager_empire; иначе None.

    Хвост обязан быть именно названием культуры: id вроде villager_child_sturgia — это подросток
    и ребёнок, у них своё ванильное имя («Villager child»), державу к нему приписывать незачем.
    """
    for role in CIVIL_ROLES:
        if cid.startswith(role + "_") and cid[len(role) + 1:] in CIVIL_OF:
            culture = cid[len(role) + 1:]
            return role, swapped_culture(cid, culture)   # villager_vlandia теперь у драконов
    return None


def civil_names(characters):
    """{id: (русское имя, английское)} для мирных записей всех культур."""
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


# ---------------------------------------------------------------- обмен ветками
# Державы остаются при своих культурах (vlandia = Грифонстоун, khuzait = Якьякистан, sturgia =
# Драконьи Земли, battania = гора Арис, nord = Оления; make_world.RACE_BY_CULTURE), а ванильную
# ВЕТКУ — войска, ополчение, горожан, крестьян, знать и их одежду — каждая берёт у другой
# (10.10.2026): летающим грифонам и драконам — конные хузаиты и вландийцы, пешим якам и оленям —
# стургийцы и баттанийцы, гиппогрифам — копии стургийской ветки (у нордов в ванили войск нет,
# поэтому копии нужны в любом случае). Для этого у ванильных записей ветки переписывается
# культура (khuzait_nomad → Culture.vlandia), а make_world (FULL_CULTURE_FROM) даёт культуре
# ссылки её донора. Наёмные роты (company_of_the_boar и прочие, не входящие в дерево культуры)
# не трогаем: их раса — по вожаку.
ROSTER_OF = {"vlandia": "khuzait", "khuzait": "sturgia", "sturgia": "vlandia",
             "nord": "battania", "battania": "sturgia"}
# Культура, которая берёт КОПИИ ветки (COPY_PREFIX): у стургийской ветки два хозяина.
COPY_CULTURE = "battania"
# Куда уходят ванильные записи ветки: {ванильная культура ветки: наша культура}
RECORD_CULTURE = {roster: culture for culture, roster in ROSTER_OF.items() if culture != COPY_CULTURE}


def swapped_culture(cid, culture, roster_ids=None):
    """Культура записи после обмена (khuzait_nomad → vlandia); чужие записи не меняются."""
    new = RECORD_CULTURE.get(culture)
    if not new:
        return culture
    if culture in cid or (roster_ids is not None and cid in roster_ids.get(culture, ())):
        return new
    return culture


def swap_cultures(characters, game=None):
    """Переписывает культуру у записей обмениваемых веток (на месте).

    Запись считается своей для ветки, если в id есть слово культуры (vlandian_*, villager_khuzait)
    или она входит в дерево улучшений культуры (varyag, druzhinnik — без слова в id).
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


# ---------------------------------------------------------------- копии стургийской ветки
# Стургийская ветка нужна двум державам: якам (ванильные записи, культура khuzait) и гиппогрифам
# (COPY_CULTURE). Поэтому для гиппогрифов делаются СВОИ копии всех записей, на которые смотрит
# культура-донор: id с приставкой COPY_PREFIX, культура battania, раса hippogriff. Ссылки в
# культуре переписывает make_world по этой же карте (copy_map). Раньше так жила Оления (у нордов
# в ванили ни войск, ни горожан); с 10.10.2026 олени на баттанийской ветке.
DONOR_CULTURE = "sturgia"


# Где лежат записи, на которые смотрит культура: войска и горожане в одном файле, шаблоны
# крестьян и горожанок — во втором, стража — в третьем, знать и главы деревень — в четвёртом.
DONOR_FILES = [
    ("SandBoxCore", "spnpccharacters.xml"),
    ("SandBoxCore", "spnpccharactertemplates.xml"),
    ("SandBox", "spgenericcharacters.xml"),
    ("SandBox", "spspecialcharacters.xml"),
]


def donor_characters(game=None):
    """{id: запись} из всех файлов, где игра держит персонажей культуры."""
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
    """{ванильный id: id копии} — все записи стургийской ветки, которые нужны гиппогрифам."""
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
    # дерево улучшений: от рекрута ссылки уходят на остальные войска, их тоже дублируем
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
    # Берём только записи самой культуры-донора: наёмники и прочие чужаки остаются общими.
    # Культура у записей уже переписана обменом (swap_cultures), сверяемся с новой.
    owner = "Culture." + RECORD_CULTURE.get(DONOR_CULTURE, DONOR_CULTURE)
    ours = [tid for tid in sorted(wanted)
            if tid in characters and (characters[tid].get("culture") or "") == owner]
    return {tid: COPY_PREFIX + tid for tid in ours}


def groups(game=None):
    """Группы войск: (название, {id: ванильная запись}, [id по порядку], {id: имя})."""
    base = os.path.join(game or GAME, "Modules")
    characters = {c.get("id"): c for c in ET.parse(
        os.path.join(base, "SandBoxCore", "ModuleData", "spnpccharacters.xml")).getroot() if c.get("id")}
    cultures = {c.get("id"): c for c in ET.parse(
        os.path.join(base, "SandBoxCore", "ModuleData", "spcultures.xml")).getroot()}
    # разбойники описаны в модуле SandBox, отдельным файлом
    bandits = {c.get("id"): c for c in ET.parse(
        os.path.join(base, "SandBox", "ModuleData", "bandits.xml")).getroot()
        if c.tag == "NPCCharacter" and c.get("id")}
    civilians = donor_characters(game)
    swap_cultures(characters, game)
    return [
        ("Эквестрия", characters, tree(characters, cultures[CULTURE]), NAMES),
        ("разбойники", bandits, list(bandits), BANDIT_NAMES),
        ("Чейнджлинги", characters, tree(characters, cultures["aserai"]), CHANGELING_NAMES),
        # Ветки по ROSTER_OF: дерево берём у культуры-донора, культура у записей уже
        # переписана при загрузке (swap_cultures).
        ("Грифоны", characters, tree(characters, cultures[ROSTER_OF["vlandia"]]), GRIFFON_NAMES),
        ("Олени", characters, tree(characters, cultures[ROSTER_OF["nord"]]), DEER_NAMES),
        ("Драконы", characters, tree(characters, cultures[ROSTER_OF["sturgia"]]) + ["vlandian_infantry"],
         DRAGON_NAMES),
        ("Яки", characters, tree(characters, cultures[ROSTER_OF["khuzait"]]), YAK_NAMES),
        # гиппогрифы — копии стургийской ветки, собираются отдельно в main()
        # Мирные ищем по ВСЕМ файлам игры: крестьяне и деревенские бойцы описаны не в
        # spnpccharacters.xml, а в шаблонах, и до 24.09.2026 оставались «Асерайскими крестьянами».
        ("мирные", civilians, sorted(civil_names(civilians)), civil_names(civilians)),
        ("знать", civilians, sorted(notable_names(civilians)), notable_names(civilians)),
        ("вожаки", civilians, sorted(leader_names(civilians)), leader_names(civilians)),
        ("наёмники", characters, sorted(merc_names(characters)), merc_names(characters)),
    ]


# Этим группам броню по ступеням не выдаём: у торговца в пустом слоте оказался бы ламелляр.
# Наёмники — отдельный случай: у рот свой ванильный облик (у каждой своя), и переодевать их по
# нашим ступеням значит стереть эту разницу. Меняем только имя и расу.
NO_ARMOR_GROUPS = {"мирные", "знать", "вожаки", "наёмники"}


def troop_armor(game=None):
    """Броня всех переделываемых войск по порядку появления: {группа: [id вещей]}."""
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


# Ванильная имперская броня от слабой к сильной (по защите)
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
# Ступень войска (уровень 6/11/16/21/26/31) -> номер вещи в ARMOR; None — слот пустой.
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
    # уровни войск 6, 11, 16, 21, 26, 31 — ступени 1..6
    return max(1, min(6, level // 5))


def tree(characters, culture):
    """Все войска дерева культуры: от рекрутов вверх по улучшениям, плюс ополчение."""
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
    """Оставить войску только причёски с тегом tag (<face><hair_tags>)."""
    face = node.find("face")
    if face is None:
        face = ET.SubElement(node, "face")
    for old in face.findall("hair_tags"):
        face.remove(old)
    tags = ET.SubElement(face, "hair_tags")
    ET.SubElement(tags, "hair_tag", name=tag)


# Своя броня у державы: приставка предмета. У улья это ванильные асерайские меши с хитиновыми
# текстурами и свечением (tools/hive_armor.py); геометрия ванильная, меняются только материалы.
# Если для ванильной вещи есть наша копия — надеваем её.
OWN_ARMOR = {"Чейнджлинги": "eq_changeling_"}
OWN_ITEMS = set()      # id наших вещей, читается из собранного equestria_items.xml
# Проверка на одном войске (было: mamluke_palace_guard) показала, что броня улья рисуется —
# беда была в пустом материале ванильных рукавиц, см. fallback в tools/hive_material.ps1.
# Пустая строка — броню носят все, кому положено; имя войска — только оно (для новых проверок).
OWN_ARMOR_ONLY = ""


def dress(roster, tier, ranged, race=PONY, own=None):
    """Меняет броню одного набора снаряжения. own — приставка своих вещей державы."""
    slots = {}
    for eq in list(roster.findall("equipment")):
        slot = eq.get("slot")
        if slot in ARMOR_SLOTS or slot == "Cape":
            slots[slot] = eq.get("id", "").replace("Item.", "")
            roster.remove(eq)

    # Стрелки легче пехоты на одну ступень: единорогам нужна свобода для магии.
    plan = BY_TIER[max(1, tier - 1) if ranged else tier]
    for slot in ARMOR_SLOTS:
        vanilla = slots.get(slot)
        item = None
        if vanilla:
            item = vanilla          # что ванильное войско носило, то и носит
            if own and own + vanilla in OWN_ITEMS:
                item = own + vanilla    # …но если у державы есть своя версия вещи, надеваем её
        elif plan[slot] is not None:
            item = ARMOR[slot][plan[slot]]
        if slot == "Leg" and tier <= race["bare_tier"]:
            item = None
        if slot == "Head" and (item is None or race["no_helmet"]):
            # mane = None: голова свободна (у пони грива и рог — причёска расы)
            item = race["mane"].replace("Item.", "") if race["mane"] else None
        if item:
            ET.SubElement(roster, "equipment", {"slot": slot, "id": "Item." + item})
    if race["tail"]:
        ET.SubElement(roster, "equipment", {"slot": "Cape", "id": race["tail"]})


def looter_id(tid, race):
    """id копии мародёра для расы; у пони — ванильный id."""
    return tid if race == "pony" else "eq_%s_%s" % (race, tid)


# Ванильные шаблоны отрядов мародёров: в каждом одна стопка ванильного «looter». Переписываем их
# своими — по стопке на народ, поэтому в ватаге оказываются и пони, и грифоны, и яки разом.
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
            # Предел на стопку делим на число народов, остаток отдаём первой: общий размер
            # ватаги остаётся ванильным (у квестового шаблона он ровно 15 — там это важно).
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
    # Свои вещи (броня улья) — из уже собранного equestria_items.xml: make_items.py запускается
    # раньше, и по этому списку решается, есть ли у державы своя версия ванильной вещи.
    items_path = os.path.join(MODULE, "ModuleData", "equestria_items.xml")
    if os.path.exists(items_path):
        OWN_ITEMS.update(i.get("id") for i in ET.parse(items_path).getroot() if i.get("id"))
        log("своих вещей в моде: %d" % len(OWN_ITEMS))
    root = ET.Element("NPCCharacters")
    missing = []
    total = 0
    civil_records = donor_characters()   # в них лежат вожаки рот: по ним берём расу наёмников
    for title, characters, ids, names in groups():
        group_race = RACES.get(title, PONY)
        log(f"== {title}: {len(ids)}, раса {group_race['race']}")
        for tid in ids:
            node = copy.deepcopy(characters[tid])
            # У мирных, знати и вожаков группа общая на все державы, поэтому раса — по культуре
            # самой записи.
            culture = (node.get("culture") or "").replace("Culture.", "")
            race = RACES.get(CULTURE_RACE.get(culture, title), group_race) \
                if title in NO_ARMOR_GROUPS else group_race
            # Банда — своей расы (см. BANDIT_RACE); мародёры остаются пони, их разноплемённые
            # копии делаются ниже.
            if title == "разбойники" and culture in BANDIT_RACE:
                race = RACES[BANDIT_RACE[culture]]
            # Наёмная рота — расы своего вожака, а не своей культуры (см. merc_race).
            if title == "наёмники":
                race = merc_race(merc_clan(tid), civil_records) or race
            name = names.get(tid)
            if name is None:
                missing.append(tid)
                name = node.get("name", tid)
            # _replaceWhileMerging сносит все атрибуты ванильной записи — переписываем их все.
            attrs = dict(node.attrib)
            node.attrib.clear()
            node.set("id", tid)
            node.set("_replaceWhileMerging", "true")
            for key, value in attrs.items():
                if key != "id":
                    node.set(key, value)
            # имя бывает парой (русское, английское): у мирных английский собран рядом
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
                    own = None          # на проверке своя броня только у одного войска
                for roster in node.iter("EquipmentRoster"):
                    dress(roster, tier, ranged, race, own)
            root.append(node)
            total += 1
            log(f"  {tid}: {name} (ступень {tier}{', стрелок' if ranged else ''})")

    # ---- Гиппогрифы: копии стургийских записей со своей расой и именами (см. copy_map)
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
        # Имя: войскам — лорное, мирным — по роли и державе, горожанам оставляем ванильное
        # (оно общее для всех культур: «Горожанин», «Трактирщик»).
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
        # ссылки на улучшения ведут на такие же копии, иначе дерево уходит к якам
        for up in node.findall("upgrade_targets/upgrade_target"):
            target = up.get("id").replace("NPCCharacter.", "")
            if target in mapping:
                up.set("id", "NPCCharacter." + mapping[target])
        root.append(node)
        total += 1

    # ---- Мародёры всех народов: на каждую расу своя копия записи
    bandits = {c.get("id"): c for c in ET.parse(
        os.path.join(GAME, "Modules", "SandBox", "ModuleData", "bandits.xml")).getroot()
        if c.tag == "NPCCharacter" and c.get("id")}
    made = 0
    for race, upgrades in LOOTER_RACES.items():
        if race == "pony":
            continue          # пони остаются на ванильных id, их записи уже собраны выше
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
            # улучшение — в пехоту своей же культуры, иначе разбойник сменит народность
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
