"""Cartoon pony manes: real hairstyles (hair slot), as in the cartoon: smooth voluminous locks.

Run (headless Blender, on the finished pony):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python make_pony_manes.py -- ../assets/pony_manes

Each lock is a tube with a flattened cross-section along the strand line (hair_common.lock_path/Mane.lock): from
the root on the head through a convergence point downward, with a wave, a curl or a sharp tip. Locks go around
the eyes and ears. Styles are inspired by the Mane Six; the meshes do not copy the cartoon, they are our own shapes.
The locks themselves, the cap and the solid-colour areas of the hair texture live in hair_common (deer antlers use them too).
"""
import os
import sys

import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hair_common import (D, DARK, LIGHT, Mane, V, export, lock_path, log,  # noqa: E402
                         preview, push_out, scalp_point)

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])


# ---------------------------------------------------------------- styles
def style_straight(m):
    """Straight bangs and straight strands to the shoulders, a stripe of the second tone (Twilight motif)."""
    m.cap(hang=0.08)
    for k, x in enumerate(np.linspace(-1, 1, 6)):
        tone = DARK if k == 4 else LIGHT
        m.lock(lock_path(D(180 - 32 * x, 84), D(180 - 44 * x, 34), 0.02, V(0, -0.3, -1), 0.024, 0.085),
               0.085, 0.024, tone, tip="blunt")
    for k, th in enumerate(np.linspace(-78, 78, 9)):
        tone = DARK if k in (5, 6) else LIGHT
        m.lock(lock_path(D(th * 0.6, 80), D(th, 0), 0.32, V(0, 0.35, -1), 0.024, 0.1),
               0.1, 0.024, tone, tip="blunt")
    for s in (-1, 1):
        m.lock(lock_path(D(s * 122, 55), D(s * 102, 0), 0.14, V(s * 0.1, -0.2, -1), 0.028, 0.06),
               0.06, 0.028, LIGHT, tip="blunt")


def style_curly(m):
    """Full side-swept bangs and large curls at the ends (Rarity motif)."""
    m.cap(hang=0.06)
    m.lock(lock_path(D(-165, 86), D(118, 22), 0.12, V(0.1, -0.3, -1), 0.045, 0.11, curl=0.9, curl_r=0.04),
           0.11, 0.045, LIGHT, tip="round")
    m.lock(lock_path(D(-172, 80), D(150, 42), 0.04, V(0.2, -0.4, -1), 0.04, 0.085, curl=0.6, curl_r=0.03),
           0.085, 0.04, DARK, tip="round")
    for k, th in enumerate(np.linspace(-75, 75, 7)):
        m.lock(lock_path(D(th * 0.6, 82), D(th, 5), 0.2, V(0, 0.3, -1), 0.035, 0.1, curl=1.1, curl_r=0.045),
               0.1, 0.035, DARK if k == 3 else LIGHT, tip="round")
    m.lock(lock_path(D(-124, 52), D(-102, 0), 0.12, V(-0.1, -0.2, -1), 0.035, 0.075, curl=1.0, curl_r=0.035),
           0.075, 0.035, LIGHT, tip="round")


def style_wild(m):
    """Messy sharp strands sticking back and up (Rainbow Dash motif)."""
    m.cap(hang=0.03)
    for k, x in enumerate(np.linspace(-1, 1, 4)):
        m.lock(lock_path(D(180 - 20 * x, 82), D(180 - 38 * x, 48), 0.06, V(x * 0.3, -1, 0.5), 0.025, 0.06,
                         curl=-0.12), 0.06, 0.025, DARK if k % 2 else LIGHT, tip="point")
    for k, th in enumerate(np.linspace(-80, 80, 9)):
        sgn = 1 if th >= 0 else -1
        m.lock(lock_path(D(th * 0.5, 80), D(th, 25), 0.11, V(sgn * 0.3 * abs(th) / 75, 1, 0.25), 0.028, 0.075,
                         curl=-0.15), 0.075, 0.028, DARK if k % 2 else LIGHT, tip="point")
    for s in (-1, 1):
        m.lock(lock_path(D(s * 125, 50), D(s * 106, 15), 0.07, V(s, 0.2, -0.6), 0.022, 0.055),
               0.055, 0.022, LIGHT, tip="point")


def style_puffy(m):
    """Fluffy curls all over the head (Pinkie Pie motif)."""
    m.cap(hang=0.05)
    k = 0
    # the lower rows do not reach the face: the lower the row, the narrower it is at the front
    for phi, count, reach in ((-8, 8, 105), (12, 10, 118), (32, 10, 130), (52, 9, 145), (72, 6, 150), (86, 2, 150)):
        for th in np.linspace(-reach, reach, count) + (k % 2) * 6:
            m.lock(lock_path(D(th, phi + 12), D(th, phi - 4), 0.03, V(0, 0.3, -1), 0.06, 0.1, curl=1.3,
                             curl_r=0.03, n_scalp=5), 0.1, 0.06, DARK if k % 3 == 0 else LIGHT, tip="round")
            k += 1
    for x in (-1, 0, 1):
        m.lock(lock_path(D(180 - 22 * x, 80), D(180 - 30 * x, 50), 0.02, V(0, -1, -0.3), 0.05, 0.08, curl=1.2,
                         curl_r=0.025, n_scalp=6), 0.08, 0.05, LIGHT, tip="round")


def style_long(m):
    """Long wavy mane and bangs swept to the side (Fluttershy motif)."""
    m.cap(hang=0.1)
    m.lock(lock_path(D(-162, 86), D(116, 26), 0.26, V(0.05, -0.3, -1), 0.035, 0.1, wave=0.02, waves=2.0),
           0.1, 0.035, LIGHT, tip="point")
    for k, th in enumerate(np.linspace(-80, 80, 9)):
        m.lock(lock_path(D(th * 0.6, 82), D(th, -5), 0.55, V(0, 0.3, -1), 0.028, 0.105, wave=0.025, waves=2.5),
               0.105, 0.028, DARK if k == 1 else LIGHT, tip="point")
    m.lock(lock_path(D(-126, 50), D(-102, -5), 0.34, V(-0.05, -0.4, -1), 0.03, 0.08, wave=0.02, waves=2.0),
           0.08, 0.03, LIGHT, tip="point")


def style_ponytail(m):
    """Short bangs, hair pulled back into a tail with a hair tie (Applejack motif)."""
    m.cap(hang=0.0)
    for x in np.linspace(-1, 1, 5):
        m.lock(lock_path(D(180 - 30 * x, 84), D(180 - 36 * x, 40), 0.0, V(0, -0.3, -1), 0.025, 0.07),
               0.07, 0.025, LIGHT, tip="blunt")
    tie = D(0, 18)
    for a in np.linspace(-1, 1, 9):
        root = D(180 - 150 * a, 70 - 45 * abs(a))
        m.lock(lock_path(root, tie, 0.0, V(0, 0, -1), 0.022, 0.08, n_scalp=14), 0.08, 0.022, LIGHT, tip="blunt")
    start = scalp_point(tie, 0.03)
    tail = [start + Vector((0, 0.02 * i, 0)) for i in range(3)]
    t = Vector((0, 0.6, -0.4)).normalized()
    p = tail[-1]
    for i in range(26):
        t = (t + Vector((0, 0.05, -0.12))).normalized()
        p = push_out(p + t * 0.016, 0.03)
        tail.append(p)
    m.lock(tail, 0.1, 0.055, LIGHT, tip="round", root_scale=0.55)
    m.lock([start + Vector((0, 0.005, 0)), start + Vector((0, 0.03, 0))], 0.075, 0.065, DARK, tip="blunt",
           root_scale=1.0)


def style_short(m):
    """Short boyish haircut with sticking-out strands (Scootaloo and stallions motif)."""
    m.cap(hang=0.02)
    for x in np.linspace(-1, 1, 3):
        m.lock(lock_path(D(180 - 25 * x, 84), D(180 - 35 * x, 52), 0.03, V(x * 0.3, -1, 0.3), 0.025, 0.07),
               0.07, 0.025, LIGHT, tip="point")
    for k, th in enumerate(np.linspace(-80, 80, 9)):
        m.lock(lock_path(D(th * 0.5, 82), D(th, 32), 0.04, V(0, 1, 0.1), 0.025, 0.09),
               0.09, 0.025, DARK if k % 3 == 1 else LIGHT, tip="point")
    for s in (-1, 1):
        m.lock(lock_path(D(s * 122, 55), D(s * 108, 30), 0.02, V(s, 0, -0.5), 0.022, 0.06),
               0.06, 0.022, LIGHT, tip="point")


STYLES = {
    "eq_hair_pony_straight": style_straight,
    "eq_hair_pony_curly": style_curly,
    "eq_hair_pony_wild": style_wild,
    "eq_hair_pony_puffy": style_puffy,
    "eq_hair_pony_long": style_long,
    "eq_hair_pony_ponytail": style_ponytail,
    "eq_hair_pony_short": style_short,
}

objects = []
for name, fn in STYLES.items():
    m = Mane(name)
    fn(m)
    m.add_horn()
    objects.append(m.to_object(radial_normals=False, cut_ears=False))
export(objects, os.path.join(OUT, "eq_pony_manes.fbx"))
log("styles", list(STYLES))
preview(objects, os.path.join(OUT, "preview"), (0.85, 0.45, 0.95))
