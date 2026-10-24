# Материал чейнджлинга и привязка его мешей — после того, как FBX и текстуры импортированы в редакторе.
#
#   .\tools\changeling_material.ps1
#
# Порядок работы:
#   1. blender --background assets\twilight_anthro\export\eq_twilight.blend --python tools\make_changeling_model.py
#      -- "<модель.fbx>" "<папка assets\changeling3d>"   — режет модель на части и пишет FBX;
#   2. py -3 tools\make_changeling_textures.py         — делает eq_changeling_body_d/_n/_s.png;
#   3. в Modding Kit: импорт assets\changeling3d\eq_changeling.fbx и трёх текстур (пакет twilight);
#   4. этот скрипт — всё остальное кодом:
#        материал eq_changeling_body — копия eq_twilight_body (шейдер кожи со скиннингом) со своими
#        текстурами; меши eq_changeling_* получают этот материал; раса снимается с заглушки пони.
# Хвост и крылья в слоты не кладём: их вешает на скелет src/EquestriaBodyParts.cs, как хвост пони.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"

Write-Host "== Текстуры в пакете" -ForegroundColor Cyan
# Выгрузкой не проверить: у импортированных редактором текстур в пакете нет пикселей (только
# ссылка на PNG), поэтому смотрим сами записи ассетов.
foreach ($name in "eq_changeling_body_d", "eq_changeling_body_n", "eq_changeling_body_s") {
    $found = & $Tool info $Assets $name 2>&1 | Select-String -Pattern "^== $name`: Texture"
    if (-not $found) {
        throw "В пакете нет текстуры $name — импортируйте её в редакторе из assets\changeling3d\textures"
    }
    Write-Host "  $name — есть"
}

Write-Host "== Материал eq_changeling_body" -ForegroundColor Cyan
& $Tool mat-clone $Assets eq_twilight_body (Join-Path $Assets "twilight\eq_changeling_body_mtl.tpac") eq_changeling_body `
    0=eq_changeling_body_d 1=eq_changeling_body_d 2=eq_changeling_body_n 3=eq_changeling_body_n 4=eq_changeling_body_s
if ($LASTEXITCODE -ne 0) { throw "материал не создан" }

# Своего материала волос у чейнджлинга НЕТ, в отличие от дракона и грифона: макушку в причёску
# мы не режем (на ней уши и рог, а трутням причёска не выдаётся — см. make_changeling_model.py),
# гривы у расы отдельные, со своим материалом (tools/make_changeling_hair.py).

Write-Host "== Материал крыльев и хвоста (цвет причёски)" -ForegroundColor Cyan
# Крылья и хвост красятся цветом гривы из окна внешности (src/EquestriaBodyParts.cs, HairTinted), а этот
# цвет читает только шейдер волос: копия female_hair_mat с текстурой тела чейнджлинга.
$Native = Join-Path $Game "Modules\Native\AssetPackages"
& $Tool mat-clone "$Native;$Assets" female_hair_mat (Join-Path $Assets "twilight\eq_changeling_tint_mtl.tpac") `
    eq_changeling_tint 0=eq_changeling_body_d 1=eq_changeling_body_n
if ($LASTEXITCODE -ne 0) { throw "материал крыльев не создан" }

Write-Host "== Привязка мешей" -ForegroundColor Cyan
& $Tool mesh-setmat $Assets (Join-Path $Assets "twilight\eq_changeling_geo.tpac") eq_changeling_ eq_changeling_body
if ($LASTEXITCODE -ne 0) { throw "меши не привязаны" }
foreach ($m in "eq_changeling_wings", "eq_changeling_tail") {
    & $Tool mesh-setmat $Assets (Join-Path $Assets "twilight\eq_changeling_geo.tpac") $m eq_changeling_tint
    if ($LASTEXITCODE -ne 0) { throw "$m не привязан" }
}

Write-Host "== Раса без заглушки" -ForegroundColor Cyan
$race = Join-Path $Root "tools\make_pony_race.py"
$text = [IO.File]::ReadAllText($race)
$fixed = $text -replace 'NOT_IMPORTED = \{"changeling"\}[^\r\n]*', 'NOT_IMPORTED = set()'
if ($fixed -ne $text) {
    [IO.File]::WriteAllText($race, $fixed, (New-Object Text.UTF8Encoding($false)))
    Write-Host "  changeling убран из NOT_IMPORTED"
}
py $race (Join-Path $Game "Modules") (Join-Path $Root "Module")
Write-Host "Готово: запускайте игру, чейнджлинг на новой модели." -ForegroundColor Green
