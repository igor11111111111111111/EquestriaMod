# Файлы синхронизации губ (формат Rhubarb) для наших звуков реплик.
#
#   py -3 tools\make_lipsync.py Module\Sounds\bandit_greeting Module\Sounds\lord_greeting
#
# Игра, проигрывая реплику в диалоге, ищет рядом со звуком файл <имя>.xml с «ртами» по времени
# (CampaignMissionComponent.PlayConversationSoundEvent -> StartRhubarbRecord). Настоящий Rhubarb
# разбирает фонемы; нам хватает громкости: тишина — рот закрыт (X), тихо — B, громче — C, D.
import os
import struct
import sys
import wave

import numpy as np

STEP = 0.07   # длина одного «рта», с


def read_wav(path):
    with wave.open(path, "rb") as f:
        channels, width, rate, frames = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
        raw = f.readframes(frames)
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
    data = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if width == 1:
        data -= 128
    data = data.reshape(-1, channels).mean(axis=1)
    return data / max(float(np.abs(data).max()), 1.0), rate


def cues(data, rate):
    size = int(STEP * rate)
    levels = [float(np.sqrt(np.mean(data[i:i + size] ** 2))) for i in range(0, len(data), size)]
    top = max(levels) or 1.0
    out = []
    for i, level in enumerate(levels):
        share = level / top
        mouth = "X" if share < 0.08 else "B" if share < 0.3 else "C" if share < 0.6 else "D"
        start, end = i * STEP, min((i + 1) * STEP, len(data) / rate)
        if out and out[-1][2] == mouth:
            out[-1][1] = end
        else:
            out.append([start, end, mouth])
    return out


def write(path, data, rate):
    lines = ["<rhubarbResult>", "  <metadata>", "    <soundFile />",
             "    <duration>%.2f</duration>" % (len(data) / rate), "  </metadata>", "  <mouthCues>"]
    for start, end, mouth in cues(data, rate):
        lines.append('    <mouthCue start="%.2f" end="%.2f">%s</mouthCue>' % (start, end, mouth))
    lines += ["  </mouthCues>", "</rhubarbResult>", ""]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main():
    for folder in sys.argv[1:]:
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(".wav"):
                data, rate = read_wav(os.path.join(folder, name))
                write(os.path.join(folder, os.path.splitext(name)[0] + ".xml"), data, rate)
                print("записан", os.path.join(folder, os.path.splitext(name)[0] + ".xml"))


if __name__ == "__main__":
    main()
