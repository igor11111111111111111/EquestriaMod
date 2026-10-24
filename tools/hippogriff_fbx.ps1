# Экспорт FBX гиппогрифа из поправленной модели — перед tools\hippogriff_material.ps1.
#
#   .\tools\hippogriff_fbx.ps1
#
# Зовёт tools\hippogriff_edit_export.py в assets\hippogriff\hippogriff.blend: экспортирует скелет
# (bip01_notused) и шесть частей (body/tail/wings/head/legs/gloves) из коллекции
# «Meshy Skyclaw Guardian» в assets\hippogriff\eq_hippogriff.fbx — теми же настройками, что и
# основной конвейер tools\make_hippogriff.py (оси X/-Y, без анимации). Дальше руками: импорт этого
# FBX в Modding Kit (Resource Browser -> Import), затем .\tools\hippogriff_material.ps1.
param([string]$Blender = "D:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Blend = Join-Path $Root "assets\hippogriff\hippogriff.blend"
$Script = Join-Path $PSScriptRoot "hippogriff_edit_export.py"

if (-not (Test-Path $Blender)) { throw "Blender не найден: $Blender" }
if (-not (Test-Path $Blend)) { throw "Не найден файл модели: $Blend" }

Write-Host "== Экспорт FBX гиппогрифа" -ForegroundColor Cyan
& $Blender --background --factory-startup $Blend --python $Script
if ($LASTEXITCODE -ne 0) { throw "экспорт не удался" }

Write-Host "Готово: assets\hippogriff\eq_hippogriff.fbx. Импортируйте его в Modding Kit (Resource Browser -> Import), затем .\tools\hippogriff_material.ps1." -ForegroundColor Green
