# Exports the changeling FBX from the fixed-up model; run before tools\changeling_material.ps1.
#
#   .\tools\changeling_fbx.ps1
#
# Calls tools\changeling_edit_export.py in assets\changeling\eq_changeling.blend: exports the
# skeleton (bip01_notused) and eight parts (body/tail/wings/legs/gloves/head/ears/horn) from the collection
# «Meshy Midnight Changeling» to assets\changeling\eq_changeling.fbx, with the same settings as the
# main pipeline tools\make_changeling_model.py (axes X/-Y, no animation). Then by hand: import
# this FBX into the Modding Kit (Resource Browser -> Import), then .\tools\changeling_material.ps1.
param([string]$Blender = "D:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Blend = Join-Path $Root "assets\changeling\eq_changeling.blend"
$Script = Join-Path $PSScriptRoot "changeling_edit_export.py"

if (-not (Test-Path $Blender)) { throw "Blender не найден: $Blender" }
if (-not (Test-Path $Blend)) { throw "Не найден файл модели: $Blend" }

Write-Host "== Экспорт FBX чейнджлинга" -ForegroundColor Cyan
& $Blender --background --factory-startup $Blend --python $Script
if ($LASTEXITCODE -ne 0) { throw "экспорт не удался" }

Write-Host "Готово: assets\changeling\eq_changeling.fbx. Импортируйте его в Modding Kit (Resource Browser -> Import), затем .\tools\changeling_material.ps1." -ForegroundColor Green
