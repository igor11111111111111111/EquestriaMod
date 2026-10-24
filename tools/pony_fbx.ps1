# Export the pony FBX from the hand-made model, before tools\pony_material.ps1.
#
#   .\tools\pony_fbx.ps1
#
# Calls tools\pony_edit_export.py in assets\pony\eq_pony_edit.blend: exports the skeleton and eight
# parts (body/gloves/hair/head/horn/legs/tail/wings) from the "Pony - whole" collection to
# assets\pony\eq_pony.fbx with the same settings as the main pipeline (axes X/-Y, no animation).
# Then by hand: import this FBX into the Modding Kit (Resource Browser -> Import), then
# .\tools\pony_material.ps1.
param([string]$Blender = "D:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Blend = Join-Path $Root "assets\pony\eq_pony_edit.blend"
$Script = Join-Path $PSScriptRoot "pony_edit_export.py"

if (-not (Test-Path $Blender)) { throw "Blender не найден: $Blender" }
if (-not (Test-Path $Blend)) { throw "Не найден файл модели: $Blend" }

Write-Host "== Экспорт FBX пони" -ForegroundColor Cyan
& $Blender --background --factory-startup $Blend --python $Script
if ($LASTEXITCODE -ne 0) { throw "экспорт не удался" }

Write-Host "Готово: assets\pony\eq_pony.fbx. Импортируйте его в Modding Kit (Resource Browser -> Import), затем .\tools\pony_material.ps1." -ForegroundColor Green
