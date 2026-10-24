# Материал гиппогрифа и привязка его мешей — после того, как FBX и текстуры импортированы в редакторе.
#
#   .\tools\hippogriff_material.ps1
#
# Порядок работы:
#   1. blender --background assets\twilight_anthro\export\eq_twilight.blend --python tools\make_hippogriff.py
#      -- "<модель.fbx>" "<папка assets\hippogriff>"   — режет модель на части и пишет FBX;
#   2. py -3 tools\make_hippogriff_textures.py         — делает eq_hippogriff_body_d/_n/_s.png;
#   3. в Modding Kit: импорт assets\hippogriff\eq_hippogriff.fbx и трёх текстур (пакет twilight);
#   4. этот скрипт — всё остальное кодом:
#        материал eq_hippogriff_body — копия eq_twilight_body (шейдер кожи со скиннингом) со своими
#        текстурами; меши eq_hippogriff_* получают этот материал; раса снимается с заглушки пони.
# Хвост и крылья в слоты не кладём: их вешает на скелет src/EquestriaBodyParts.cs, как хвост пони.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"

Write-Host "== Текстуры в пакете" -ForegroundColor Cyan
# Выгрузкой не проверить: у импортированных редактором текстур в пакете нет пикселей (только
# ссылка на PNG), поэтому смотрим сами записи ассетов.
foreach ($name in "eq_hippogriff_body_d", "eq_hippogriff_body_n", "eq_hippogriff_body_s") {
    $found = & $Tool info $Assets $name 2>&1 | Select-String -Pattern "^== $name`: Texture"
    if (-not $found) {
        throw "В пакете нет текстуры $name — импортируйте её в редакторе из assets\hippogriff\textures"
    }
    Write-Host "  $name — есть"
}

Write-Host "== Материал eq_hippogriff_body" -ForegroundColor Cyan
& $Tool mat-clone $Assets eq_twilight_body (Join-Path $Assets "twilight\eq_hippogriff_body_mtl.tpac") eq_hippogriff_body `
    0=eq_hippogriff_body_d 1=eq_hippogriff_body_d 2=eq_hippogriff_body_n 3=eq_hippogriff_body_n 4=eq_hippogriff_body_s
if ($LASTEXITCODE -ne 0) { throw "материал не создан" }

Write-Host "== Материал гребня" -ForegroundColor Cyan
# Цвет волос из окна внешности слушает только ванильный шейдер волос, поэтому хохолку нужен свой
# материал — копия female_hair_mat (bumpmap + skinning, две текстуры) с нашими текстурами.
# Исходник лежит в ванильных пакетах, а текстуры в нашем, поэтому папок две через «;».
$Native = Join-Path $Game "Modules\Native\AssetPackages"
& $Tool mat-clone "$Native;$Assets" female_hair_mat (Join-Path $Assets "twilight\eq_hippogriff_hair_mtl.tpac") `
    eq_hippogriff_hair 0=eq_hippogriff_body_d 1=eq_hippogriff_body_n
if ($LASTEXITCODE -ne 0) { throw "материал гребня не создан" }

Write-Host "== Привязка мешей" -ForegroundColor Cyan
& $Tool mesh-setmat $Assets (Join-Path $Assets "twilight\eq_hippogriff_geo.tpac") eq_hippogriff_ eq_hippogriff_body
if ($LASTEXITCODE -ne 0) { throw "меши не привязаны" }
# хохолку — свой материал, поверх общей привязки
& $Tool mesh-setmat $Assets (Join-Path $Assets "twilight\eq_hippogriff_geo.tpac") eq_hippogriff_hair eq_hippogriff_hair
if ($LASTEXITCODE -ne 0) { throw "хохолок не привязан" }

Write-Host "== Раса без заглушки" -ForegroundColor Cyan
$race = Join-Path $Root "tools\make_pony_race.py"
$text = [IO.File]::ReadAllText($race)
$fixed = $text -replace 'NOT_IMPORTED = \{"hippogriff"\}[^\r\n]*', 'NOT_IMPORTED = set()'
if ($fixed -ne $text) {
    [IO.File]::WriteAllText($race, $fixed, (New-Object Text.UTF8Encoding($false)))
    Write-Host "  hippogriff убран из NOT_IMPORTED"
}
py $race (Join-Path $Game "Modules") (Join-Path $Root "Module")
Write-Host "Готово: запускайте игру, дракон на своей модели." -ForegroundColor Green
