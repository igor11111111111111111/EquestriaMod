# Changeling material and binding of its meshes — after the FBX and textures are imported in the editor.
#
#   .\tools\changeling_material.ps1
#
# Workflow:
#   1. blender --background assets\twilight_anthro\export\eq_twilight.blend --python tools\make_changeling_model.py
#      -- "<model.fbx>" "<assets\changeling3d folder>"   — cuts the model into parts and writes FBX;
#   2. py -3 tools\make_changeling_textures.py         — makes eq_changeling_body_d/_n/_s.png;
#   3. in the Modding Kit: import assets\changeling3d\eq_changeling.fbx and the three textures (twilight pack);
#   4. this script — everything else in code:
#        material eq_changeling_body — a copy of eq_twilight_body (skin shader with skinning) with its own
#        textures; the eq_changeling_* meshes get this material; the race is taken off the pony stub.
# Tail and wings are not put into slots: src/EquestriaBodyParts.cs attaches them to the skeleton, like the pony tail.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"

Write-Host "== Текстуры в пакете" -ForegroundColor Cyan
# Cannot be checked by exporting: textures imported by the editor have no pixels in the pack (only
# a link to the PNG), so we look at the asset records themselves.
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

# The changeling has NO hair material of its own, unlike the dragon and the griffon: we do not cut the
# crown into a hairstyle (it carries the ears and the horn, and drones get no hairstyle — see
# make_changeling_model.py); the race's manes are separate, with their own material
# (tools/make_changeling_hair.py).

Write-Host "== Материал крыльев и хвоста (цвет причёски)" -ForegroundColor Cyan
# Wings and tail are tinted with the mane colour from the appearance screen (src/EquestriaBodyParts.cs,
# HairTinted), and only the hair shader reads that colour: a copy of female_hair_mat with the changeling
# body texture.
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
