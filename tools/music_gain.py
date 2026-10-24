"""Усиление музыки (запускается внутри Blender: у него есть звуковой модуль aud).

  blender --background --factory-startup --python tools/music_gain.py -- <файл-задание.json>

Задание: [[исходный ogg, готовый ogg, целевая громкость, битрейт], ...].

Треки в наборе очень разные по громкости (у тихих в 5 раз меньше, чем у ванильной музыки игры),
поэтому каждый подтягивается к ОДНОЙ громкости: подбирается усиление, при котором средняя громкость
(rms) после мягкого ограничения (tanh) равна целевой. Так тихие становятся слышны, а громкие не орут.
Битрейт заодно задаёт вес готовой музыки. Вызывается из tools/make_music.py.
"""
import json
import os
import sys

import aud
import numpy as np

jobs = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
MAX_GAIN = 16.0
# запас по пикам: кодек ogg на выходе слегка перелетает через край, с запасом пики остаются в норме
HEADROOM = 0.85


def rms(x):
    return float(np.sqrt((x.astype(np.float64) ** 2).mean()))


for src, dst, target, bitrate in jobs:
    sound = aud.Sound(src)
    rate, channels = int(sound.specs[0]), int(sound.specs[1])
    data = sound.data()
    gain = min(MAX_GAIN, target / max(rms(data), 1e-9))
    for _ in range(4):  # tanh поджимает громкость, поэтому усиление подбираем в несколько шагов
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
