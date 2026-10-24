# Броня улья: материалы и копии ванильных мешей — после импорта текстур в редакторе.
#
#   .\tools\hive_material.ps1
#
# Порядок: tools\hive_armor.py кладёт eq_ch_<имя>_d.png в assets\hive_armor\textures (узор впечён
# в цвет), их импортируют в редакторе (Resource Browser -> Import; пакет armor_changeling).
# Дальше всё кодом:
#   1. материалы eq_ch_<ванильный> — копии ванильных асерайских с нашей текстурой в слоте 0;
#      флаги ванильные, поэтому все варианты шейдера у игры уже собраны;
#   2. копии ванильных мешей брони под именами eq_ch_<меш>, привязанные к этим материалам —
#      ванильные ассеты при этом не трогаются;
#   3. предметы eq_changeling_* и переодевание ульевого дерева (tools\make_items.py, make_troops.py).
#
#   .\tools\hive_material.ps1 -Glow      настоящее свечение через self_illumination
# ВНИМАНИЕ: -Glow стоит дорого. Такого сочетания флагов (свечение + скиннинг) в ванили нет ни у
# одного материала, и движок собирает его сам при КАЖДОМ запуске: 1332 сборки, минуты на
# загрузочном экране. Ровно на это напоролись 25.09.2026, когда скрипт запустили без ключей, а
# свечение было включено по умолчанию. Теперь по умолчанию свечения нет.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord",
      [switch]$Glow)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"
$Native = Join-Path $Game "Modules\Native\AssetPackages"
$Pack = Join-Path $Assets "armor_changeling"
# Без ключа флаги не трогаем вовсе: в слоте 1 остаётся ванильная маска, броня красится цветами
# клана, а свечение у нас впечено в саму текстуру. С -Glow включаем self_illumination и снимаем
# двухцветную маску (обе настройки читают один слот и вместе не работают).
$Flags = if ($Glow) { "flags=+self_illumination,-use_double_colormap_with_mask_texture" } else { "" }

# Список мешей берём из общего каталога брони (tools\armor_catalog.py): он же решает, какие вещи
# входят в асерайское дерево, по нему собираются и текстуры (tools\hive_armor.py).
$script = @"
import sys, json
sys.path.insert(0, r'$(Join-Path $Root "tools")')
import armor_catalog as ac
print(json.dumps(sorted({r['mesh'] for r in ac.pieces('changeling')})))
"@
$meshes = (py -c $script | ConvertFrom-Json)
Write-Host "== Броня улья: мешей $($meshes.Count)" -ForegroundColor Cyan

Write-Host "== Материалы мешей" -ForegroundColor Cyan
$matLines = & $Tool mesh-mats $Native ($meshes -join ",") 2>&1
$materials = @()
foreach ($line in $matLines) {
    # разбираем только строки «<меш>: <материалы>»; у инструмента есть и свои («packages: 150,
    # assets: 40808»), из-за них в список материалов попадали числа
    if ($line -match "^(\S+): (.+)$" -and $meshes -contains $Matches[1]) {
        foreach ($m in $Matches[2].Split(",")) {
            $m = $m.Trim()
            # у одного подмеша материал не разрешается и печатается голым guid — его пропускаем,
            # такому подмешу останется ванильный материал
            if ($m -match "^[0-9a-f]{8}-") { continue }
            if ($m -and $materials -notcontains $m) { $materials += $m }
        }
    }
}
if (-not $materials) { throw "не удалось получить материалы мешей" }
Write-Host "  разных материалов: $($materials.Count)"

Write-Host "== Клонирование материалов$(if ($Glow) { ' (со свечением, долгая загрузка игры!)' })" -ForegroundColor Cyan
if ($Glow) {
    & $Tool mat-batch "$Native;$Assets" $Pack "eq_ch_" ($materials -join ",") $Flags
} else {
    & $Tool mat-batch "$Native;$Assets" $Pack "eq_ch_" ($materials -join ",")
}
if ($LASTEXITCODE -ne 0) { throw "материалы не созданы (код $LASTEXITCODE)" }

Write-Host "== Копии мешей" -ForegroundColor Cyan
# Пустая строка, попавшая инструменту в поток ошибок, при "Stop" валила скрипт на ровном месте
# (25.09.2026). Успех проверяем по коду возврата, как и раньше.
$ErrorActionPreference = "Continue"
# У ванильных рукавиц mail_mitten_e/f/h материал пустой во всех подмешах — дефект самой игры.
# Меш с пустым материалом движок не рисует, поэтому закрываем их своим хитиновым eq_ch_mail_mitten
# (раньше подставлялся ванильный mail_mitten — рукавицы оставались кольчужно-серыми).
& $Tool mesh-copy "$Native;$Assets" (Join-Path $Pack "eq_ch_armor_geo.tpac") "eq_ch_" ($meshes -join ",") "fallback=eq_ch_mail_mitten"
if ($LASTEXITCODE -ne 0) { throw "меши не скопированы" }

Write-Host "Готово: пересоберите предметы и войска (py tools\make_items.py, py tools\make_troops.py)." -ForegroundColor Green
