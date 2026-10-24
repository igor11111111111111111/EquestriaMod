# Hippogriff FBX export from the fixed model — before tools\hippogriff_material.ps1.
#
#   .\tools\hippogriff_fbx.ps1
#
# Calls tools\hippogriff_edit_export.py in assets\hippogriff\hippogriff.blend: exports the skeleton
# (bip01_notused) and six parts (body/tail/wings/head/legs/gloves) from the collection
# "Meshy Skyclaw Guardian" into assets\hippogriff\eq_hippogriff.fbx — with the same settings as the
# main pipeline tools\make_hippogriff.py (axes X/-Y, no animation). Then by hand: import this
# FBX into the Modding Kit (Resource Browser -> Import), then .\tools\hippogriff_material.ps1.
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
