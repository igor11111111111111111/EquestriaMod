# -*- coding: utf-8 -*-
r"""Выгрузка ванильных текстур брони в assets\reference\vanilla_armor\<меш>\.

  py -3 tools/dump_armor_textures.py               # чего не хватает пакету улья
  py -3 tools/dump_armor_textures.py --force       # заново всё

Из них tools/hive_armor.py печёт хитиновые: нужны цвет (_d) и маска клана (_c), нормали и блики
остаются ванильными. Раньше это делалось руками по мешу, и у 23 вещей текстур не оказалось вовсе:
меш есть, папка есть, а в ней один FBX (обнаружено 25.09.2026).

Где что лежит:
  Modules\Native\AssetPackages    — меши и материалы, по ним узнаём имена текстур;
  Modules\Native\EmAssetPackages  — редакторские пакеты, и ТОЛЬКО там у текстур есть пиксели.
    В игровых пакетах картинка почти всегда пустая («has no pixel data»).
Каждый запуск инструмента заново читает сотни пакетов, поэтому все имена передаём списком через
запятую и обходимся тремя запусками на всю броню.
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import armor_catalog  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "tpac_export", "bin", "Release", "tpac_export.exe")
OUT = os.path.join(ROOT, "assets", "reference", "vanilla_armor")
NATIVE = os.path.join(armor_catalog.GAME, "Modules", "Native", "AssetPackages")
EDITOR = os.path.join(armor_catalog.GAME, "Modules", "Native", "EmAssetPackages")
PACK = "changeling"


def log(*a):
    print("[textures]", *a, flush=True)


def run(*args):
    out = subprocess.run([TOOL] + list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         encoding="utf-8", errors="replace")
    return out.stdout.splitlines()


def is_guid(text):
    return set(text.lower()) <= set("0123456789abcdef-") and len(text) > 16


def has_diffuse(mesh):
    folder = os.path.join(OUT, mesh)
    return os.path.isdir(folder) and any(n.endswith("_d.dds") for n in os.listdir(folder))


def materials_of(meshes):
    """меш -> список материалов; пустой список, если у подмешей материал не проставлен"""
    found = {}
    for line in run("mesh-mats", NATIVE, ",".join(meshes)):
        name, _, rest = line.partition(": ")
        if name not in meshes or not rest:
            continue
        # У части ванильных рукавиц материал пустой (нулевой guid) — их спасает fallback
        # в tools/hive_material.ps1, текстуры им не нужны.
        found[name] = [m for m in (p.strip() for p in rest.split(",")) if m and not is_guid(m)]
    return found


def textures_of(mats):
    """материал -> имена текстур из слотов 0 (цвет) и 1 (маска клана)"""
    found = {}
    current = None
    for line in run("mat-info", NATIVE, ",".join(mats)):
        if line.startswith("material "):
            current = line.split()[1]
            found.setdefault(current, [])
        elif current and line.strip().startswith(("tex[0]", "tex[1]")):
            found[current].append(line.split("=")[-1].strip())
    return found


def main():
    force = "--force" in sys.argv
    meshes = sorted({row["mesh"] for row in armor_catalog.pieces(PACK)})
    log("мешей в пакете %s: %d" % (PACK, len(meshes)))
    need = [m for m in meshes if force or not has_diffuse(m)]
    if not need:
        log("все текстуры на месте")
        return
    log("выгружаем: %d" % len(need))

    mats = materials_of(need)
    all_mats = sorted({m for row in mats.values() for m in row})
    tex = textures_of(all_mats)

    want = {}
    for mesh in need:
        names = sorted({n for m in mats.get(mesh, []) for n in tex.get(m, [])})
        if names:
            want[mesh] = names
        else:
            log("  %-42s материал без текстур (%s)" % (mesh, ", ".join(mats.get(mesh, [])) or "нет"))
    if not want:
        raise SystemExit("не нашёл ни одной текстуры")

    # Одним заходом по редакторским пакетам на все имена; по папкам мешей раскладываем сами.
    # Имена набора отличаются хвостом (_d, _c, _n, _s) — забираем набор целиком: цвет и маску
    # читает hive_armor.py, остальное пригодится глазами сверить.
    bases = sorted({n[:-2] for names in want.values() for n in names})
    temp = tempfile.mkdtemp(prefix="armor_tex_")
    log("выгружаю %d наборов текстур из редакторских пакетов…" % len(bases))
    for line in run("texture", EDITOR, ",".join(bases), temp, ".dds"):
        if line.startswith("FAILED"):
            log(" ", line)

    for mesh, names in sorted(want.items()):
        folder = os.path.join(OUT, mesh)
        os.makedirs(folder, exist_ok=True)
        count = 0
        for base in sorted({n[:-2] for n in names}):
            for name in os.listdir(temp):
                if name.startswith(base + "_") and name.endswith(".dds"):
                    shutil.copyfile(os.path.join(temp, name), os.path.join(folder, name))
                    count += 1
        log("  %-42s %d текстур" % (mesh, count))
    shutil.rmtree(temp, ignore_errors=True)
    log("готово: дальше py -3 tools/hive_armor.py")


main()
