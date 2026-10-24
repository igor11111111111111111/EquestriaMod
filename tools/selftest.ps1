# Self-check without a human: build, run a quick test, wait for the map, take a screenshot.
#
#   .\tools\selftest.ps1                     full cycle
#   .\tools\selftest.ps1 -Timeout 300        wait for the map longer (after a shader cache reset)
#
# What it does along the way:
#   "Mod change detected" window  -> OK (notification about the shader cache reset)
#   "Safe Mode" window            -> No
#   crash window "*_*"            -> No, then prints the error logs, result: CRASH
#   the game closed by itself     -> prints the logs, result: CRASH
#   the session start mark appeared in eq_exceptions.log -> the map is ready, screenshot, result: OK
#
# The screenshot requires borderless windowed mode (display_mode = 2 in engine_config.txt): in
# exclusive fullscreen mode the frame comes out black.
param(
    [int]$Timeout = 240,
    [string]$Shot = "$env:TEMP\equestria_selftest.png",
    # leave the game open after the screenshot; by default we close it, as it holds the mod files
    [switch]$KeepOpen,
    # extra game switches, for example "/eqset:2" to show an armour set
    [string]$GameArgs = "",
    # the mod log line after which the screenshot can be taken
    [string]$ReadyMark = "опись данных мода: запуск сессии",
    # how long to wait after the mark before taking the screenshot
    [int]$SettleSeconds = 8,
    # do not start a new campaign (for example, for /eqload:name, loading a save)
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

# Button IDs of standard Windows dialogs
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

# ---------------------------------------------------------------- launch
$runArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $ModRoot "run.ps1"))
if (-not $NoQuickStart) { $runArgs += "-QuickStart" }
if ($GameArgs) { $runArgs += @("-ExtraArgs", $GameArgs) }
& powershell @runArgs | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) { Write-Host "ИТОГ: СБОРКА НЕ ПРОШЛА" -ForegroundColor Red; exit 2 }
$started = Get-Date

# ---------------------------------------------------------------- waiting
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
            # in the notification window "OK" has ID 2 (IDCANCEL); we try both
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
    # The crashed game is held by the watchdog and cannot be closed right away, so we wait until it closes by itself.
    for ($i = 0; $i -lt 20; $i++) {
        $game = Get-Process Bannerlord -ErrorAction SilentlyContinue
        if (-not $game) { return }
        try { $game | Stop-Process -Force -ErrorAction Stop } catch { }
        Start-Sleep -Milliseconds 500
    }
}

# ---------------------------------------------------------------- result
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
