# Выгружает вершинные ключи (морфы) ванильной головы Bannerlord в простой бинарный файл.
# Ими движок делает моргание, движение глаз и мимику; у импортированной головы их нет.
#
#   .\tools\dump_face_morphs.ps1 [-Mesh head_female_a] [-Out assets\reference\face_morphs\head_female_a.bin]
#
# Формат: int32 verts, int32 frames, float32[verts*3] базовые позиции,
#         затем на каждый кадр: int32 time, float32[verts*3] позиции.
param(
    [string]$Mesh = "head_female_a",
    [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
if (-not $Out) { $Out = "$root\assets\reference\face_morphs\$Mesh.bin" }
$assets = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord\Modules\Native\AssetPackages"

Get-ChildItem "$root\tools\external\TpacTool\bin" -Filter *.dll | ForEach-Object {
    try { [Reflection.Assembly]::LoadFrom($_.FullName) | Out-Null } catch { }
}
$manager = New-Object TpacTool.Lib.AssetManager
$manager.Load($assets)
[TpacTool.Lib.DefaultDependenceResolver]::Instance = $manager

$meta = $manager.LoadedAssets | Where-Object { $_ -is [TpacTool.Lib.Metamesh] -and $_.Name -eq $Mesh } | Select-Object -First 1
if (-not $meta) { throw "metamesh $Mesh не найден" }
$lod0 = $meta.Meshes | Where-Object { $_.VertexKeyCount -gt 0 } | Select-Object -First 1
if (-not $lod0) { throw "у $Mesh нет вершинных ключей" }
$data = $lod0.EditData.Data
$frames = $data.MorphFrames
Write-Host "$($lod0.Name): позиций $($data.Positions.Length), кадров $($frames.Count)" -ForegroundColor Green

New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null
$fs = [IO.File]::Create($Out)
$bw = New-Object IO.BinaryWriter($fs)
try {
    $bw.Write([int]$data.Positions.Length)
    $bw.Write([int]$frames.Count)
    foreach ($p in $data.Positions) { $bw.Write([single]$p.X); $bw.Write([single]$p.Y); $bw.Write([single]$p.Z) }
    foreach ($f in $frames) {
        $bw.Write([int]$f.Time)
        foreach ($p in $f.Positions) { $bw.Write([single]$p.X); $bw.Write([single]$p.Y); $bw.Write([single]$p.Z) }
    }
} finally {
    $bw.Close(); $fs.Close()
}
Write-Host "записано $Out ($([Math]::Round((Get-Item $Out).Length/1MB,2)) МБ)" -ForegroundColor Green
