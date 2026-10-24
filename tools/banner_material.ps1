# Материал для своих значков знамён — после того, как лист импортирован в редакторе.
#
#   .\tools\banner_material.ps1
#
# Порядок: tools\make_banner_icons.py кладёт лист assets\banner_icons\eq_banner_icons_d.png
# (2048x2048, 4x4 значка). Его импортируют в редакторе (Resource Browser -> Import; пакет
# banner_icons). Дальше материал делается копией ванильного custom_banner_icons_01: у него нужный
# шейдер gui_color_and_stroke и флаг alpha_test, подбирать их руками не нужно.
#
# Имя материала обязано совпадать с material_name в Module\ModuleData\equestria_banner_icons.xml.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"
$Native = Join-Path $Game "Modules\Native\AssetPackages"
$Pack = Join-Path $Assets "banner_icons"

Write-Host "== Лист значков в пакете" -ForegroundColor Cyan
$found = & $Tool assets $Assets "texture:eq_banner_icons_d" 2>&1 | Select-String -Pattern "^Texture"
if (-not $found) {
    throw "в пакете нет текстуры eq_banner_icons_d — импортируйте assets\banner_icons\eq_banner_icons_d.png"
}
Write-Host "  eq_banner_icons_d — есть"

Write-Host "== Материал eq_banner_icons" -ForegroundColor Cyan
New-Item -ItemType Directory -Force $Pack | Out-Null
$ErrorActionPreference = "Continue"      # инструмент пишет ход работы, и пустая строка в потоке ошибок роняла скрипт
& $Tool mat-clone "$Native;$Assets" custom_banner_icons_01 (Join-Path $Pack "eq_banner_icons_mtl.tpac") `
    eq_banner_icons 0=eq_banner_icons_d
if ($LASTEXITCODE -ne 0) { throw "материал не создан (код $LASTEXITCODE)" }

Write-Host "Готово: значки появятся в редакторе знамён группой «Эквестрия»." -ForegroundColor Green
