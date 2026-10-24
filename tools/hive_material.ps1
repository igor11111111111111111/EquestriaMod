# Hive armour: materials and copies of vanilla meshes — after importing the textures in the editor.
#
#   .\tools\hive_material.ps1
#
# Order: tools\hive_armor.py puts eq_ch_<name>_d.png into assets\hive_armor\textures (the pattern is
# baked into the color), they are imported in the editor (Resource Browser -> Import; package armor_changeling).
# Then everything by code:
#   1. materials eq_ch_<vanilla> — copies of the vanilla Aserai ones with our texture in slot 0;
#      the flags are vanilla, so all shader variants are already compiled by the game;
#   2. copies of the vanilla armour meshes named eq_ch_<mesh>, bound to these materials —
#      the vanilla assets are not touched;
#   3. items eq_changeling_* and re-dressing the hive tree (tools\make_items.py, make_troops.py).
#
#   .\tools\hive_material.ps1 -Glow      real glow via self_illumination
# WARNING: -Glow is expensive. No vanilla material has this combination of flags (glow + skinning),
# and the engine compiles it itself on EVERY launch: 1332 compilations, minutes on the loading
# screen. That is exactly what we ran into on 25.09.2026, when the script was run without switches
# and the glow was on by default. Now there is no glow by default.
param([string]$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord",
      [switch]$Glow)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Tool = Join-Path $Root "tools\tpac_export\bin\Release\tpac_export.exe"
$Assets = Join-Path $Root "Module\Assets"
$Native = Join-Path $Game "Modules\Native\AssetPackages"
$Pack = Join-Path $Assets "armor_changeling"
# Without the switch the flags are not touched at all: slot 1 keeps the vanilla mask, the armour is
# tinted with clan colors, and our glow is baked into the texture itself. With -Glow we enable
# self_illumination and remove the two-color mask (both settings read the same slot and do not work together).
$Flags = if ($Glow) { "flags=+self_illumination,-use_double_colormap_with_mask_texture" } else { "" }

# The mesh list comes from the shared armour catalog (tools\armor_catalog.py): it also decides which
# items belong to the Aserai tree, and the textures are built from it too (tools\hive_armor.py).
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
    # parse only lines "<mesh>: <materials>"; the tool also prints its own ("packages: 150,
    # assets: 40808"), because of them numbers got into the material list
    if ($line -match "^(\S+): (.+)$" -and $meshes -contains $Matches[1]) {
        foreach ($m in $Matches[2].Split(",")) {
            $m = $m.Trim()
            # for one submesh the material does not resolve and is printed as a bare guid — skip it,
            # such a submesh keeps the vanilla material
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
# An empty line that the tool wrote to the error stream crashed the script for nothing under "Stop"
# (25.09.2026). Success is checked by the exit code, as before.
$ErrorActionPreference = "Continue"
# The vanilla mittens mail_mitten_e/f/h have an empty material in all submeshes — a defect of the game.
# The engine does not draw a mesh with an empty material, so we cover them with our chitin eq_ch_mail_mitten
# (previously the vanilla mail_mitten was substituted — the mittens stayed chainmail-grey).
& $Tool mesh-copy "$Native;$Assets" (Join-Path $Pack "eq_ch_armor_geo.tpac") "eq_ch_" ($meshes -join ",") "fallback=eq_ch_mail_mitten"
if ($LASTEXITCODE -ne 0) { throw "меши не скопированы" }

Write-Host "Готово: пересоберите предметы и войска (py tools\make_items.py, py tools\make_troops.py)." -ForegroundColor Green
