# Экспорт FBX пони из ручной модели — перед tools\pony_material.ps1.
#
#   .\tools\pony_fbx.ps1
#
# Зовёт tools\pony_edit_export.py в assets\pony\eq_pony_edit.blend: экспортирует скелет и восемь
# частей (body/gloves/hair/head/horn/legs/tail/wings) из коллекции «Пони - цельная» в
# assets\pony\eq_pony.fbx — теми же настройками, что и основной конвейер (оси X/-Y, без анимации).
# Дальше руками: импорт этого FBX в Modding Kit (Resource Browser -> Import), затем
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
