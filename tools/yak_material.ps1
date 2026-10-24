# The yak material and the binding of its meshes, after the textures have been imported in the editor.
#
#   .\tools\yak_material.ps1
#
# Order: tools\make_yak_textures.py puts eq_yak_body_d/_n/_s.png into Module\AssetSources\twilight,
# they are imported in the editor (Resource Browser -> Import; package twilight). The rest is done in code:
#   1. the eq_yak_body material is a copy of eq_twilight_body (skin shader, skinning) with its own textures;
#   2. the five eq_yak_* meshes in eq_yak_geo.tpac get this material;
#   3. the yak race is taken off the pony placeholder: "yak" leaves NOT_IMPORTED, the skins are rebuilt.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"

Write-Host "== Текстуры в пакете" -ForegroundColor Cyan
# Cannot be checked by exporting: textures imported by the editor have no pixels in the package (only
# a reference to the PNG), so we look at the asset records themselves.
foreach ($name in "eq_yak_body_d", "eq_yak_body_n", "eq_yak_body_s") {
    $found = & $Tool info $Assets $name 2>&1 | Select-String -Pattern "^== $name`: Texture"
    if (-not $found) {
        throw "В пакете нет текстуры $name — импортируйте её в редакторе из assets\yak\textures"
    }
    Write-Host "  $name — есть"
}

Write-Host "== Материал eq_yak_body" -ForegroundColor Cyan
& $Tool mat-clone $Assets eq_twilight_body (Join-Path $Assets "twilight\eq_yak_body_mtl.tpac") eq_yak_body `
    0=eq_yak_body_d 1=eq_yak_body_d 2=eq_yak_body_n 3=eq_yak_body_n 4=eq_yak_body_s
if ($LASTEXITCODE -ne 0) { throw "материал не создан" }

Write-Host "== Материал гривы" -ForegroundColor Cyan
# The hair colour from the appearance window is only listened to by the vanilla hair shader, so the mane needs its own
# material: a copy of female_hair_mat (bumpmap + skinning, two textures) with our textures.
# The source lies in the vanilla packages and the textures in ours, so there are two folders separated by ";".
$Native = Join-Path $Game "Modules\Native\AssetPackages"
& $Tool mat-clone "$Native;$Assets" female_hair_mat (Join-Path $Assets "twilight\eq_yak_hair_mtl.tpac") `
    eq_yak_hair 0=eq_yak_body_d 1=eq_yak_body_n
if ($LASTEXITCODE -ne 0) { throw "материал гривы не создан" }

Write-Host "== Привязка мешей" -ForegroundColor Cyan
# Where the editor puts the mesh package depends on which package was selected at import:
# for the hippogriff it is Assets\twilight, for the yak it came out as the Assets root. So we search instead of setting the path.
$Found = @(Get-ChildItem $Assets -Recurse -Filter "eq_yak_geo.tpac")
if ($Found.Count -eq 0) {
    throw "не найден eq_yak_geo.tpac — импортируйте assets\yak\eq_yak.fbx в редакторе"
}
if ($Found.Count -gt 1) {
    # Two copies = the import landed in another package, and the old one remained. Silently taking the first is wrong:
    # the binding would go to outdated meshes, and the game would pick up some of its own.
    throw "пакетов eq_yak_geo.tpac несколько, удалите лишние:`n  " + ($Found.FullName -join "`n  ")
}
$Geo = $Found[0]
Write-Host "  пакет: $($Geo.FullName)"
& $Tool mesh-setmat $Assets $Geo.FullName eq_yak_ eq_yak_body
if ($LASTEXITCODE -ne 0) { throw "меши не привязаны" }
# the mane gets its own material, on top of the common binding
& $Tool mesh-setmat $Assets $Geo.FullName eq_yak_hair eq_yak_hair
if ($LASTEXITCODE -ne 0) { throw "грива не привязана" }

Write-Host "== Раса без заглушки" -ForegroundColor Cyan
$race = Join-Path $Root "tools\make_pony_race.py"
$text = [IO.File]::ReadAllText($race)
$fixed = $text -replace 'NOT_IMPORTED = \{"yak"\}', 'NOT_IMPORTED = set()'
if ($fixed -ne $text) {
    [IO.File]::WriteAllText($race, $fixed, (New-Object Text.UTF8Encoding($false)))
    Write-Host "  yak убран из NOT_IMPORTED"
}
py $race (Join-Path $Game "Modules") (Join-Path $Root "Module")
Write-Host "Готово: запускайте игру, як на своей модели." -ForegroundColor Green
