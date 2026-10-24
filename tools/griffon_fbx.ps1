# Export of the griffon FBX from the fixed model, before tools\griffon_material.ps1.
#
#   .\tools\griffon_fbx.ps1
#
# Calls tools\griffon_edit_export.py in assets\griffon\eq_griffon.blend: exports the skeleton
# (bip01_notused) and seven parts (body/legs/tail/wings/gloves/head/ear) from the collection
# "Meshy Skybound Griffin" to assets\griffon\eq_griffon.fbx, with the same settings as the main
# pipeline tools\make_griffon.py (axes X/-Y, no animation). Then by hand: import this FBX into the
# Modding Kit (Resource Browser -> Import), then .\tools\griffon_material.ps1.
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
