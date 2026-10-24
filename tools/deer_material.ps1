# Doe material and binding of her meshes - after the textures have been imported in the editor.
#
#   .\tools\deer_material.ps1
#
# Order: tools\make_deer_textures.py puts eq_deer_body_d/_n/_s.png into assets\deer\textures,
# they are imported in the editor (Resource Browser -> Import; package twilight). Then everything is done by code:
#   1. material eq_deer_body - a copy of eq_twilight_body (skin shader, skinning) with its own textures;
#   2. meshes eq_deer_* in the geometry package get this material;
#   3. the deer race is taken off the pony placeholder: "deer" leaves NOT_IMPORTED, skins are rebuilt.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"

Write-Host "== Текстуры в пакете" -ForegroundColor Cyan
# Cannot be checked by exporting: textures imported by the editor have no pixels in the package (only
# a link to the PNG), so we look at the asset records themselves.
foreach ($name in "eq_deer_body_d", "eq_deer_body_n", "eq_deer_body_s") {
    $found = & $Tool info $Assets $name 2>&1 | Select-String -Pattern "^== $name`: Texture"
    if (-not $found) {
        throw "В пакете нет текстуры $name — импортируйте её в редакторе из assets\deer\textures"
    }
    Write-Host "  $name — есть"
}

Write-Host "== Материал eq_deer_body" -ForegroundColor Cyan
& $Tool mat-clone $Assets eq_twilight_body (Join-Path $Assets "twilight\eq_deer_body_mtl.tpac") eq_deer_body `
    0=eq_deer_body_d 1=eq_deer_body_d 2=eq_deer_body_n 3=eq_deer_body_n 4=eq_deer_body_s
if ($LASTEXITCODE -ne 0) { throw "материал не создан" }

Write-Host "== Материал рогов" -ForegroundColor Cyan
# Hair color from the appearance window is listened to only by the vanilla hair shader, so the antlers need
# their own material - a copy of female_hair_mat (bumpmap + skinning, two textures) with our textures.
# The source is in the vanilla packages and the textures in ours, so there are two folders separated by «;».
$Native = Join-Path $Game "Modules\Native\AssetPackages"
& $Tool mat-clone "$Native;$Assets" female_hair_mat (Join-Path $Assets "twilight\eq_deer_hair_mtl.tpac") `
    eq_deer_hair 0=eq_deer_body_d 1=eq_deer_body_n
if ($LASTEXITCODE -ne 0) { throw "материал рогов не создан" }

Write-Host "== Привязка мешей" -ForegroundColor Cyan
# Where the editor puts the mesh package depends on which package was selected on import,
# so we search instead of setting the path.
$Found = @(Get-ChildItem $Assets -Recurse -Filter "eq_deer_geo.tpac")
if ($Found.Count -eq 0) {
    throw "не найден eq_deer_geo.tpac — импортируйте assets\deer\eq_deer.fbx в редакторе"
}
if ($Found.Count -gt 1) {
    # Two copies = the import landed in another package and the old one remained. Silently taking the first is
    # not allowed: the binding would go to outdated meshes, and the game would pick up some of its own.
    throw "пакетов eq_deer_geo.tpac несколько, удалите лишние:`n  " + ($Found.FullName -join "`n  ")
}
$Geo = $Found[0]
Write-Host "  пакет: $($Geo.FullName)"
& $Tool mesh-setmat $Assets $Geo.FullName eq_deer_ eq_deer_body
if ($LASTEXITCODE -ne 0) { throw "меши не привязаны" }
# the antlers get their own material, on top of the common binding
& $Tool mesh-setmat $Assets $Geo.FullName eq_deer_hair eq_deer_hair
if ($LASTEXITCODE -ne 0) { throw "рога не привязаны" }

Write-Host "== Раса без заглушки" -ForegroundColor Cyan
$race = Join-Path $Root "tools\make_pony_race.py"
$text = [IO.File]::ReadAllText($race)
$fixed = $text -replace 'NOT_IMPORTED = \{"deer"\}', 'NOT_IMPORTED = set()'
if ($fixed -ne $text) {
    [IO.File]::WriteAllText($race, $fixed, (New-Object Text.UTF8Encoding($false)))
    Write-Host "  deer убран из NOT_IMPORTED"
}
py $race (Join-Path $Game "Modules") (Join-Path $Root "Module")
Write-Host "Готово: запускайте игру, олениха на своей модели." -ForegroundColor Green
