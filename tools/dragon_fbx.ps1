# Экспорт FBX дракона из поправленной модели — перед tools\dragon_material.ps1.
#
#   .\tools\dragon_fbx.ps1
#
# Зовёт tools\dragon_edit_export.py в assets\dragon\eq_dragon.blend: экспортирует скелет
# (bip01_notused) и восемь частей (body/wings/tail/legs/gloves/horn/hair/head) из коллекции
# «Meshy Frostwing Princess» в assets\dragon\eq_dragon.fbx — теми же настройками, что и основной
# конвейер tools\make_dragon.py (оси X/-Y, без анимации). Дальше руками: импорт этого FBX в
# Modding Kit (Resource Browser -> Import), затем .\tools\dragon_material.ps1.
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
