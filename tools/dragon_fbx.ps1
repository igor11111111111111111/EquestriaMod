# FBX export of the dragon from the corrected model, before tools\dragon_material.ps1.
#
#   .\tools\dragon_fbx.ps1
#
# Calls tools\dragon_edit_export.py in assets\dragon\eq_dragon.blend: exports the skeleton
# (bip01_notused) and eight parts (body/wings/tail/legs/gloves/horn/hair/head) from the collection
# "Meshy Frostwing Princess" to assets\dragon\eq_dragon.fbx, with the same settings as the main
# pipeline tools\make_dragon.py (axes X/-Y, no animation). Then by hand: import this FBX into the
# Modding Kit (Resource Browser -> Import), then .\tools\dragon_material.ps1.
param([string]$Blender = "D:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe")

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Blend = Join-Path $Root "assets\dragon\eq_dragon.blend"
$Script = Join-Path $PSScriptRoot "dragon_edit_export.py"

if (-not (Test-Path $Blender)) { throw "Blender не найден: $Blender" }
if (-not (Test-Path $Blend)) { throw "Не найден файл модели: $Blend" }

Write-Host "== Экспорт FBX дракона" -ForegroundColor Cyan
& $Blender --background --factory-startup $Blend --python $Script
if ($LASTEXITCODE -ne 0) { throw "экспорт не удался" }

Write-Host "Готово: assets\dragon\eq_dragon.fbx. Импортируйте его в Modding Kit (Resource Browser -> Import), затем .\tools\dragon_material.ps1." -ForegroundColor Green
