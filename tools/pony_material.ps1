# Материал пони и привязка её мешей — после того, как текстуры импортированы в редакторе.
#
#   .\tools\pony_material.ps1
#
# Порядок: tools\make_pony_textures.py кладёт eq_pony_body_d/_n/_s.png в assets\pony\textures,
# их импортируют в редакторе (Resource Browser -> Import; пакет twilight). Дальше всё кодом:
#   1. материал eq_pony_body — копия eq_twilight_body (шейдер кожи, скиннинг) со своими текстурами;
#   2. меши eq_pony_* в пакете с геометрией получают этот материал;
#   3. новая раса pony снимается с заглушки пони: "pony" уходит из NOT_IMPORTED, skins пересобираются.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"

Write-Host "== Текстуры в пакете" -ForegroundColor Cyan
# Выгрузкой не проверить: у импортированных редактором текстур в пакете нет пикселей (только
# ссылка на PNG), поэтому смотрим сами записи ассетов.
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
# Цвет волос из окна внешности слушает только ванильный шейдер волос, поэтому гриве нужен свой
# материал — копия female_hair_mat (bumpmap + skinning, две текстуры) с нашими текстурами.
# Исходник лежит в ванильных пакетах, а текстуры в нашем, поэтому папок две через «;».
$Native = Join-Path $Game "Modules\Native\AssetPackages"
& $Tool mat-clone "$Native;$Assets" female_hair_mat (Join-Path $Assets "twilight\eq_pony_hair_mtl.tpac") `
    eq_pony_hair 0=eq_pony_body_d 1=eq_pony_body_n
if ($LASTEXITCODE -ne 0) { throw "материал гривы не создан" }

Write-Host "== Привязка мешей" -ForegroundColor Cyan
# Куда редактор положит пакет с мешами — зависит от того, какой пакет был выбран при импорте,
# поэтому ищем, а не задаём путь.
$Found = @(Get-ChildItem $Assets -Recurse -Filter "eq_pony_geo.tpac")
if ($Found.Count -eq 0) {
    throw "не найден eq_pony_geo.tpac — импортируйте assets\pony\eq_pony.fbx в редакторе"
}
if ($Found.Count -gt 1) {
    # Две копии = импорт лёг в другой пакет, а старая осталась. Молча взять первую нельзя:
    # привязка уйдёт в устаревшие меши, а игра подхватит какие-то свои.
    throw "пакетов eq_pony_geo.tpac несколько, удалите лишние:`n  " + ($Found.FullName -join "`n  ")
}
$Geo = $Found[0]
Write-Host "  пакет: $($Geo.FullName)"
& $Tool mesh-setmat $Assets $Geo.FullName eq_pony_ eq_pony_body
if ($LASTEXITCODE -ne 0) { throw "меши не привязаны" }
# гриве, рогу, хвосту и крыльям — волосяной материал: они красятся цветом причёски из окна
# внешности (src/EquestriaBodyParts.cs, HairTinted), а этот цвет читает только шейдер волос
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
# Предмет eq_pony_tail нужен окнам без персонажа-агента (смотр рас). Пока пони не была
# импортирована, он смотрел на хвост Twilight; теперь — на хвост новой модели.
$items = Join-Path $Root "tools\make_items.py"
$text = [IO.File]::ReadAllText($items)
$fixed = $text -replace 'mesh="eq_twilight_tail"', 'mesh="eq_pony_tail"'
if ($fixed -ne $text) {
    [IO.File]::WriteAllText($items, $fixed, (New-Object Text.UTF8Encoding($false)))
    Write-Host "  предмет eq_pony_tail: mesh eq_pony_tail"
}
py $items (Join-Path $Root "Module") $Game
Write-Host "Готово: пересоберите мод (.\run.ps1 -NoLaunch, в EquestriaBodyParts хвост и крылья подхватятся сами) и запускайте игру." -ForegroundColor Green
