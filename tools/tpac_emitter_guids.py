"""GUID эмиттеров ванильных эффектов частиц из Modules/Native/AssetPackages/particles.tpac.

Нужны для <emitter_overrides> в прафабах (Module/Prefabs/eq_flight_fx.xml, eq_spell_fx.xml):
эмиттер там выбирается только по guid, а в XML игры (ModuleData/particle_systems*.xml) GUID
эмиттеров нет — только GUID эффекта. Выбор по name роняет игру при загрузке прафабов.

Формат (выяснен 10.10.2026, проверен на psys_game_burning_agent — три GUID совпали с теми,
что использует The Old Realms):
  заголовок пакета: ... u32 len + имя эффекта, 8 нулей, маркер bb1bdbcacd6ac934, u32,
  затем записи сегментов (u64 смещение, u64 размер распакованный, u64 размер сжатый).
  У эффектов с текстурой первый сегмент — страница текстуры (1 МБ), данные эффекта идут
  сразу за ней. Данные — один LZ4-блок: u32 len + sound_code, служебные байты, затем на
  каждый эмиттер: 02 00 00 00, GUID эмиттера, 32 байта (GUID меша sample_mesh или нули),
  GUID материала, u32 len + имя эмиттера, параметры. В одной странице может лежать несколько
  эффектов — берём эмиттеры с начала блока, сколько их в XML.

    py -3 tools/tpac_emitter_guids.py psys_game_campfire falling_leaves psys_game_hoof_dust_on_default
"""
import re
import struct
import sys
import uuid

TPAC = (r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
        r"\Modules\Native\AssetPackages\particles.tpac")
MAGIC = bytes.fromhex("bb1bdbcacd6ac934")
EMITTER = re.compile(rb"\x02\x00\x00\x00(.{16})(.{32})(.{16})(.)\x00\x00\x00([A-Za-z0-9_ ]{1,40})", re.S)


def lz4_block(src):
    out = bytearray()
    i = 0
    n = len(src)
    try:
        while i < n:
            tok = src[i]
            i += 1
            ll = tok >> 4
            if ll == 15:
                while True:
                    b = src[i]
                    i += 1
                    ll += b
                    if b != 255:
                        break
            out += src[i:i + ll]
            i += ll
            if i >= n:
                break
            off = src[i] | (src[i + 1] << 8)
            i += 2
            ml = tok & 15
            if ml == 15:
                while True:
                    b = src[i]
                    i += 1
                    ml += b
                    if b != 255:
                        break
            ml += 4
            start = len(out) - off
            if off == 0 or start < 0:
                break
            for k in range(ml):
                out.append(out[start + k])
    except IndexError:
        pass
    return bytes(out)


def guid(b):
    return "{" + str(uuid.UUID(bytes_le=b)).upper() + "}"


def main():
    data = open(TPAC, "rb").read()
    for name in sys.argv[1:]:
        nb = name.encode()
        pos = data.find(struct.pack("<I", len(nb)) + nb)
        if pos < 0:
            print(name, ": не найден")
            continue
        m = data.find(MAGIC, pos, pos + 200)
        effect = guid(data[pos - 20:pos - 4])
        off, usize, csize = struct.unpack_from("<QQQ", data, m + 12)
        dec = lz4_block(data[off:off + csize])
        if not EMITTER.search(dec[:20000]):
            # первый сегмент — текстура, эффект лежит сразу за ней
            dec = lz4_block(data[off + csize:off + csize + 300000])
        print("%s  эффект %s" % (name, effect))
        for em in EMITTER.finditer(dec[:40000]):
            ln = em.group(4)[0]
            print("    эмиттер %-20s %s" % (em.group(5)[:ln].decode(), guid(em.group(1))))


if __name__ == "__main__":
    main()
