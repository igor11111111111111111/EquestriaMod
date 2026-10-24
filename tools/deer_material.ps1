# Материал оленихи и привязка её мешей — после того, как текстуры импортированы в редакторе.
#
#   .\tools\deer_material.ps1
#
# Порядок: tools\make_deer_textures.py кладёт eq_deer_body_d/_n/_s.png в assets\deer\textures,
# их импортируют в редакторе (Resource Browser -> Import; пакет twilight). Дальше всё кодом:
#   1. материал eq_deer_body — копия eq_twilight_body (шейдер кожи, скиннинг) со своими текстурами;
#   2. меши eq_deer_* в пакете с геометрией получают этот материал;
#   3. раса deer снимается с заглушки пони: "deer" уходит из NOT_IMPORTED, skins пересобираются.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"

Write-Host "== Текстуры в пакете" -ForegroundColor Cyan
# Выгрузкой не проверить: у импортированных редактором текстур в пакете нет пикселей (только
# ссылка на PNG), поэтому смотрим сами записи ассетов.
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
# Цвет волос из окна внешности слушает только ванильный шейдер волос, поэтому рогам нужен свой
# материал — копия female_hair_mat (bumpmap + skinning, две текстуры) с нашими текстурами.
# Исходник лежит в ванильных пакетах, а текстуры в нашем, поэтому папок две через «;».
$Native = Join-Path $Game "Modules\Native\AssetPackages"
& $Tool mat-clone "$Native;$Assets" female_hair_mat (Join-Path $Assets "twilight\eq_deer_hair_mtl.tpac") `
    eq_deer_hair 0=eq_deer_body_d 1=eq_deer_body_n
if ($LASTEXITCODE -ne 0) { throw "материал рогов не создан" }

Write-Host "== Привязка мешей" -ForegroundColor Cyan
# Куда редактор положит пакет с мешами — зависит от того, какой пакет был выбран при импорте,
# поэтому ищем, а не задаём путь.
$Found = @(Get-ChildItem $Assets -Recurse -Filter "eq_deer_geo.tpac")
if ($Found.Count -eq 0) {
    throw "не найден eq_deer_geo.tpac — импортируйте assets\deer\eq_deer.fbx в редакторе"
}
if ($Found.Count -gt 1) {
    # Две копии = импорт лёг в другой пакет, а старая осталась. Молча взять первую нельзя:
    # привязка уйдёт в устаревшие меши, а игра подхватит какие-то свои.
    throw "пакетов eq_deer_geo.tpac несколько, удалите лишние:`n  " + ($Found.FullName -join "`n  ")
}
$Geo = $Found[0]
Write-Host "  пакет: $($Geo.FullName)"
& $Tool mesh-setmat $Assets $Geo.FullName eq_deer_ eq_deer_body
if ($LASTEXITCODE -ne 0) { throw "меши не привязаны" }
# рогам — свой материал, поверх общей привязки
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
