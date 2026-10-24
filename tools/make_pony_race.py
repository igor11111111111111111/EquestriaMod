# Генерирует расы "pony", "changeling" и "deer" из ванильной человеческой расы Bannerlord
# (как делают расы в The Old Realms):
#   ModuleData/pony_skins.xml        — <race id="pony">: 10 skin-вариантов с мешами Twilight,
#                                      <race id="changeling"> и <race id="deer">: то же со своими мешами
#   ModuleData/pony_monsters.xml     — pony, pony_child, pony_settlement(_slow/_fast) и то же для остальных рас
#   ModuleData/pony_action_sets.xml  — as_pony_* на основе всех as_human_* (чейнджлинг двигается так же)
#   ModuleData/project.mbproj        — регистрация skin / monster / action_set для движка
#
# py tools/make_pony_race.py <папка Modules игры> <папка Module мода>
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
MATERIAL = "eq_twilight_body"  # общий материал-атлас старой пони: им же кормятся заглушки
# Новая пони (tools/make_pony_model.py, Meshy-аликорн): своя модель с рогом, гривой в голове,
# крыльями и хвостом. Прежняя Twilight осталась мешами-заглушками (MESHES выше) для рас, которые
# ждут своего импорта, и как сама пони, пока FBX новой не импортирован в редакторе.
PONY_MESHES = {
    "body_meta_mesh": "eq_pony_body",
    "body_meta_mesh_shoulders": "eq_pony_body",
    "legs_mesh": "eq_pony_legs",
    "hands_mesh": "eq_pony_gloves",
    "face_meta_mesh": "eq_pony_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
# Текстура у новой пони белая с голубыми глазами: палитра множится на неё, поэтому первый тон —
# «как в модели», остальные мягкие окрасы. Тёмные не берём: они гасят нарисованные глаза.
PONY_PALETTE = [
    "1.00, 1.00, 1.00",  # свой цвет модели — белая
    "1.00, 0.86, 0.94",  # розовая
    "0.80, 0.92, 1.00",  # голубая
    "1.00, 0.96, 0.75",  # кремовая
    "0.93, 0.80, 0.98",  # сиреневая
    "0.82, 1.00, 0.86",  # мятная
    "1.00, 0.84, 0.68",  # персиковая
    "0.78, 0.84, 1.00",  # синеватая
    "0.88, 0.88, 0.92",  # серая
    "0.72, 0.70, 0.78",  # тёмно-серая
]
# Причёска новой пони — её вшитая волнистая грива (eq_pony_hair): единственная, зато на ней работает
# цвет волос из окна внешности (материал eq_pony_hair на ванильном шейдере волос,
# tools/pony_material.ps1). Рог — отдельная часть тела (eq_pony_horn), как хвост и крылья: его вешает
# на скелет src/EquestriaBodyParts.cs, причёской он не выбирается.
PONY_MANE = ["eq_pony_hair"]
# Цветов ровно 24 и все разные: окно внешности рисует два ряда по 12, и с 12 цветами нижний ряд
# повторял верхний. Шейдер волос выбеливает светлое, поэтому тона насыщенные; верхний ряд —
# яркие «мультяшные», нижний — приглушённые и природные.
PONY_MANE_COLORS = [
    "0.85, 0.20, 0.55", "0.45, 0.20, 0.75", "0.15, 0.30, 0.85", "0.10, 0.60, 0.85",
    "0.05, 0.65, 0.60", "0.15, 0.70, 0.30", "0.60, 0.80, 0.15", "0.90, 0.75, 0.10",
    "0.95, 0.50, 0.10", "0.85, 0.15, 0.15", "0.95, 0.55, 0.65", "0.65, 0.45, 0.90",
    "0.55, 0.12, 0.30", "0.25, 0.12, 0.45", "0.10, 0.18, 0.50", "0.08, 0.35, 0.45",
    "0.10, 0.35, 0.25", "0.40, 0.35, 0.10", "0.55, 0.30, 0.08", "0.35, 0.18, 0.08",
    "0.75, 0.70, 0.60", "0.50, 0.50, 0.55", "0.20, 0.20, 0.24", "0.06, 0.06, 0.08",
]
PONY_MANE_TAG = "PonyMane"   # тот же тег, что у старых грив: на него завязаны войска и мир (make_troops, make_world)
# Новая пони (tools/make_pony_model.py, Meshy-аликорн): своя модель с рогом, гривой в голове,
# крыльями и хвостом. Прежняя Twilight осталась мешами-заглушками (MESHES выше) для рас, которые
# ждут своего импорта, и как сама пони, пока FBX новой не импортирован в редакторе.
PONY_MESHES = {
    "body_meta_mesh": "eq_pony_body",
    "body_meta_mesh_shoulders": "eq_pony_body",
    "legs_mesh": "eq_pony_legs",
    "hands_mesh": "eq_pony_gloves",
    "face_meta_mesh": "eq_pony_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
# Текстура у новой пони белая с голубыми глазами: палитра множится на неё, поэтому первый тон —
# «как в модели», остальные мягкие окрасы. Тёмные не берём: они гасят нарисованные глаза.
PONY_PALETTE = [
    "1.00, 1.00, 1.00",  # свой цвет модели — белая
    "1.00, 0.86, 0.94",  # розовая
    "0.80, 0.92, 1.00",  # голубая
    "1.00, 0.96, 0.75",  # кремовая
    "0.93, 0.80, 0.98",  # сиреневая
    "0.82, 1.00, 0.86",  # мятная
    "1.00, 0.84, 0.68",  # персиковая
    "0.78, 0.84, 1.00",  # синеватая
    "0.88, 0.88, 0.92",  # серая
    "0.72, 0.70, 0.78",  # тёмно-серая
]
# Рог — единственная «причёска» новой пони (грива вшита в голову и красится вместе с окрасом):
# на нём работает цвет волос из окна внешности (материал eq_pony_hair на ванильном шейдере
# волос, tools/pony_material.ps1). Шейдер волос выбеливает светлое — тона насыщенные.
PONY_HORN = ["eq_pony_hair"]
PONY_HORN_TAG = "PonyMane"   # тот же тег, что у старых грив: на него завязаны войска и мир (make_troops, make_world)
PONY_HORN_COLORS = [
    "0.80, 0.72, 0.55", "0.70, 0.55, 0.25", "0.55, 0.45, 0.60", "0.45, 0.60, 0.75",
    "0.75, 0.50, 0.60", "0.60, 0.65, 0.65", "0.85, 0.80, 0.70", "0.50, 0.35, 0.55",
    "0.35, 0.50, 0.70", "0.65, 0.60, 0.45", "0.80, 0.60, 0.40", "0.30, 0.30, 0.40",
]
# Особый вариант лица чейнджлингов — зелёные глаза со щелевым зрачком (Кризалис и её линия).
# Он был сделан для СТАРОЙ модели (tools/make_changeling.py, своя клетка глаз в атласе пони).
# Новая модель пришла со своим атласом, где такой клетки нет, поэтому особого лица пока нет:
# None — значит все варианты лица берут общий материал расы. Вернуть, когда нарисуем клетку
# глаз королевы в новом атласе.
CHANGELING_QUEEN_FACE = None

# Окрасы пони: множители к текстуре тела (базовая шерсть сиреневая, поэтому оттенки мягкие).
# Первая точка — 1,1,1: исходный цвет модели.
# Кьютимарки: имена своих материалов-накладок, когда они появятся в редакторе. Пустой список — оставить
# человеческие татуировки (ими удобно проверить, работает ли канал накладок на материале пони).
# Кьютимарка сделана геометрией в предмете-хвосте (convert_twilight.py): накладки движка рисуются только
# на лице, на теле их не бывает. Здесь остаются человеческие боевые раскраски для лица.
TATTOO_MATERIALS = []

COAT_PALETTE = [
    "0.93, 0.74, 0.95",  # сиреневый, как у исходной Twilight
    "1.00, 0.98, 0.95",  # белый
    "1.00, 0.78, 0.85",  # розовый
    "0.70, 0.90, 1.00",  # голубой
    "1.00, 0.95, 0.65",  # жёлтый
    "0.75, 1.00, 0.80",  # мятный
    "1.00, 0.80, 0.55",  # оранжевый
    "0.60, 0.70, 1.00",  # синий
    "0.85, 0.85, 0.88",  # серый
    "0.55, 0.50, 0.60",  # тёмно-серый
]


def write(root, name):
    ET.indent(root, space="\t")
    path = os.path.join(OUT, name)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    print("written", path)


def keep_only_empty(parent):
    """Заменить все варианты «пустыми» (без name): лысый / без бороды / без татуировки.

    Длина списка сохраняется: редактор внешности («Случайный выбор для всего») берёт случайный номер
    из человеческого диапазона, и с укороченным списком игра падала внутри движка.
    """
    children = list(parent)
    empty = next((c for c in children if not c.get("name")), None)
    if empty is None:
        return
    for i, child in enumerate(children):
        if child.get("name"):
            parent.remove(child)
            parent.insert(i, copy.deepcopy(empty))


# Чейнджлинг (tools/make_changeling_model.py): своя модель с рогом, ушами, двумя парами
# стрекозиных крыльев и хвостом; крылья и хвост вешает на скелет src/EquestriaBodyParts.cs.
# Прежнего чейнджлинга делали из меша пони (tools/make_changeling.py) — он заменён целиком,
# имена мешей те же.
# Чёрный хитин нарисован в текстуре, поэтому палитра светлая — лишь лёгкий оттенок: движок умножает
# на неё весь атлас головы, и тёмная палитра погасила бы голубые глаза и белые клыки.
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
    "0.92, 0.96, 1.00",  # холодный синеватый
    "0.95, 1.00, 0.96",  # зеленоватый
    "1.00, 0.97, 1.00",
    "0.88, 0.92, 0.98",
]

# Олениха (tools/make_deer_model.py): своя модель — длинная морда, оленьи уши, косы, рога и
# короткий хвост. Прежний олень был перекроенной пони на общем атласе; от него не осталось
# ничего, кроме имён мешей.
# Хвост — отдельный меш, его вешает на скелет src/EquestriaBodyParts.cs; рога работают
# причёской и красятся цветом волос.
# Пока FBX не импортирован в редакторе, раса сидит в NOT_IMPORTED и ходит на мешах пони.
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
# У оленихи своя текстура (assets/deer): палитра множится на неё, поэтому тона близки к белому —
# от палевого до чуть холодного, чтобы олени отличались друг от друга, но остались рыжеватыми.
DEER_PALETTE = [
    "1.00, 1.00, 1.00",  # свой цвет модели
    "1.00, 0.94, 0.86",  # палевая
    "0.88, 0.80, 0.72",  # тёмно-бурая
    "0.94, 0.90, 0.86",  # серо-бурая
    "1.00, 0.98, 0.94",  # светлая, почти белая
    "0.78, 0.72, 0.68",  # почти чёрная для такого атласа
    "1.00, 0.90, 0.78",  # рыжая
    "0.92, 0.90, 0.88",  # седая
    "0.86, 0.78, 0.70",
    "1.00, 0.96, 0.90",
]
# Косы — «причёска» оленихи, на ней работает цвет волос из окна внешности (материал eq_deer_hair
# на ванильном шейдере волос, см. tools/deer_material.ps1). Рога — отдельная часть тела в четырёх
# вариантах (10.10.2026), и выбирают их этим же списком: одна и та же коса лежит под четырьмя
# именами (копии делает tools/deer_edit_export.py), а src/EquestriaBodyParts.cs показывает рога
# с тем же номером, что у надетой косы. Список идёт по кругу: причёска 1, 5, 9… — рога 1,
# 2, 6, 10… — рога 2 и так далее; «лысая» (нулевая) — рога 1.
DEER_HAIR = ["eq_deer_hair", "eq_deer_hair_2", "eq_deer_hair_3", "eq_deer_hair_4"]
DEER_HAIR_TAG = "DeerAntlers"
DEER_HAIR_COLORS = [  # рога: от белой кости до тёмно-бурой, плюс седые тона
    "0.82, 0.74, 0.60", "0.66, 0.54, 0.38", "0.50, 0.40, 0.28", "0.36, 0.28, 0.20",
    "0.24, 0.20, 0.16", "0.74, 0.70, 0.64", "0.56, 0.52, 0.48", "0.88, 0.82, 0.70",
    "0.62, 0.46, 0.30", "0.42, 0.34, 0.26", "0.78, 0.66, 0.46", "0.30, 0.26, 0.24",
]


# Грифон (tools/make_griffon.py): орлиная голова с клювом, перьевые «уши», когтистые кисти,
# львиный хвост и крылья, растущие из рук. Крылья и хвост — отдельные меши, их вешает на скелет
# src/EquestriaBodyParts.cs; перья макушки и затылка работают причёской и красятся цветом волос.
# Палитра множится на текстуру модели, поэтому тона близки к белому: от тёплого песочного
# до холодного стального, чтобы грифоны отличались друг от друга, но оставались птицами.
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
    "1.00, 0.96, 0.88",  # палевый, обычный окрас
    "0.96, 0.86, 0.68",  # песочный
    "1.00, 0.92, 0.78",  # золотистый
    "0.88, 0.80, 0.72",  # серо-бурый
    "1.00, 1.00, 0.96",  # белый, как у полярного орла
    "0.82, 0.74, 0.66",  # тёмно-бурый
    "0.98, 0.88, 0.74",  # рыжеватый
    "0.86, 0.86, 0.84",  # стальной
    "0.94, 0.82, 0.64",  # медный
    "0.78, 0.72, 0.68",  # почти чёрный для модели такого атласа
]
GRIFFON_HAIR = None  # отдельной причёски у грифона нет — голова и уши одно целое с головой
GRIFFON_HAIR_TAG = "GriffonCrest"
GRIFFON_HAIR_COLORS = [  # перья макушки: от белого до тёмно-бурого, плюс несколько ярких
    "0.96, 0.92, 0.84", "0.86, 0.74, 0.54", "0.62, 0.50, 0.36", "0.40, 0.32, 0.24",
    "0.24, 0.20, 0.16", "0.72, 0.72, 0.70", "0.52, 0.56, 0.60", "0.90, 0.66, 0.30",
    "0.70, 0.30, 0.20", "0.34, 0.46, 0.62", "0.46, 0.58, 0.40", "0.58, 0.40, 0.56",
]
YAK = "yak"
# Своя модель яка (tools/make_yak_model.py): рога, косматая шерсть, светлая грива и кисточка
# хвоста. Габариты у модели почти человеческие, поэтому пропорции почти не правились.
# Хвост — отдельный меш, его вешает на скелет src/EquestriaBodyParts.cs; грива работает
# причёской и красится цветом волос.
# Пока FBX не импортирован в редакторе, раса сидит в NOT_IMPORTED и ходит на мешах пони.
YAK_MESHES = {
    "body_meta_mesh": "eq_yak_body",
    "body_meta_mesh_shoulders": "eq_yak_body",
    "legs_mesh": "eq_yak_legs",
    "hands_mesh": "eq_yak_gloves",
    "face_meta_mesh": "eq_yak_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
# Материал головы по расам (остальным — общий атлас пони MATERIAL): движок берёт материал лица из
# face_textures в skins, и у расы со своей текстурой он должен быть свой.
RACE_MATERIAL = {YAK: "eq_yak_body", "dragon": "eq_dragon_body",  # DRAGON объявлен ниже
                 GRIFFON: "eq_griffon_body", CHANGELING: "eq_changeling_body",
                 DEER: "eq_deer_body",
                 "hippogriff": "eq_hippogriff_body"}   # HIPPOGRIFF объявлен ниже, как и DRAGON
# У яка своя текстура шерсти (assets/yak): палитра множится на неё, поэтому тона близки к белому —
# от чуть тёплого до чуть холодного, чтобы яки отличались друг от друга, но оставались бурыми.
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
YAK_HAIR_COLORS = [  # грива: от белой и палевой до бурой и чёрной, как шерсть у настоящих яков
    "0.94, 0.90, 0.80", "0.86, 0.74, 0.52", "0.66, 0.52, 0.34", "0.44, 0.34, 0.24",
    "0.26, 0.20, 0.16", "0.74, 0.72, 0.68", "0.54, 0.52, 0.50", "0.88, 0.84, 0.76",
    "0.62, 0.44, 0.28", "0.36, 0.30, 0.26", "0.80, 0.66, 0.44", "0.20, 0.18, 0.18",
]

# Раньше державы драконов и гиппогрифов ходили обычными пони, и раса культуре не соответствовала.
# Теперь у обеих своя модель, окрас у каждой свой — в игре видно, кто есть кто.
DRAGON = "dragon"
# Свои меши дракона (tools/make_dragon.py): тело с руками, ноги, кисти, голова. Хвост и крылья
# сюда не идут — их вешает на скелет src/EquestriaBodyParts.cs, как хвост пони.
DRAGON_MESHES = {
    "body_meta_mesh": "eq_dragon_body",
    "body_meta_mesh_shoulders": "eq_dragon_body",
    "legs_mesh": "eq_dragon_legs",
    "hands_mesh": "eq_dragon_gloves",
    "face_meta_mesh": "eq_dragon_head",
    "underwear_bottom_mesh": "",
    "underwear_top_mesh": "",
}
# Рога и гребень — «причёска» дракона: единственная, зато на ней работает цвет волос из окна
# внешности (материал eq_dragon_hair на ванильном шейдере волос, см. tools/dragon_material.ps1).
# Все записи причёсок заняты ею, так что выбрать «лысого» дракона нельзя.
DRAGON_HAIR = ["eq_dragon_hair"]
DRAGON_HAIR_TAG = "DragonCrest"
# Шейдер волос сильно выбеливает светлые цвета, поэтому яркость держим пониже, чем у кожи,
# но круг тонов проходим весь: рога бывают любые.
DRAGON_HAIR_COLORS = ["%.2f, %.2f, %.2f" % colorsys.hsv_to_rgb(i / 24.0, 0.80, 0.70)
                      for i in range(24)]
# Драконы бывают всякие, поэтому у них не оттенки одного цвета, а весь круг: по 24 точкам
# градиента (столько их в ванильной записи) идёт полный проход по тону. Насыщенность и яркость
# чуть ниже предельных — чистый компьютерный цвет на чешуе выглядит ядовито.
DRAGON_PALETTE = ["%.2f, %.2f, %.2f" % colorsys.hsv_to_rgb(i / 24.0, 0.72, 0.92)
                  for i in range(24)]
# Гиппогриф (tools/make_hippogriff.py): орлиная голова с перьевым воротником, крылья из рук,
# птичьи лапы и широкий хвост-веер. Модель того же вида, что у грифона, и разбирается так же;
# крылья и хвост вешает на скелет src/EquestriaBodyParts.cs, перья макушки работают причёской.
# Палитра множится на текстуру модели (она бурая с золотом), поэтому оттенки светлые: от
# морской волны до песочного — гиппогрифы из Сиквестрии бывают любых мастей.
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
    "1.00, 0.98, 0.94",  # свой цвет модели
    "0.86, 0.96, 1.00",  # морская волна
    "0.94, 0.90, 1.00",  # сиреневый
    "1.00, 0.92, 0.82",  # песочный
    "0.88, 1.00, 0.94",  # мятный
    "1.00, 0.88, 0.90",  # розоватый
    "0.90, 0.94, 1.00",  # голубой
    "0.96, 1.00, 0.86",  # салатовый
    "0.84, 0.88, 0.92",  # стальной
    "1.00, 0.94, 0.72",  # золотистый
]
HIPPOGRIFF_HAIR = None  # отдельной причёски у гипогрифа нет — голова и уши одно целое с головой
HIPPOGRIFF_HAIR_TAG = "HippogriffCrest"
HIPPOGRIFF_HAIR_COLORS = [  # перья макушки: от белого до тёмно-синего, плюс яркие морские тона
    "0.94, 0.92, 0.90", "0.62, 0.78, 0.86", "0.32, 0.54, 0.70", "0.18, 0.34, 0.52",
    "0.50, 0.70, 0.62", "0.74, 0.60, 0.78", "0.86, 0.72, 0.52", "0.40, 0.46, 0.56",
    "0.66, 0.34, 0.42", "0.24, 0.46, 0.44", "0.80, 0.84, 0.88", "0.30, 0.28, 0.34",
]
# Расы цилиней здесь больше нет: она была проверочной, на мешах пони, а её держава (Земли
# цилиней) стала Оленией — олени у нас со своей моделью (tools/make_deer_model.py).

# ---------------------------------------------------------------- skins
human = next(r for r in ET.parse(os.path.join(NATIVE, "skins.xml")).getroot() if r.get("id") == "human")


# Настоящие причёски (слот волос). Слайдеры лица у человека двигают и волосы (deforms_hair у ключей лица),
# а на голове пони это рвало любую причёску на куски — у наших рас волосы от лица не зависят
# (проверено в игре 2026-09-17: с deforms_hair=0 ванильные причёски целые).
# Грива Кризалис — tools/make_changeling_hair.py; варианты длины — отдельные причёски, отражение — галочкой.
CHANGELING_HAIR = None  # отключено 05.10.2026: прядевые гривы выглядели как человеческие причёски
HAIR_TAG = "ChangelingMane"  # тег причёсок: лордам и спутникам — грива, трутням — Bald
# Пони: только мультяшные гривы — грива Твайлайт (tools/make_pony_hair.py) и стили tools/make_pony_manes.py.
# Гривы из прядей (как у чейнджлингов) слишком похожи на человеческие причёски — у пони их нет.
PONY_HAIR = ["eq_hair_pony_twilight", "eq_hair_pony_straight", "eq_hair_pony_curly", "eq_hair_pony_wild",
             "eq_hair_pony_puffy", "eq_hair_pony_long", "eq_hair_pony_ponytail", "eq_hair_pony_short"]
PONY_HAIR_TAG = "PonyMane"
# Грива Твайлайт окрашена в текстуре и от палитры не зависит. Палитра красит пряди остальных грив:
# шейдер волос сильно выбеливает светлые цвета, поэтому они тёмные и насыщенные (как у чейнджлингов).
PONY_HAIR_COLORS = [
    "0.45, 0.12, 0.30", "0.20, 0.10, 0.45", "0.10, 0.22, 0.50", "0.55, 0.35, 0.05",
    "0.50, 0.08, 0.10", "0.08, 0.35, 0.18", "0.55, 0.20, 0.05", "0.30, 0.05, 0.40",
    "0.05, 0.35, 0.50", "0.12, 0.10, 0.14", "0.60, 0.50, 0.30", "0.35, 0.18, 0.08",
]
# Цвет гривы: бирюза, морская волна, зелень и синева улья. Длина списка — как у человека (24).
CHANGELING_HAIR_COLORS = [  # текстура прядей светлая и блестит — оттенки берём тёмные и насыщенные
    # Цветов ровно 24 и все разные: окно внешности рисует два ряда по 12, и с 12 цветами нижний
    # ряд повторял верхний. Верхний — бирюза, морская волна, зелень; нижний — синева, фиолет, яд.
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


# Волосы следуют за слайдерами лица (deforms_hair), только если все причёски расы построены по её голове:
# ванильные причёски на голове пони рвались, а своя грива иначе проходит сквозь морду, когда лицо меняется.
OWN_HAIR_FOLLOWS_FACE = True


# Цирюльник показывает только причёски с тегом культуры (BodyPropertiesModel.GetHairIndicesForCulture),
# поэтому у гривы теги всех культур. Войскам, которым грива не положена, задан тег Bald (make_troops.py).
CULTURE_TAGS = ["empire", "battania", "aserai", "sturgia", "vlandia", "khuzait", "nord"]


def fill_hair(parent, names, hair_tag, keep_bald=True):
    """Причёски по кругу; длина списка человеческая.

    Первая (лысая) запись по умолчанию остаётся: это и есть пункт «лысый» в списке причёсок
    цирюльника. keep_bald=False убирает его тоже — у пони так быть не должно (заказано 28.09.2026).

    cover_type4 — та же причёска: без шлема и без доспеха (Equipment.HairCoverType = Type4) движок
    показывает именно этот вариант, без него голый герой был лысым. Под шлемами type1..3 грива скрыта.
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
    # Татуировки оставляем человеческие: это готовый канал под кьютимарки, и на них проверяется,
    # отзывается ли материал пони на накладки движка. Свои кьютимарки заменят их позже.
    if TATTOO_MATERIALS:
        for i, tattoo in enumerate(skin.find("tattoo_materials")):
            tattoo.set("name", TATTOO_MATERIALS[i % len(TATTOO_MATERIALS)])
    else:
        # без своих накладок список пустой: человеческая боевая раскраска нарисована под развёртку
        # человеческого лица и на морде пони ложится кривыми пятнами
        keep_only_empty(skin.find("tattoo_materials"))
    # Брови оставляем человеческими: с пустым списком редактор внешности при создании героя падает.
    # Они ставятся в точку человеческого лица — внутри более крупной головы пони их не видно.
    # голова пони использует общий материал модели вместо человеческой кожи лица
    # (столько же вариантов, сколько у человека, с теми же тегами — ради случайного выбора в редакторе)
    faces = list(skin.find("face_textures"))
    for i, face in enumerate(faces):
        # последняя запись — особый вариант лица расы (у чейнджлингов зелёные глаза королевы):
        # движок выбирает материал лица у каждого персонажа отдельно (ползунок «лицо» в редакторе
        # внешности), поэтому уникальная внешность вроде Кризалис не требует своей расы.
        # material — материал головы расы (у яка свой eq_yak_body: с атласом пони голова пёстрая)
        mat = face_material if face_material and i == len(faces) - 1 else material
        face.set("name", mat)
        face.set("lod_material", mat)
    # Палитра окраса: ползунок цвета кожи в редакторе персонажа выбирает точку этого градиента, и движок
    # умножает на неё текстуру тела. Длина списка сохраняется (движок берёт индекс из человеческого
    # диапазона). Работает только если материал модели использует шейдер кожи, как у body_female_a.
    points = skin.find("skin_color_gradient_points")
    for i, point in enumerate(points):
        point.set("point", palette[i % len(palette)])


# Пока FBX новой пони не импортирован (NOT_IMPORTED ниже), она ходит на прежних мешах Twilight.
# Объявлен здесь, до сборки пони, потому что проверяется ниже сразу.
NOT_IMPORTED = set()   # assets/pony/eq_pony.fbx собран, ждёт импорта: tools/pony_material.ps1 снимает
PONY_WAITING = RACE in NOT_IMPORTED or "--placeholder" in sys.argv
if PONY_WAITING:
    print("pony: меши новой модели ещё не импортированы — пока Twilight")
    # Пока FBX новой пони не импортирован (NOT_IMPORTED ниже), она ходит на прежних мешах Twilight.
# Объявлен здесь, до сборки пони, потому что проверяется ниже сразу.
NOT_IMPORTED = set()   # assets/pony/eq_pony.fbx собран, ждёт импорта: tools/pony_material.ps1 снимает
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
# Пока меши расы не импортированы в редакторе, она берёт меши пони — иначе редактор и игра
# останавливаются на «Meta mesh ... cannot be found». Импортировали FBX — убрать расу из этого списка.
# Ключ --placeholder делает то же для всех рас сразу (нужен после пересборки всех моделей).
# Расы, чьи меши ещё не импортированы в редакторе: такая раса временно ходит на мешах пони,
# иначе игра встаёт на «Meta mesh ... cannot be found». После импорта FBX в Modding Kit расу
# отсюда убирают и пересобирают skins — это делает соответствующий *_material.ps1.
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
    # Копируем ванильного человека ЦЕЛИКОМ, а не наследуемся одной строкой через base_monster:
    # по наследству не доезжают имена костей.
    #
    # НАБОР ДВИЖЕНИЙ ОСТАВЛЯЕМ ВАНИЛЬНЫЙ (as_human_*), наш as_pony_* монстрам не подсовываем.
    # Причина: кости монстра движок ищет ЧЕРЕЗ СКЕЛЕТ ЕГО НАБОРА (Monster.DeserializeBoneIndex →
    # GetBoneIndexWithId(ActionSetCode, имя)), и с нашими наборами все кости выходили -1 — молча.
    # Этот -1 движок потом передаёт в подгонку шлема под голову, и шлем улетал вверх на весь рост;
    # заодно мертвы направление взгляда, IK ног и кости тряпичной куклы.
    # А наши 88 наборов — пустые копии: внутри ни одной анимации, только base_set="as_human_*".
    # То есть прослойка ничего не давала, но ломала разрешение костей. Когда появятся настоящие
    # пони-анимации, набор можно будет вернуть — но тогда проверить, что кости всё ещё находятся.
    main = copy.deepcopy(native_monsters["human"])
    main.set("id", race_id)
    monsters.append(main)
    for suffix in ("_child", "_settlement", "_settlement_slow", "_settlement_fast"):
        m = copy.deepcopy(native_monsters["human" + suffix])
        m.set("id", race_id + suffix)
        m.set("base_monster", m.get("base_monster").replace("human", race_id, 1))
        monsters.append(m)      # набор движений — тоже ванильный, см. выше
write(monsters, "pony_monsters.xml")

# ---------------------------------------------------------------- action sets
# Скелет и набор движений НЕ ПРОПИСЫВАЕМ. Когда-то они стояли у каждого набора: без них кости
# монстра выходили -1, и от этого ломались подгонка шлема, направление взгляда, IK ног и
# тряпичная кукла. Но чинило дело не это, а набор движений у монстра: сейчас монстры ходят на
# ванильных as_human_* (см. выше), и наши наборы никто не спрашивает.
# Зато редактор на каждый такой атрибут выдаёт окно «skeleton already defined the same in
# base_set for as_pony_warrior» — 88 наборов по два окна, 176 щелчков при каждом запуске
# (замечено пользователем 24.09.2026). Значение и так приходит по цепочке base_set.
#
# Если однажды монстрам снова понадобятся НАШИ наборы — возвращать не атрибут, а полноценный
# набор с анимациями; пустая копия с атрибутом только повторяет то, что и так есть у родителя.
native_sets = {a.get("id"): a for a in ET.parse(os.path.join(NATIVE, "action_sets.xml")).getroot().iter("action_set")}
human_sets = [i for i in native_sets if i.startswith("as_human_")]
# Сам файл наборов пишет tools/make_race_action_sets.py: наборы ВСЕХ рас (as_<раса>_facegen и
# прочие) и привязку позы полёта act_eq_flight_pose → anim_eq_flight_pose. Раньше здесь писался
# урезанный файл только с as_pony_*, и каждый *_material.ps1 (они все зовут этот скрипт) молча
# стирал привязку: бойцы со свитком в окнах персонажа вставали в позу атаки вместо полёта
# (замечено пользователем 10.10.2026 после yak_material.ps1).
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
                            # Удвоенные эффекты крови (tools/make_more_blood.py) — тот же
                            # стандартный id="soln_particle_systems", что и у нескольких
                            # ванильных particle_systems_*.xml в Native/project.mbproj: движок
                            # грузит/мёржит их все, а не только один, в отличие от action_types.
                            ("soln_particle_systems", "ModuleData/equestria_more_blood.xml",
                             "particle_system"),
                            # act_eq_flight_pose (src/EquestriaFlightScroll.cs) — регистрация
                            # имени экшена, см. bannerlord-animation-pipeline.md раздел 7.
                            ("soln_action_types", "ModuleData/action_types.xml", "action_type")):
    ET.SubElement(project, "file", id=file_id, name=name, type=kind)
write(project, "project.mbproj")
