# Самопроверка без участия человека: собрать, запустить быстрый тест, дождаться карты, снять экран.
#
#   .\tools\selftest.ps1                     полный цикл
#   .\tools\selftest.ps1 -Timeout 300        ждать карту дольше (после сброса кэша шейдеров)
#
# Что делает по пути:
#   окно "Mod change detected"    -> OK (уведомление о сбросе кэша шейдеров)
#   окно "Safe Mode"              -> Нет
#   окно краша "*_*"              -> Нет, затем печатает журналы ошибок, итог: КРАШ
#   игра закрылась сама            -> печатает журналы, итог: КРАШ
#   в eq_exceptions.log появилась отметка запуска сессии -> карта готова, снимок экрана, итог: ОК
#
# Снимок требует оконного режима без рамки (display_mode = 2 в engine_config.txt): из
# исключительного полноэкранного режима кадр получается чёрным.
param(
    [int]$Timeout = 240,
    [string]$Shot = "$env:TEMP\equestria_selftest.png",
    # оставить игру открытой после снимка; по умолчанию закрываем — она держит файлы мода
    [switch]$KeepOpen,
    # дополнительные ключи игры, например "/eqset:2" — показ комплекта брони
    [string]$GameArgs = "",
    # строка журнала мода, после которой можно снимать экран
    [string]$ReadyMark = "опись данных мода: запуск сессии",
    # сколько ждать после отметки, прежде чем снимать
    [int]$SettleSeconds = 8,
    # не начинать новую кампанию (например, для /eqload:имя — загрузки сохранения)
    [switch]$NoQuickStart
)

$ErrorActionPreference = "Stop"
$ModRoot = Split-Path $PSScriptRoot -Parent
$ExceptionLog = Join-Path $ModRoot "Module\eq_exceptions.log"
$RglLogs = "C:\ProgramData\Mount and Blade II Bannerlord\logs"

Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class SelfTestWin {
    delegate bool EnumProc(IntPtr h, IntPtr p);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr h, int id);
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr w, IntPtr l);

    public static Dictionary<IntPtr, string> Visible() {
        var result = new Dictionary<IntPtr, string>();
        EnumWindows((h, p) => {
            if (IsWindowVisible(h)) {
                var sb = new StringBuilder(256);
                GetWindowText(h, sb, 256);
                if (sb.Length > 0) result[h] = sb.ToString();
            }
            return true;
        }, IntPtr.Zero);
        return result;
    }

    // Нажатие кнопки диалога по её номеру: не зависит от языка надписей и раскладки.
    public static bool Click(IntPtr dialog, int buttonId) {
        var button = GetDlgItem(dialog, buttonId);
        if (button == IntPtr.Zero) return false;
        SendMessage(button, 0x00F5 /* BM_CLICK */, IntPtr.Zero, IntPtr.Zero);
        return true;
    }
}
"@

# Номера кнопок стандартных окон Windows
$IDOK = 1
$IDNO = 7

function Show-Errors {
    Write-Host "---- eq_exceptions.log (хвост) ----" -ForegroundColor Yellow
    if (Test-Path $ExceptionLog) {
        Get-Content $ExceptionLog -Encoding UTF8 | Select-Object -Last 40 | ForEach-Object { Write-Host $_ }
    }
    $rgl = Get-ChildItem "$RglLogs\rgl_log_*.txt" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch "errors" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($rgl) {
        Write-Host "---- $($rgl.Name) (хвост) ----" -ForegroundColor Yellow
        Get-Content $rgl.FullName | Where-Object { $_.Trim() } | Select-Object -Last 20 | ForEach-Object { Write-Host $_ }
    }
}

function Save-Screenshot($path) {
    Add-Type -AssemblyName System.Drawing
    Add-Type -AssemblyName System.Windows.Forms
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bitmap.Dispose()
}

# ---------------------------------------------------------------- запуск
$runArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $ModRoot "run.ps1"))
if (-not $NoQuickStart) { $runArgs += "-QuickStart" }
if ($GameArgs) { $runArgs += @("-ExtraArgs", $GameArgs) }
& powershell @runArgs | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) { Write-Host "ИТОГ: СБОРКА НЕ ПРОШЛА" -ForegroundColor Red; exit 2 }
$started = Get-Date

# ---------------------------------------------------------------- ожидание
Write-Host "== жду карту (до $Timeout с)" -ForegroundColor Cyan
$seenGame = $false
$result = "timeout"
while (((Get-Date) - $started).TotalSeconds -lt $Timeout) {
    foreach ($entry in [SelfTestWin]::Visible().GetEnumerator()) {
        $title = $entry.Value
        if ($title -eq "*_*") {
            [void][SelfTestWin]::Click($entry.Key, $IDNO)
            Write-Host "окно краша — нажато «Нет»" -ForegroundColor Red
            $result = "crash"
        }
        elseif ($title -eq "Safe Mode") {
            [void][SelfTestWin]::Click($entry.Key, $IDNO)
            Write-Host "окно безопасного режима — нажато «Нет»"
        }
        elseif ($title -eq "Mod change detected") {
            # у окна-уведомления «ОК» имеет номер 2 (IDCANCEL); пробуем оба
            if (-not [SelfTestWin]::Click($entry.Key, $IDOK)) { [void][SelfTestWin]::Click($entry.Key, 2) }
            Write-Host "окно смены модов — нажато OK"
        }
    }
    if ($result -eq "crash") { break }

    $game = Get-Process Bannerlord -ErrorAction SilentlyContinue
    if ($game) { $seenGame = $true }
    elseif ($seenGame) {
        Write-Host "игра закрылась сама" -ForegroundColor Red
        $result = "crash"
        break
    }

    if ((Test-Path $ExceptionLog) -and (Get-Item $ExceptionLog).LastWriteTime -gt $started) {
        if (Select-String -Path $ExceptionLog -Pattern $ReadyMark -SimpleMatch -Quiet -Encoding UTF8) {
            $result = "ready"
            break
        }
    }
    Start-Sleep -Milliseconds 700
}

function Stop-Game {
    if ($KeepOpen) { return }
    # Упавшую игру держит watchdog, и закрыть её сразу не дают — ждём, пока закроется сама.
    for ($i = 0; $i -lt 20; $i++) {
        $game = Get-Process Bannerlord -ErrorAction SilentlyContinue
        if (-not $game) { return }
        try { $game | Stop-Process -Force -ErrorAction Stop } catch { }
        Start-Sleep -Milliseconds 500
    }
}

# ---------------------------------------------------------------- итог
switch ($result) {
    "ready" {
        Write-Host "карта загружена, жду отрисовку..." -ForegroundColor Green
        Start-Sleep -Seconds $SettleSeconds
        Save-Screenshot $Shot
        Stop-Game
        $warnings = @(Select-String -Path $ExceptionLog -Pattern "!!!|исключение:" -Encoding UTF8)
        Write-Host "предупреждений и исключений в журнале: $($warnings.Count)"
        Write-Host "СНИМОК: $Shot"
        Write-Host "ИТОГ: ОК" -ForegroundColor Green
        exit 0
    }
    "crash" {
        Start-Sleep -Seconds 3
        Stop-Game
        Show-Errors
        Write-Host "ИТОГ: КРАШ" -ForegroundColor Red
        exit 1
    }
    default {
        Save-Screenshot $Shot
        Stop-Game
        Show-Errors
        Write-Host "СНИМОК: $Shot"
        Write-Host "ИТОГ: НЕ ДОЖДАЛСЯ КАРТЫ за $Timeout с" -ForegroundColor Yellow
        exit 3
    }
}
