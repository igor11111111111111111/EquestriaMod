# Анатомические карты чужих моделей: где у них суставы.
#
# Модели грифона и яка сгенерированы по референсам и приходят четвероногими, без скелета и в
# произвольной ориентации. Автоматически разобрать, где нога, а где хвост, надёжно нельзя,
# поэтому суставы сняты руками по ортографическим видам с координатной сеткой
# (tools/preview_model.py + подпись координат) и записаны сюда.
#
# Координаты — в системе самой модели (метры, Z вверх), до всякого поворота. Поворот "yaw"
# применяется первым и разворачивает модель мордой в -Y, как смотрит персонаж Bannerlord.
#
# Ключи суставов — это кости ванильного скелета (bip01_*), к которым они привязываются:
#   pelvis, spine, spine1, spine2, neck, head, head_end — позвоночник от таза до макушки;
#   l/r_clavicle, l/r_upperarm, l/r_forearm, l/r_hand, l/r_hand_end — передние лапы (станут руками);
#   l/r_thigh, l/r_calf, l/r_foot, l/r_toe, l/r_toe_end — задние лапы (станут ногами).
# Всё остальное (хвост, крылья, рога) двигается вместе с ближайшей костью — отдельными костями
# в скелете Bannerlord их нет.

GRIFFON = {
    "name": "griffon",
    "yaw": 0.0,              # модель уже смотрит в -Y (клюв на -Y)
    "target_tris": 12000,
    "joints": {
        "pelvis": (0.00, 0.06, -0.05),
        "spine": (0.00, -0.10, 0.00),
        "spine1": (0.00, -0.28, 0.02),
        "spine2": (0.00, -0.45, 0.04),
        "neck": (0.00, -0.58, 0.12),
        "head": (0.00, -0.72, 0.26),
        "head_end": (0.00, -0.86, 0.34),

        "l_clavicle": (-0.10, -0.50, 0.02),
        "l_upperarm": (-0.18, -0.55, -0.05),
        "l_forearm": (-0.19, -0.62, -0.26),
        "l_hand": (-0.20, -0.70, -0.44),
        "l_hand_end": (-0.20, -0.82, -0.50),
        "r_clavicle": (0.10, -0.50, 0.02),
        "r_upperarm": (0.18, -0.55, -0.05),
        "r_forearm": (0.19, -0.62, -0.26),
        "r_hand": (0.20, -0.70, -0.44),
        "r_hand_end": (0.20, -0.82, -0.50),

        "l_thigh": (-0.13, 0.06, -0.12),
        "l_calf": (-0.14, 0.16, -0.28),
        "l_foot": (-0.14, -0.02, -0.42),
        "l_toe": (-0.14, -0.14, -0.50),
        "l_toe_end": (-0.14, -0.24, -0.52),
        "r_thigh": (0.13, 0.06, -0.12),
        "r_calf": (0.14, 0.16, -0.28),
        "r_foot": (0.14, -0.02, -0.42),
        "r_toe": (0.14, -0.14, -0.50),
        "r_toe_end": (0.14, -0.24, -0.52),
    },
    # части, которые в игре станут отдельными предметами (вершины выбираются по координатам модели)
    "extras": {
        # крылья: всё, что выше спины и дальше 0.22 от середины по X
        "wings": {"min_z": 0.06, "min_y": -0.42},
        # хвост: всё позади таза
        "tail": {"min_y": 0.28},
    },
    # крылья и хвост двигаются одной костью целиком: иначе при переносе позы их растягивает
    # между лапами и они превращаются в лапшу
    "rigid": {"wings": "spine2", "tail": "pelvis"},
    # Детали, которые пересаживаются на антро-тело пони (tools/make_creature_parts.py).
    #   rule   — какие вершины модели берём (координаты модели, после разворота мордой в -Y);
    #   bone   — на какую кость садится деталь;
    #   size/by — до какого размера по оси её масштабировать;
    #   rotate — поворот детали вокруг своей середины (тангаж, крен, рыскание, градусы);
    #   anchor — какая точка детали совмещается с костью; offset — сдвиг от кости.
    "graft": {
        "head": {"rule": {"max_y": -0.55}, "bone": "head", "size": 0.52, "by": "z",
                 "rotate": (0, 0, 0), "anchor": "bottom", "offset": (0, -0.01, -0.28),
                 "tris": 3500},
        "wings": {"rule": {"min_z": 0.20, "min_y": -0.40}, "bone": "spine2", "size": 0.95, "by": "x",
                  "rotate": (0, 0, 0), "anchor": "middle", "offset": (0, 0.22, 0.02), "tris": 3000},
        "tail": {"rule": {"min_y": 0.28}, "bone": "pelvis", "size": 0.50, "by": "y",
                 "rotate": (-15, 0, 0), "anchor": "front", "offset": (0, 0.10, 0.00), "tris": 1500},
    },
    # Области тела: какая часть модели какими костями двигается. Без этого вершина цепляется
    # за случайную ближайшую кость (живот — за лапу, перо — за руку) и при переносе позы
    # вытягивается в шип.
    "regions": {
        "arms": {"max_y": -0.42, "max_z": 0.06},      # передние лапы, станут руками
        "legs": {"min_y": -0.22, "max_z": 0.02},      # задние лапы, станут ногами
        "head": {"max_y": -0.50, "min_z": 0.08},      # голова с шеей
    },
}

YAK = {
    "name": "yak",
    "yaw": -90.0,            # модель смотрит в +X, разворачиваем мордой в -Y
    "target_tris": 14000,
    "joints": {
        "pelvis": (-0.30, 0.00, 0.38),
        "spine": (-0.18, 0.00, 0.42),
        "spine1": (-0.05, 0.00, 0.45),
        "spine2": (0.08, 0.00, 0.45),
        "neck": (0.18, 0.00, 0.44),
        "head": (0.30, 0.00, 0.40),
        "head_end": (0.44, 0.00, 0.34),

        "l_clavicle": (0.05, -0.06, 0.42),
        "l_upperarm": (0.05, -0.13, 0.35),
        "l_forearm": (0.03, -0.13, 0.20),
        "l_hand": (0.02, -0.13, 0.08),
        "l_hand_end": (0.04, -0.13, 0.01),
        "r_clavicle": (0.05, 0.06, 0.42),
        "r_upperarm": (0.05, 0.13, 0.35),
        "r_forearm": (0.03, 0.13, 0.20),
        "r_hand": (0.02, 0.13, 0.08),
        "r_hand_end": (0.04, 0.13, 0.01),

        "l_thigh": (-0.33, -0.12, 0.33),
        "l_calf": (-0.35, -0.13, 0.18),
        "l_foot": (-0.33, -0.13, 0.06),
        "l_toe": (-0.28, -0.13, 0.02),
        "l_toe_end": (-0.24, -0.13, 0.01),
        "r_thigh": (-0.33, 0.12, 0.33),
        "r_calf": (-0.35, 0.13, 0.18),
        "r_foot": (-0.33, 0.13, 0.06),
        "r_toe": (-0.28, 0.13, 0.02),
        "r_toe_end": (-0.24, 0.13, 0.01),
    },
    "extras": {
        # хвост яка — сзади, выше ног
        "tail": {"max_x": -0.44, "min_z": 0.20},
    },
    "rigid": {"tail": "pelvis"},
    "graft": {
        "head": {"rule": {"max_y": -0.02}, "bone": "head", "size": 0.50, "by": "z",
                 "rotate": (0, 0, 0), "anchor": "bottom", "offset": (0, 0.02, -0.30),
                 "tris": 4000},
        # хвост яка — короткий обрубок, масштабируем по ширине: по толщине он почти плоский
        # и масштаб «по высоте» раздувал его в лопату
        "tail": {"rule": {"min_y": 0.45, "min_z": 0.25, "max_z": 0.36}, "bone": "pelvis",
                 "size": 0.18, "by": "x", "rotate": (0, 0, 0), "anchor": "middle",
                 "offset": (0, 0.16, 0.10), "tris": 1200},
    },
    "regions": {
        "arms": {"min_x": -0.05, "max_x": 0.14, "max_z": 0.40},
        "legs": {"max_x": -0.22, "max_z": 0.38},
        "head": {"min_x": 0.15},
    },
}

CREATURES = {"griffon": GRIFFON, "yak": YAK}

# Кость скелета Bannerlord для каждого сустава карты. Имена сверены с human_skeleton.fbx.
BONES = {
    "pelvis": "bip01_pelvis_0", "spine": "bip01_spine_9", "spine1": "bip01_spine1_10",
    "spine2": "bip01_spine2_11", "neck": "bip01_neck_12", "head": "bip01_head_13",
    "head_end": "bip01_head_nub_notused",
    "l_clavicle": "bip01_l_clavicle_14", "l_upperarm": "bip01_l_upperarm_twist_15",
    "l_forearm": "bip01_l_foretwist_17", "l_hand": "bip01_l_hand_19",
    "l_hand_end": "bip01_l_finger0_20",
    "r_clavicle": "bip01_r_clavicle_21", "r_upperarm": "bip01_r_upperarm_twist_22",
    "r_forearm": "bip01_r_foretwist_24", "r_hand": "bip01_r_hand_26",
    "r_hand_end": "bip01_r_finger0_27",
    "l_thigh": "bip01_l_thigh_1", "l_calf": "bip01_l_calf_2", "l_foot": "bip01_l_foot_3",
    "l_toe": "bip01_l_toe0_4", "l_toe_end": "bip01_l_toe0_nub_notused",
    "r_thigh": "bip01_r_thigh_5", "r_calf": "bip01_r_calf_6", "r_foot": "bip01_r_foot_7",
    "r_toe": "bip01_r_toe0_8", "r_toe_end": "bip01_toe0_nub_notused",
}

# Цепочки «кость -> следующий сустав»: по ним строятся хвосты костей временного скелета.
CHAINS = [
    ["pelvis", "spine", "spine1", "spine2", "neck", "head", "head_end"],
    ["l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_hand_end"],
    ["r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_hand_end"],
    ["l_thigh", "l_calf", "l_foot", "l_toe", "l_toe_end"],
    ["r_thigh", "r_calf", "r_foot", "r_toe", "r_toe_end"],
]

# Оснащённая модель грифона (Meshy, скелет из 27 костей). Здесь записано, куда должна смотреть
# каждая кость в стойке: спина вверх, передние лапы в стороны руками, задние вниз ногами,
# хвост назад-вниз. Модель смотрит в -Y, «frontleg» без приставки — левая сторона (+X).
GRIFFON["rigged_yaw"] = 0.0
GRIFFON["tpose"] = {
    # Корпус поднимаем поворотом самого таза: туловище четвероногого висит в основном на этой
    # кости, и поворот груди его не двигает. После этого ноги, руки и хвост доворачиваются
    # по месту, каждый своей целью.
    "Hips": {"rotate": (-90.0, 0.0, 0.0)},
    "head": {"ref": "headend", "dir": (0.0, -0.75, 0.55)},
    "earend": {"dir": (0.25, -0.2, 1.0)},
    "R_earend": {"dir": (-0.25, -0.2, 1.0)},

    # передние лапы становятся руками: разводим в стороны
    "frontleg": {"ref": "frontleg0", "dir": (1.0, 0.0, -0.05)},
    "frontleg0": {"ref": "frontleg1", "dir": (1.0, 0.0, -0.05)},
    "frontleg1": {"ref": "frontleg2", "dir": (1.0, 0.0, 0.0)},
    "frontleg2": {"dir": (1.0, 0.0, -0.15)},
    "R_frontleg": {"ref": "R_frontleg0", "dir": (-1.0, 0.0, -0.05)},
    "R_frontleg0": {"ref": "R_frontleg1", "dir": (-1.0, 0.0, -0.05)},
    "R_frontleg1": {"ref": "R_frontleg2", "dir": (-1.0, 0.0, 0.0)},
    "R_frontleg2": {"dir": (-1.0, 0.0, -0.15)},

    # задние лапы выпрямляются ногами вниз
    "backleg": {"ref": "backleg0", "dir": (0.05, 0.0, -1.0)},
    "backleg0": {"ref": "backleg1", "dir": (0.0, 0.0, -1.0)},
    "backleg1": {"ref": "backleg2", "dir": (0.0, 0.0, -1.0)},
    "backleg2": {"dir": (0.0, -1.0, -0.3)},
    "R_backleg": {"ref": "R_backleg0", "dir": (-0.05, 0.0, -1.0)},
    "R_backleg0": {"ref": "R_backleg1", "dir": (0.0, 0.0, -1.0)},
    "R_backleg1": {"ref": "R_backleg2", "dir": (0.0, 0.0, -1.0)},
    "R_backleg2": {"dir": (0.0, -1.0, -0.3)},

    # хвост назад и вниз
    "tail": {"ref": "tailstart", "dir": (0.0, 1.0, -0.35)},
    "tailstart": {"ref": "tail1", "dir": (0.0, 1.0, -0.45)},
    "tail1": {"ref": "tail2", "dir": (0.0, 1.0, -0.55)},
    "tail2": {"ref": "tail3", "dir": (0.0, 1.0, -0.65)},
    "tail3": {"dir": (0.0, 1.0, -0.75)},
}

# Какая кость зверя какой кости Bannerlord соответствует (для переноса весов).
GRIFFON["bone_map"] = {
    "Hips": "pelvis", "chest": "spine1",
    "head": "neck", "headend": "head", "earend": "head", "R_earend": "head",
    "frontleg": "l_upperarm", "frontleg0": "l_forearm", "frontleg1": "l_hand", "frontleg2": "l_hand",
    "R_frontleg": "r_upperarm", "R_frontleg0": "r_forearm", "R_frontleg1": "r_hand",
    "R_frontleg2": "r_hand",
    "backleg": "l_thigh", "backleg0": "l_calf", "backleg1": "l_foot", "backleg2": "l_toe",
    "R_backleg": "r_thigh", "R_backleg0": "r_calf", "R_backleg1": "r_foot", "R_backleg2": "r_toe",
    "tail": "pelvis", "tailstart": "pelvis", "tail1": "pelvis", "tail2": "pelvis", "tail3": "pelvis",
}

# Доворот костей зверя к костям Bannerlord: какая кость к какой и по какому суставу считать
# направление. Хвост, уши и крылья сюда не входят — они должны остаться в стойке.
GRIFFON["retarget"] = {
    # таз: направление «таз -> поясница» у Bannerlord вертикальное, по нему и ставим корпус
    "Hips": {"key": "pelvis", "ref": "chest"},
    "chest": {"key": "spine1", "ref": "head"},
    "head": {"key": "neck", "ref": "headend"},
    "frontleg": {"stretch": True, "key": "l_upperarm", "ref": "frontleg0"},
    "frontleg0": {"stretch": True, "key": "l_forearm", "ref": "frontleg1"},
    "frontleg1": {"stretch": True, "key": "l_hand", "ref": "frontleg2"},
    "R_frontleg": {"stretch": True, "key": "r_upperarm", "ref": "R_frontleg0"},
    "R_frontleg0": {"stretch": True, "key": "r_forearm", "ref": "R_frontleg1"},
    "R_frontleg1": {"stretch": True, "key": "r_hand", "ref": "R_frontleg2"},
    "backleg": {"stretch": True, "key": "l_thigh", "ref": "backleg0"},
    "backleg0": {"stretch": True, "key": "l_calf", "ref": "backleg1"},
    "backleg1": {"stretch": True, "key": "l_foot", "ref": "backleg2"},
    "R_backleg": {"stretch": True, "key": "r_thigh", "ref": "R_backleg0"},
    "R_backleg0": {"stretch": True, "key": "r_calf", "ref": "R_backleg1"},
    "R_backleg1": {"stretch": True, "key": "r_foot", "ref": "R_backleg2"},
}
