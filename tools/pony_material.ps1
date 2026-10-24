# Pony material and binding of her meshes — after the textures are imported in the editor.
#
#   .\tools\pony_material.ps1
#
# Order: tools\make_pony_textures.py puts eq_pony_body_d/_n/_s.png into assets\pony\textures,
# they are imported in the editor (Resource Browser -> Import; package twilight). Then everything by code:
#   1. material eq_pony_body — a copy of eq_twilight_body (skin shader, skinning) with its own textures;
#   2. meshes eq_pony_* in the geometry package get this material;
#   3. the new pony race is taken off the pony placeholder: "pony" leaves NOT_IMPORTED, skins are rebuilt.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"

Write-Host "== Текстуры в пакете" -ForegroundColor Cyan
# Cannot be checked by exporting: textures imported by the editor have no pixels in the package (only
# a link to the PNG), so we look at the asset records themselves.
foreach ($name in "eq_pony_body_d", "eq_pony_body_n", "eq_pony_body_s") {
    $found = & $Tool info $Assets $name 2>&1 | Select-String -Pattern "^== $name`: Texture"
    if (-not $found) {
        throw "В пакете нет текстуры $name — импортируйте её в редакторе из assets\pony\textures"
    }
    Write-Host "  $name — есть"
}

Write-Host "== Материал eq_pony_body" -ForegroundColor Cyan
& $Tool mat-clone $Assets eq_twilight_body (Join-Path $Assets "twilight\eq_pony_body_mtl.tpac") eq_pony_body `
    0=eq_pony_body_d 1=eq_pony_body_d 2=eq_pony_body_n 3=eq_pony_body_n 4=eq_pony_body_s
if ($LASTEXITCODE -ne 0) { throw "материал не создан" }

Write-Host "== Материал гривы" -ForegroundColor Cyan
# Only the vanilla hair shader listens to the hair color from the appearance screen, so the mane needs
# its own material — a copy of female_hair_mat (bumpmap + skinning, two textures) with our textures.
# The source is in the vanilla packages and the textures in ours, so there are two folders joined by ";".
$Native = Join-Path $Game "Modules\Native\AssetPackages"
& $Tool mat-clone "$Native;$Assets" female_hair_mat (Join-Path $Assets "twilight\eq_pony_hair_mtl.tpac") `
    eq_pony_hair 0=eq_pony_body_d 1=eq_pony_body_n
if ($LASTEXITCODE -ne 0) { throw "материал гривы не создан" }

Write-Host "== Привязка мешей" -ForegroundColor Cyan
# Where the editor puts the mesh package depends on which package was chosen at import,
# so we search instead of setting the path.
$Found = @(Get-ChildItem $Assets -Recurse -Filter "eq_pony_geo.tpac")
if ($Found.Count -eq 0) {
    throw "не найден eq_pony_geo.tpac — импортируйте assets\pony\eq_pony.fbx в редакторе"
}
if ($Found.Count -gt 1) {
    # Two copies = the import went into another package and the old one stayed. Silently taking the
    # first is not allowed: the binding would go to stale meshes, and the game would pick up some others.
    throw "пакетов eq_pony_geo.tpac несколько, удалите лишние:`n  " + ($Found.FullName -join "`n  ")
}
$Geo = $Found[0]
Write-Host "  пакет: $($Geo.FullName)"
& $Tool mesh-setmat $Assets $Geo.FullName eq_pony_ eq_pony_body
if ($LASTEXITCODE -ne 0) { throw "меши не привязаны" }
# the mane, horn, tail and wings get the hair material: they are tinted with the hairstyle color from the
# appearance screen (src/EquestriaBodyParts.cs, HairTinted), and only the hair shader reads that color
foreach ($m in "eq_pony_hair", "eq_pony_horn", "eq_pony_tail", "eq_pony_wings") {
    & $Tool mesh-setmat $Assets $Geo.FullName $m eq_pony_hair
    if ($LASTEXITCODE -ne 0) { throw "$m не привязан" }
}

Write-Host "== Раса без заглушки" -ForegroundColor Cyan
$race = Join-Path $Root "tools\make_pony_race.py"
$text = [IO.File]::ReadAllText($race)
$fixed = $text -replace 'NOT_IMPORTED = \{"pony"\}', 'NOT_IMPORTED = set()'
if ($fixed -ne $text) {
    [IO.File]::WriteAllText($race, $fixed, (New-Object Text.UTF8Encoding($false)))
    Write-Host "  pony убран из NOT_IMPORTED"
}
py $race (Join-Path $Game "Modules") (Join-Path $Root "Module")

Write-Host "== Предмет-хвост на новый меш" -ForegroundColor Cyan
# The eq_pony_tail item is needed by screens without a character agent (race review). While the pony was
# not imported, it pointed to Twilight's tail; now — to the tail of the new model.
$items = Join-Path $Root "tools\make_items.py"
$text = [IO.File]::ReadAllText($items)
$fixed = $text -replace 'mesh="eq_twilight_tail"', 'mesh="eq_pony_tail"'
if ($fixed -ne $text) {
    [IO.File]::WriteAllText($items, $fixed, (New-Object Text.UTF8Encoding($false)))
    Write-Host "  предмет eq_pony_tail: mesh eq_pony_tail"
}
py $items (Join-Path $Root "Module") $Game
Write-Host "Готово: пересоберите мод (.\run.ps1 -NoLaunch, в EquestriaBodyParts хвост и крылья подхватятся сами) и запускайте игру." -ForegroundColor Green
