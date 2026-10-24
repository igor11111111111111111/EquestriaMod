"""Своя музыка мода: копирует треки и собирает Module/Music/soundtrack.xml.

  py -3 tools/make_music.py [папка Module] [папка с треками]

Как устроена музыка в Bannerlord (проверено 2026-09-17 по коду и ванильным файлам):
  - движок (psai) собирает музыку из всех модулей, у которых в ModuleData/project.mbproj есть строка
    <file id="soln_soundtrack" name="Music/soundtrack.xml" type="soundtrack" /> (MBMusicManager);
  - номера тем в soundtrack.xml должны быть СВОБОДНЫМИ: тема с ванильным номером роняет игру при загрузке,
    поэтому у нас 41..48, а подмену ванильной темы на нашу делает src/EquestriaMusic.cs;
  - сегмент ссылается на файл через <Path>имя.wav</Path>, а лежит рядом Music/PC/имя.ogg;
  - psai нужны длина трека в сэмплах и частота дискретизации — читаем их прямо из ogg.
Таверна своей темы не имеет: там играют живые музыканты (SettlementMusiciansCampaignBehavior).
"""
import json
import os
import struct
import subprocess
import sys
import tempfile

BLENDER = os.environ.get("EQ_BLENDER", r"D:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe")
# Целевая средняя громкость (rms) готовых треков: все треки подтягиваются к ней (tools/music_gain.py).
# Для сравнения: главная тема ванильной игры — 0.21, самый тихий трек набора был 0.02.
TARGET_RMS = 0.30
# Битрейт готовых треков: он же задаёт вес музыки в моде (96 кбит/с — примерно 45 МБ на нынешние 21 трек).
BITRATE = 96000

MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
SRC = sys.argv[2] if len(sys.argv) > 2 else r"C:\SteamLibrary\steamapps\workshop\content\394360\1826643372\music"

# Номера тем — СВОИ (41..48), не ванильные: если номер повторяет ванильный, игра падает при загрузке
# (проверено 2026-09-18). Ванильную тему на нашу подменяет src/EquestriaMusic.cs в момент запуска музыки.
# тема -> (наш номер темы, тип psai, треки). Тип: 1 — карта, 3 — бой, 5 — короткая вставка, 7 — меню.
THEMES = {
    "Главное меню": (41, 7, ["Zykrath_Blessing_From_The_Stars"]),
    "Карта спокойная": (42, 1, [
        "Zykrath_Snowfall_in_Equestria", "Zykrath_Princess_of_Dreams", "hoi4mainthemeallies",
        "David_Larsen_Night_Sky", "Aida_Vedischeva_Forest_Deer", "Acryliks-But_The_Moon_Said_No",
        "Acryliks_Cloudspeak"]),
    "Карта тревожная": (43, 1, [
        "Zykrath_Inferior", "Artem_Yegorov_The_Heart_Carol", "Acryliks-But_The_Moon_Said_No"]),
    "Малый бой": (44, 3, [
        "Zvykar-March_of_Old_and_New", "Zvykar-Fire_Trek", "Sun", "Moon", "5_deioderan",
        "Brad_Cypy-Battle_For_Supremacy", "Armesto-Cheeki_Breeki_-_Bandit_Radio_orchestral_cover_"]),
    "Средний бой": (45, 3, [
        "Zvykar-March_of_Old_and_New", "Zvykar-Fire_Trek", "Sun", "Moon", "5_deioderan",
        "Brad_Cypy-Battle_For_Supremacy", "Armesto-Cheeki_Breeki_-_Bandit_Radio_orchestral_cover_"]),
    "Осада": (46, 3, [
        "Zvykar-March_of_Old_and_New", "Zvykar-Fire_Trek", "Sun", "Moon", "5_deioderan",
        "Katyusha_Instrumental", "Armesto-glory_to_arstotzka"]),
    "Победа": (47, 5, ["Neighsayer_Equestrias_Finest"]),
    "Поражение": (48, 5, ["DST-Darkess_extended"]),
}
# Настройки тем взяты у ванильных: карта — длинные фазы и паузы, бой — без пауз, вставки — короткие.
THEME_SETTINGS = {
    1: dict(intensity=0.01, phase=15, rest=(30, 90), priority=1),
    3: dict(intensity=0.5, phase=30, rest=(0, 0), priority=3),
    5: dict(intensity=0.5, phase=10, rest=(0, 0), priority=5),
    7: dict(intensity=0.5, phase=60, rest=(30, 60), priority=1),
}


def log(*a):
    print("[music]", *a, flush=True)


def ogg_info(path):
    """(частота дискретизации, длина в сэмплах) из ogg: заголовок Vorbis и granule последней страницы."""
    with open(path, "rb") as f:
        data = f.read(65536)
        i = data.find(b"\x01vorbis")
        rate = struct.unpack("<I", data[i + 12:i + 16])[0]
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - 65536))
        tail = f.read()
    last = tail.rfind(b"OggS")
    total = struct.unpack("<q", tail[last + 6:last + 14])[0] if last >= 0 else 0
    return rate, total


def segment_xml(name, seg_id, theme_id, rate, total, intensity):
    return f"""            <Segment>
              <Name>{name}</Name>
              <Id>{seg_id}</Id>
              <IsAutomaticBridgeSegment>false</IsAutomaticBridgeSegment>
              <Intensity>{intensity}</Intensity>
              <IsUsableAtStart>true</IsUsableAtStart>
              <IsUsableInMiddle>true</IsUsableInMiddle>
              <IsUsableAtEnd>true</IsUsableAtEnd>
              <AudioData>
                <_prebeatLengthInSamplesEnteredManually>0</_prebeatLengthInSamplesEnteredManually>
                <_postbeatLengthInSamplesEnteredManually>0</_postbeatLengthInSamplesEnteredManually>
                <Path>{name}.wav</Path>
                <Bpm>100</Bpm>
                <PreBeats>0</PreBeats>
                <PostBeats>0</PostBeats>
                <CalculatePostAndPrebeatLengthBasedOnBeats>false</CalculatePostAndPrebeatLengthBasedOnBeats>
                <PreBeatLengthInSamples>0</PreBeatLengthInSamples>
                <PostBeatLengthInSamples>0</PostBeatLengthInSamples>
                <TotalLengthInSamples>{total}</TotalLengthInSamples>
                <SampleRate>{rate}</SampleRate>
              </AudioData>
              <CalculatePostAndPrebeatLengthBasedOnBeats>false</CalculatePostAndPrebeatLengthBasedOnBeats>
              <PreBeatLengthInSamples>0</PreBeatLengthInSamples>
              <PostBeatLengthInSamples>0</PostBeatLengthInSamples>
              <PreBeats>0</PreBeats>
              <PostBeats>0</PostBeats>
              <Bpm>100</Bpm>
              <SampleRate>{rate}</SampleRate>
              <BitsPerSample>16</BitsPerSample>
              <ThemeId>{theme_id}</ThemeId>
              <Serialization_ManuallyBlockedSegmentIds />
              <Serialization_ManuallyLinkedSegmentIds />
              <DefaultCompatibiltyAsFollower>allowed_implicitly</DefaultCompatibiltyAsFollower>
            </Segment>"""


def main():
    music_dir = os.path.join(MOD, "Music")
    pc_dir = os.path.join(music_dir, "PC")
    os.makedirs(pc_dir, exist_ok=True)
    used = {name for _, _, tracks in THEMES.values() for name in tracks}
    missing = [n for n in used if not os.path.exists(os.path.join(SRC, n + ".ogg"))]
    if missing:
        raise SystemExit("[music] нет файлов: " + ", ".join(sorted(missing)))
    jobs = []
    for name in sorted(used):
        src = os.path.join(SRC, name + ".ogg")
        dst = os.path.join(pc_dir, name + ".ogg")
        if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src):
            jobs.append([src, dst, TARGET_RMS, BITRATE])
    if jobs:
        log(f"выравнивание громкости {len(jobs)} треков в Blender (rms {TARGET_RMS}, {BITRATE // 1000} кбит/с)")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(jobs, f)
            task = f.name
        gain = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music_gain.py")
        subprocess.run([BLENDER, "--background", "--factory-startup", "--python", gain, "--", task],
                       check=True, stdout=subprocess.DEVNULL)
        os.unlink(task)
    info = {}
    for name in sorted(used):
        dst = os.path.join(pc_dir, name + ".ogg")
        rate, total = ogg_info(dst)
        info[name] = (rate, total)
        log(f"{name}: {total / max(rate, 1) / 60:.1f} мин, {rate} Гц")

    seg_id, group_id, themes = 1000, 2000, []
    for title, (theme_id, theme_type, tracks) in THEMES.items():
        st = THEME_SETTINGS[theme_type]
        segments = []
        for name in tracks:
            rate, total = info[name]
            segments.append(segment_xml(name, seg_id, theme_id, rate, total, st["intensity"]))
            seg_id += 1
        themes.append(f"""    <Theme>
      <Name>{title}</Name>
      <Id>{theme_id}</Id>
      <ThemeTypeInt>{theme_type}</ThemeTypeInt>
      <Serialization_ManuallyBlockedThemeIds />
      <IntensityAfterRest>{st["intensity"]}</IntensityAfterRest>
      <MusicPhaseSecondsAfterRest>{st["phase"]}</MusicPhaseSecondsAfterRest>
      <MusicPhaseSecondsGeneral>{st["phase"]}</MusicPhaseSecondsGeneral>
      <RestSecondsMin>{st["rest"][0]}</RestSecondsMin>
      <RestSecondsMax>{st["rest"][1]}</RestSecondsMax>
      <FadeoutMs>2000</FadeoutMs>
      <Priority>{st["priority"]}</Priority>
      <WeightingSwitchGroups>0.5</WeightingSwitchGroups>
      <WeightingIntensityVsVariance>0.5</WeightingIntensityVsVariance>
      <WeightingLowPlaycountVsRandom>0.5</WeightingLowPlaycountVsRandom>
      <Groups>
        <Group>
          <Name>default group</Name>
          <Segments>
{chr(10).join(segments)}
          </Segments>
          <Description />
          <Serialization_Id>{group_id}</Serialization_Id>
          <Serialization_ManuallyBlockedGroupIds />
          <Serialization_ManuallyLinkedGroupIds />
          <Serialization_ManualBridgeSegmentIds />
        </Group>
      </Groups>
    </Theme>""")
        group_id += 1
        log(f"тема {theme_id} «{title}»: {len(tracks)} треков")

    text = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- Музыка мода. Собран tools/make_music.py — правьте скрипт, не этот файл.
     Номера тем — из enum MusicTheme движка; файлы лежат в Music/PC. -->
<PsaiProject xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <SerializedByProtocolVersion>1.0</SerializedByProtocolVersion>
  <Properties>
    <ModuleIdPrefix></ModuleIdPrefix>
    <WarningThresholdPreBeatMillis>1500</WarningThresholdPreBeatMillis>
    <DefaultCalculatePostAndPrebeatLengthBasedOnBeats>false</DefaultCalculatePostAndPrebeatLengthBasedOnBeats>
    <DefaultSegmentSuitabilites>3</DefaultSegmentSuitabilites>
    <ForceFullRebuild>true</ForceFullRebuild>
    <VolumeBoost>0</VolumeBoost>
    <ExportSoundQualityInPercent>90</ExportSoundQualityInPercent>
    <DefaultPrebeats>0</DefaultPrebeats>
    <DefaultPostbeats>0</DefaultPostbeats>
    <DefaultBpm>100</DefaultBpm>
    <DefaultPrebeatLengthInSamples>0</DefaultPrebeatLengthInSamples>
    <DefaultPostbeatLengthInSamples>0</DefaultPostbeatLengthInSamples>
  </Properties>
  <Themes>
{chr(10).join(themes)}
  </Themes>
</PsaiProject>
"""
    path = os.path.join(music_dir, "soundtrack.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    log("записан", path, f"({len(used)} файлов в Music/PC)")


if __name__ == "__main__":
    main()
