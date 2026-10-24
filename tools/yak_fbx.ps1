# FBX export of the yak from the fixed model - before tools\yak_material.ps1.
#
#   .\tools\yak_fbx.ps1
#
# Calls tools\yak_edit_export.py in assets\yak\eq_yak.blend: exports the skeleton (bip01_notused) and
# seven parts (body/tail/gloves/legs/horn/hair/head) from the collection «Meshy Highland Hugger» to
# assets\yak\eq_yak.fbx - with the same settings as the main pipeline tools\make_yak_model.py
# (axes X/-Y, no animation). Then by hand: import this FBX into the Modding Kit (Resource Browser ->
# Import), then .\tools\yak_material.ps1.
param([string]$Blender = "D:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Blend = Join-Path $Root "assets\yak\eq_yak.blend"
$Script = Join-Path $PSScriptRoot "yak_edit_export.py"

if (-not (Test-Path $Blender)) { throw "Blender не найден: $Blender" }
if (-not (Test-Path $Blend)) { throw "Не найден файл модели: $Blend" }

Write-Host "== Экспорт FBX яка" -ForegroundColor Cyan
& $Blender --background --factory-startup $Blend --python $Script
if ($LASTEXITCODE -ne 0) { throw "экспорт не удался" }

Write-Host "Готово: assets\yak\eq_yak.fbx. Импортируйте его в Modding Kit (Resource Browser -> Import), затем .\tools\yak_material.ps1." -ForegroundColor Green
