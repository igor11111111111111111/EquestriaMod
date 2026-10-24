# Anatomy maps of third-party models: where their joints are.
#
# The griffon and yak models are generated from references and arrive as quadrupeds, with no skeleton
# and in arbitrary orientation. Telling a leg from a tail automatically cannot be done reliably,
# so the joints were taken by hand from orthographic views with a coordinate grid
# (tools/preview_model.py + coordinate labels) and recorded here.
#
# Coordinates are in the model's own space (metres, Z up), before any rotation. The "yaw" rotation
# is applied first and turns the model to face -Y, the way a Bannerlord character faces.
#
# The joint keys are the vanilla skeleton bones (bip01_*) they are bound to:
#   pelvis, spine, spine1, spine2, neck, head, head_end - the spine from the pelvis to the crown;
#   l/r_clavicle, l/r_upperarm, l/r_forearm, l/r_hand, l/r_hand_end - front legs (will become arms);
#   l/r_thigh, l/r_calf, l/r_foot, l/r_toe, l/r_toe_end - hind legs (will become legs).
# Everything else (tail, wings, horns) moves with the nearest bone - the Bannerlord skeleton has
# no separate bones for them.

GRIFFON = {
    "name": "griffon",
    "yaw": 0.0,              # the model already faces -Y (beak towards -Y)
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
    # parts that will become separate items in game (vertices are selected by model coordinates)
    "extras": {
        # wings: everything above the back and further than 0.22 from the middle in X
        "wings": {"min_z": 0.06, "min_y": -0.42},
        # tail: everything behind the pelvis
        "tail": {"min_y": 0.28},
    },
    # wings and tail move with a single bone as a whole: otherwise retargeting the pose stretches them
    # between the legs and they turn into noodles
    "rigid": {"wings": "spine2", "tail": "pelvis"},
    # Parts grafted onto the anthro pony body (tools/make_creature_parts.py).
    #   rule   - which model vertices to take (model coordinates, after turning to face -Y);
    #   bone   - which bone the part sits on;
    #   size/by - what size along which axis to scale it to;
    #   rotate - rotation of the part around its middle (pitch, roll, yaw, degrees);
    #   anchor - which point of the part is aligned with the bone; offset - shift from the bone.
    "graft": {
        "head": {"rule": {"max_y": -0.55}, "bone": "head", "size": 0.52, "by": "z",
                 "rotate": (0, 0, 0), "anchor": "bottom", "offset": (0, -0.01, -0.28),
                 "tris": 3500},
        "wings": {"rule": {"min_z": 0.20, "min_y": -0.40}, "bone": "spine2", "size": 0.95, "by": "x",
                  "rotate": (0, 0, 0), "anchor": "middle", "offset": (0, 0.22, 0.02), "tris": 3000},
        "tail": {"rule": {"min_y": 0.28}, "bone": "pelvis", "size": 0.50, "by": "y",
                 "rotate": (-15, 0, 0), "anchor": "front", "offset": (0, 0.10, 0.00), "tris": 1500},
    },
    # Body regions: which part of the model moves with which bones. Without this a vertex grabs
    # a random nearest bone (the belly a leg, a feather an arm) and is stretched into a spike
    # when the pose is retargeted.
    "regions": {
        "arms": {"max_y": -0.42, "max_z": 0.06},      # front legs, will become arms
        "legs": {"min_y": -0.22, "max_z": 0.02},      # hind legs, will become legs
        "head": {"max_y": -0.50, "min_z": 0.08},      # head with neck
    },
}

YAK = {
    "name": "yak",
    "yaw": -90.0,            # the model faces +X, turn it to face -Y
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
        # the yak's tail is at the back, above the legs
        "tail": {"max_x": -0.44, "min_z": 0.20},
    },
    "rigid": {"tail": "pelvis"},
    "graft": {
        "head": {"rule": {"max_y": -0.02}, "bone": "head", "size": 0.50, "by": "z",
                 "rotate": (0, 0, 0), "anchor": "bottom", "offset": (0, 0.02, -0.30),
                 "tris": 4000},
        # the yak's tail is a short stub, scale it by width: in thickness it is almost flat
        # and scaling "by height" inflated it into a shovel
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

# The Bannerlord skeleton bone for each joint of the map. Names checked against human_skeleton.fbx.
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

# "bone -> next joint" chains: the bone tails of the temporary skeleton are built from them.
CHAINS = [
    ["pelvis", "spine", "spine1", "spine2", "neck", "head", "head_end"],
    ["l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_hand_end"],
    ["r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_hand_end"],
    ["l_thigh", "l_calf", "l_foot", "l_toe", "l_toe_end"],
    ["r_thigh", "r_calf", "r_foot", "r_toe", "r_toe_end"],
]

# The rigged griffon model (Meshy, 27-bone skeleton). This records where each bone should point
# in the stance: back up, front legs out to the sides as arms, hind legs down as legs,
# tail back and down. The model faces -Y; "frontleg" without a prefix is the left side (+X).
GRIFFON["rigged_yaw"] = 0.0
GRIFFON["tpose"] = {
    # The torso is raised by rotating the pelvis itself: a quadruped's trunk hangs mostly on this
    # bone, and rotating the chest does not move it. After that the legs, arms and tail are turned
    # into place, each towards its own target.
    "Hips": {"rotate": (-90.0, 0.0, 0.0)},
    "head": {"ref": "headend", "dir": (0.0, -0.75, 0.55)},
    "earend": {"dir": (0.25, -0.2, 1.0)},
    "R_earend": {"dir": (-0.25, -0.2, 1.0)},

    # front legs become arms: spread them out to the sides
    "frontleg": {"ref": "frontleg0", "dir": (1.0, 0.0, -0.05)},
    "frontleg0": {"ref": "frontleg1", "dir": (1.0, 0.0, -0.05)},
    "frontleg1": {"ref": "frontleg2", "dir": (1.0, 0.0, 0.0)},
    "frontleg2": {"dir": (1.0, 0.0, -0.15)},
    "R_frontleg": {"ref": "R_frontleg0", "dir": (-1.0, 0.0, -0.05)},
    "R_frontleg0": {"ref": "R_frontleg1", "dir": (-1.0, 0.0, -0.05)},
    "R_frontleg1": {"ref": "R_frontleg2", "dir": (-1.0, 0.0, 0.0)},
    "R_frontleg2": {"dir": (-1.0, 0.0, -0.15)},

    # hind legs straighten down as legs
    "backleg": {"ref": "backleg0", "dir": (0.05, 0.0, -1.0)},
    "backleg0": {"ref": "backleg1", "dir": (0.0, 0.0, -1.0)},
    "backleg1": {"ref": "backleg2", "dir": (0.0, 0.0, -1.0)},
    "backleg2": {"dir": (0.0, -1.0, -0.3)},
    "R_backleg": {"ref": "R_backleg0", "dir": (-0.05, 0.0, -1.0)},
    "R_backleg0": {"ref": "R_backleg1", "dir": (0.0, 0.0, -1.0)},
    "R_backleg1": {"ref": "R_backleg2", "dir": (0.0, 0.0, -1.0)},
    "R_backleg2": {"dir": (0.0, -1.0, -0.3)},

    # tail back and down
    "tail": {"ref": "tailstart", "dir": (0.0, 1.0, -0.35)},
    "tailstart": {"ref": "tail1", "dir": (0.0, 1.0, -0.45)},
    "tail1": {"ref": "tail2", "dir": (0.0, 1.0, -0.55)},
    "tail2": {"ref": "tail3", "dir": (0.0, 1.0, -0.65)},
    "tail3": {"dir": (0.0, 1.0, -0.75)},
}

# Which creature bone corresponds to which Bannerlord bone (for weight transfer).
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

# Turning the creature bones onto the Bannerlord bones: which bone to which, and by which joint to
# measure the direction. Tail, ears and wings are not included - they must stay in the stance.
GRIFFON["retarget"] = {
    # pelvis: the "pelvis -> lower back" direction is vertical in Bannerlord, so the torso is set by it
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
