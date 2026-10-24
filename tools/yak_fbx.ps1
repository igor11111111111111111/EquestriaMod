# Экспорт FBX яка из поправленной модели — перед tools\yak_material.ps1.
#
#   .\tools\yak_fbx.ps1
#
# Зовёт tools\yak_edit_export.py в assets\yak\eq_yak.blend: экспортирует скелет (bip01_notused) и
# семь частей (body/tail/gloves/legs/horn/hair/head) из коллекции «Meshy Highland Hugger» в
# assets\yak\eq_yak.fbx — теми же настройками, что и основной конвейер tools\make_yak_model.py
# (оси X/-Y, без анимации). Дальше руками: импорт этого FBX в Modding Kit (Resource Browser ->
# Import), затем .\tools\yak_material.ps1.
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
