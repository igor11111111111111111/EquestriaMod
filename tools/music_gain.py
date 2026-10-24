"""Music gain (runs inside Blender: it has the aud sound module).

  blender --background --factory-startup --python tools/music_gain.py -- <job-file.json>

Job: [[source ogg, output ogg, target loudness, bitrate], ...].

The tracks in the set differ a lot in loudness (the quiet ones are 5 times lower than the game's vanilla music),
so each one is pulled to ONE loudness: a gain is chosen at which the average loudness
(rms) after soft limiting (tanh) equals the target. That way the quiet ones become audible and the loud ones do not blare.
The bitrate also sets the size of the finished music. Called from tools/make_music.py.
"""
import json
import os
import sys

import aud
import numpy as np

jobs = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
MAX_GAIN = 16.0
# peak headroom: the ogg codec slightly overshoots the edge on output, with headroom the peaks stay within limits
HEADROOM = 0.85


def rms(x):
    return float(np.sqrt((x.astype(np.float64) ** 2).mean()))


for src, dst, target, bitrate in jobs:
    sound = aud.Sound(src)
    rate, channels = int(sound.specs[0]), int(sound.specs[1])
    data = sound.data()
    gain = min(MAX_GAIN, target / max(rms(data), 1e-9))
    for _ in range(4):  # tanh squeezes loudness, so the gain is chosen in several steps
        loud = np.tanh(data * gain) * HEADROOM
        got = rms(loud)
        if abs(got - target) < 0.005 or got < 1e-9:
            break
        gain = min(MAX_GAIN, gain * target / got)
    loud = (np.tanh(data * gain) * HEADROOM).astype(np.float32)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    aud.Sound.buffer(loud, rate).write(dst, rate=rate, channels=channels, format=aud.FORMAT_FLOAT32,
                                       container=aud.CONTAINER_OGG, codec=aud.CODEC_VORBIS, bitrate=bitrate)
    rms_before = float(np.sqrt((data.astype(np.float64) ** 2).mean()))
    rms_after = float(np.sqrt((loud.astype(np.float64) ** 2).mean()))
    print(f"[gain] {os.path.basename(dst)}: rms {rms_before:.3f} -> {rms_after:.3f} "
          f"(x{rms_after / max(rms_before, 1e-9):.1f}, усиление {gain:.1f}), пик {np.abs(loud).max():.2f}, "
          f"{os.path.getsize(dst) // 1024} КБ", flush=True)
