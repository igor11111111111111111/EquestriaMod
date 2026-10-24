# Материал яка и привязка его мешей — после того, как текстуры импортированы в редакторе.
#
#   .\tools\yak_material.ps1
#
# Порядок: tools\make_yak_textures.py кладёт eq_yak_body_d/_n/_s.png в Module\AssetSources\twilight,
# их импортируют в редакторе (Resource Browser -> Import; пакет twilight). Дальше всё кодом:
#   1. материал eq_yak_body — копия eq_twilight_body (шейдер кожи, скиннинг) со своими текстурами;
#   2. пять мешей eq_yak_* в eq_yak_geo.tpac получают этот материал;
#   3. раса yak снимается с заглушки пони: "yak" уходит из NOT_IMPORTED, skins пересобираются.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"

Write-Host "== Текстуры в пакете" -ForegroundColor Cyan
# Выгрузкой не проверить: у импортированных редактором текстур в пакете нет пикселей (только
# ссылка на PNG), поэтому смотрим сами записи ассетов.
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
# Цвет волос из окна внешности слушает только ванильный шейдер волос, поэтому гриве нужен свой
# материал — копия female_hair_mat (bumpmap + skinning, две текстуры) с нашими текстурами.
# Исходник лежит в ванильных пакетах, а текстуры в нашем, поэтому папок две через «;».
$Native = Join-Path $Game "Modules\Native\AssetPackages"
& $Tool mat-clone "$Native;$Assets" female_hair_mat (Join-Path $Assets "twilight\eq_yak_hair_mtl.tpac") `
    eq_yak_hair 0=eq_yak_body_d 1=eq_yak_body_n
if ($LASTEXITCODE -ne 0) { throw "материал гривы не создан" }

Write-Host "== Привязка мешей" -ForegroundColor Cyan
# Куда редактор положит пакет с мешами — зависит от того, какой пакет был выбран при импорте:
# у гиппогрифа это Assets\twilight, у яка вышел корень Assets. Поэтому ищем, а не задаём путь.
$Found = @(Get-ChildItem $Assets -Recurse -Filter "eq_yak_geo.tpac")
if ($Found.Count -eq 0) {
    throw "не найден eq_yak_geo.tpac — импортируйте assets\yak\eq_yak.fbx в редакторе"
}
if ($Found.Count -gt 1) {
    # Две копии = импорт лёг в другой пакет, а старая осталась. Молча взять первую нельзя:
    # привязка уйдёт в устаревшие меши, а игра подхватит какие-то свои.
    throw "пакетов eq_yak_geo.tpac несколько, удалите лишние:`n  " + ($Found.FullName -join "`n  ")
}
$Geo = $Found[0]
Write-Host "  пакет: $($Geo.FullName)"
& $Tool mesh-setmat $Assets $Geo.FullName eq_yak_ eq_yak_body
if ($LASTEXITCODE -ne 0) { throw "меши не привязаны" }
# гриве — свой материал, поверх общей привязки
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
