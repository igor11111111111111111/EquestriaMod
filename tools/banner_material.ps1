# Material for our own banner icons - after the sheet has been imported in the editor.
#
#   .\tools\banner_material.ps1
#
# Order: tools\make_banner_icons.py puts the sheet assets\banner_icons\eq_banner_icons_d.png
# (2048x2048, 4x4 icons). It is imported in the editor (Resource Browser -> Import; package
# banner_icons). Then the material is made as a copy of vanilla custom_banner_icons_01: it has the right
# shader gui_color_and_stroke and the alpha_test flag, no need to pick them by hand.
#
# The material name must match material_name in Module\ModuleData\equestria_banner_icons.xml.
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
$ErrorActionPreference = "Continue"      # the tool prints its progress, and an empty line in the error stream crashed the script
& $Tool mat-clone "$Native;$Assets" custom_banner_icons_01 (Join-Path $Pack "eq_banner_icons_mtl.tpac") `
    eq_banner_icons 0=eq_banner_icons_d
if ($LASTEXITCODE -ne 0) { throw "материал не создан (код $LASTEXITCODE)" }

Write-Host "Готово: значки появятся в редакторе знамён группой «Эквестрия»." -ForegroundColor Green
