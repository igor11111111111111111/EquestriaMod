# Экспорт FBX грифона из поправленной модели — перед tools\griffon_material.ps1.
#
#   .\tools\griffon_fbx.ps1
#
# Зовёт tools\griffon_edit_export.py в assets\griffon\eq_griffon.blend: экспортирует скелет
# (bip01_notused) и семь частей (body/legs/tail/wings/gloves/head/ear) из коллекции
# «Meshy Skybound Griffin» в assets\griffon\eq_griffon.fbx — теми же настройками, что и основной
# конвейер tools\make_griffon.py (оси X/-Y, без анимации). Дальше руками: импорт этого FBX в
# Modding Kit (Resource Browser -> Import), затем .\tools\griffon_material.ps1.
param([string]$Blender = "D:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Blend = Join-Path $Root "assets\griffon\eq_griffon.blend"
$Script = Join-Path $PSScriptRoot "griffon_edit_export.py"

if (-not (Test-Path $Blender)) { throw "Blender не найден: $Blender" }
if (-not (Test-Path $Blend)) { throw "Не найден файл модели: $Blend" }

Write-Host "== Экспорт FBX грифона" -ForegroundColor Cyan
& $Blender --background --factory-startup $Blend --python $Script
if ($LASTEXITCODE -ne 0) { throw "экспорт не удался" }

Write-Host "Готово: assets\griffon\eq_griffon.fbx. Импортируйте его в Modding Kit (Resource Browser -> Import), затем .\tools\griffon_material.ps1." -ForegroundColor Green
