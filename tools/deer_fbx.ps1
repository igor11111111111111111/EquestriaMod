# Экспорт FBX оленихи из поправленной модели — перед tools\deer_material.ps1.
#
#   .\tools\deer_fbx.ps1
#
# Зовёт tools\deer_edit_export.py в assets\deer\eq_deer.blend: экспортирует скелет (bip01_notused)
# и части (body/legs/tail/gloves/ears/hair/head, 4 варианта рогов, 4 копии кос) из «Meshy Braided Fawn» в
# assets\deer\eq_deer.fbx — теми же настройками, что и основной конвейер tools\make_deer_model.py
# (оси X/-Y, без анимации). Дальше руками: импорт этого FBX в Modding Kit (Resource Browser ->
# Import), затем .\tools\deer_material.ps1.
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
