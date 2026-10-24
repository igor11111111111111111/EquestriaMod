# Exports the doe FBX from the fixed-up model; run before tools\deer_material.ps1.
#
#   .\tools\deer_fbx.ps1
#
# Calls tools\deer_edit_export.py in assets\deer\eq_deer.blend: exports the skeleton (bip01_notused)
# and parts (body/legs/tail/gloves/ears/hair/head, 4 antler variants, 4 braid copies) from
# «Meshy Braided Fawn» to assets\deer\eq_deer.fbx, with the same settings as the main pipeline
# tools\make_deer_model.py (axes X/-Y, no animation). Then by hand: import this FBX into the Modding Kit
# (Resource Browser -> Import), then .\tools\deer_material.ps1.
param([string]$Blender = "D:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Blend = Join-Path $Root "assets\deer\eq_deer.blend"
$Script = Join-Path $PSScriptRoot "deer_edit_export.py"

if (-not (Test-Path $Blender)) { throw "Blender не найден: $Blender" }
if (-not (Test-Path $Blend)) { throw "Не найден файл модели: $Blend" }

Write-Host "== Экспорт FBX оленихи" -ForegroundColor Cyan
& $Blender --background --factory-startup $Blend --python $Script
if ($LASTEXITCODE -ne 0) { throw "экспорт не удался" }

Write-Host "Готово: assets\deer\eq_deer.fbx. Импортируйте его в Modding Kit (Resource Browser -> Import), затем .\tools\deer_material.ps1." -ForegroundColor Green
