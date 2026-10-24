# Снимки карты мира в нескольких точках за один запуск игры.
#
#   .\tools\tour.ps1 -Points "614,600;544,600" -Out C:\temp\tour
#
# Мод (ключ /eqgoto со списком точек, src/EquestriaLongRun.cs) переносит отряд игрока по точкам
# каждые 14 с и пишет в журнал «обход: точка N»; скрипт после каждой отметки снимает экран
# в <Out>\point_N.png. В конце игра закрывается.
param(
    [Parameter(Mandatory)] [string]$Points,
    [Parameter(Mandatory)] [string]$Out,
    [int]$Settle = 9
)

$ErrorActionPreference = "Stop"
$ModRoot = Split-Path $PSScriptRoot -Parent
$Log = Join-Path $ModRoot "Module\eq_exceptions.log"
New-Item -ItemType Directory -Force $Out | Out-Null
$count = ($Points -split ";").Count

& (Join-Path $PSScriptRoot "selftest.ps1") -GameArgs "/eqlongrun:1 /eqgoto:$Points" `
    -ReadyMark "обход: точка 1 " -Timeout 900 -SettleSeconds $Settle -KeepOpen `
    -Shot (Join-Path $Out "point_1.png") | Select-Object -Last 1

for ($n = 2; $n -le $count; $n++) {
    $deadline = (Get-Date).AddSeconds(60)
    while (-not (Select-String -Path $Log -Pattern "обход: точка $n " -Quiet)) {
        if ((Get-Date) -gt $deadline) { Write-Output "точка $n не дождались"; break }
        Start-Sleep -Milliseconds 500
    }
    Start-Sleep -Seconds $Settle
    & (Join-Path $PSScriptRoot "screenshot.ps1") | Out-Null
    Copy-Item "$env:TEMP\bannerlord_shot.png" (Join-Path $Out "point_$n.png") -Force
    Write-Output "снимок точки $n"
}
Get-Process Bannerlord -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Output "обход закончен"
