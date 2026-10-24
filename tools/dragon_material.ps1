# The dragon material and the binding of its meshes, after the FBX and textures have been imported in the editor.
#
#   .\tools\dragon_material.ps1
#
# Workflow:
#   1. blender --background assets\twilight_anthro\export\eq_twilight.blend --python tools\make_dragon.py
#      -- "<model.fbx>" "<assets\dragon folder>"   - cuts the model into parts and writes the FBX;
#   2. py -3 tools\make_dragon_textures.py         - makes eq_dragon_body_d/_n/_s.png;
#   3. in the Modding Kit: import assets\dragon\eq_dragon.fbx and the three textures (package twilight);
#   4. this script does the rest in code:
#        the eq_dragon_body material is a copy of eq_twilight_body (skin shader with skinning) with its own
#        textures; the eq_dragon_* meshes get this material; the race is taken off the pony placeholder.
# The tail and wings are not put into slots: src/EquestriaBodyParts.cs hangs them on the skeleton, like the pony tail.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"

Write-Host "== Текстуры в пакете" -ForegroundColor Cyan
# Cannot be checked by exporting: textures imported by the editor have no pixels in the package (only
# a reference to the PNG), so we look at the asset records themselves.
foreach ($name in "eq_dragon_body_d", "eq_dragon_body_n", "eq_dragon_body_s") {
    $found = & $Tool info $Assets $name 2>&1 | Select-String -Pattern "^== $name`: Texture"
    if (-not $found) {
        throw "В пакете нет текстуры $name — импортируйте её в редакторе из assets\dragon\textures"
    }
    Write-Host "  $name — есть"
}

Write-Host "== Материал eq_dragon_body" -ForegroundColor Cyan
& $Tool mat-clone $Assets eq_twilight_body (Join-Path $Assets "twilight\eq_dragon_body_mtl.tpac") eq_dragon_body `
    0=eq_dragon_body_d 1=eq_dragon_body_d 2=eq_dragon_body_n 3=eq_dragon_body_n 4=eq_dragon_body_s
if ($LASTEXITCODE -ne 0) { throw "материал не создан" }

Write-Host "== Материал рогов и гребня" -ForegroundColor Cyan
# The hair colour from the appearance window is only listened to by the vanilla hair shader, so the crest needs its own
# material: a copy of female_hair_mat (bumpmap + skinning, two textures) with our textures.
# The source lies in the vanilla packages and the textures in ours, so there are two folders separated by ";".
$Native = Join-Path $Game "Modules\Native\AssetPackages"
& $Tool mat-clone "$Native;$Assets" female_hair_mat (Join-Path $Assets "twilight\eq_dragon_hair_mtl.tpac") `
    eq_dragon_hair 0=eq_dragon_body_d 1=eq_dragon_body_n
if ($LASTEXITCODE -ne 0) { throw "материал гребня не создан" }

Write-Host "== Привязка мешей" -ForegroundColor Cyan
& $Tool mesh-setmat $Assets (Join-Path $Assets "twilight\eq_dragon_geo.tpac") eq_dragon_ eq_dragon_body
if ($LASTEXITCODE -ne 0) { throw "меши не привязаны" }
# the crest gets its own material, on top of the common binding
& $Tool mesh-setmat $Assets (Join-Path $Assets "twilight\eq_dragon_geo.tpac") eq_dragon_hair eq_dragon_hair
if ($LASTEXITCODE -ne 0) { throw "гребень не привязан" }

Write-Host "== Раса без заглушки" -ForegroundColor Cyan
$race = Join-Path $Root "tools\make_pony_race.py"
$text = [IO.File]::ReadAllText($race)
$fixed = $text -replace 'NOT_IMPORTED = \{"dragon"\}[^\r\n]*', 'NOT_IMPORTED = set()'
if ($fixed -ne $text) {
    [IO.File]::WriteAllText($race, $fixed, (New-Object Text.UTF8Encoding($false)))
    Write-Host "  dragon убран из NOT_IMPORTED"
}
py $race (Join-Path $Game "Modules") (Join-Path $Root "Module")
Write-Host "Готово: запускайте игру, дракон на своей модели." -ForegroundColor Green
