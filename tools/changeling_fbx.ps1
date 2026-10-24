# Экспорт FBX чейнджлинга из поправленной модели — перед tools\changeling_material.ps1.
#
#   .\tools\changeling_fbx.ps1
#
# Зовёт tools\changeling_edit_export.py в assets\changeling\eq_changeling.blend: экспортирует
# скелет (bip01_notused) и восемь частей (body/tail/wings/legs/gloves/head/ears/horn) из коллекции
# «Meshy Midnight Changeling» в assets\changeling\eq_changeling.fbx — теми же настройками, что и
# основной конвейер tools\make_changeling_model.py (оси X/-Y, без анимации). Дальше руками: импорт
# этого FBX в Modding Kit (Resource Browser -> Import), затем .\tools\changeling_material.ps1.
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
