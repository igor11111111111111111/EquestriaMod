# Запуск редактора Modding Kit одной командой — без лаунчера и без щелчков по окнам.
#
#   .\tools\editor.ps1                 собрать мод, открыть редактор, дождаться окна Edit Mode
#   .\tools\editor.ps1 -Shot shot.png  то же, и снимок экрана, когда редактор открылся
#
# Что происходит вместо ручных шагов:
#   лаунчер              -> Bannerlord.exe из Win64_Shipping_wEditor запускается напрямую
#   кнопка «Редактор»    -> мод видит ключ /eqeditor и сам нажимает пункт меню Editor
#   "Safe Mode"          -> Нет       (и заранее ставим safely_exited = 1)
#   "Mod change detected"-> OK
#   "RGL WARNING"        -> OK
#   "*_*" (application faced a problem) -> Нет
#   "Always Ignore?"     -> OK
#
# Уже открытый редактор закрывается: запущенный держит DLL мода, и сборка не может её обновить.
param(
    [int]$Timeout = 300,
    [string]$Shot = ""
)

$ErrorActionPreference = "Stop"
$ModRoot = Split-Path $PSScriptRoot -Parent
$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
$EditorBin = Join-Path $Game "bin\Win64_Shipping_wEditor"
$ExceptionLog = Join-Path $ModRoot "Module\eq_exceptions.log"
$Modules = @("Native", "SandBoxCore", "BirthAndDeath", "CustomBattle", "Sandbox", "StoryMode", "EquestriaMod")

Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class EditorWin {
    delegate bool EnumProc(IntPtr h, IntPtr p);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetDlgItem(IntPtr h, int id);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr w, IntPtr l);

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

    // Нажимает первую существующую кнопку из списка номеров (1 OK, 2 Отмена, 6 Да, 7 Нет).
    public static int Click(IntPtr dialog, int[] ids) {
        foreach (var id in ids) {
            var button = GetDlgItem(dialog, id);
            if (button != IntPtr.Zero) {
                SendMessage(button, 0x00F5, IntPtr.Zero, IntPtr.Zero);
                return id;
            }
        }
        return 0;
    }
}
"@

$IDOK = 1; $IDCANCEL = 2; $IDYES = 6; $IDNO = 7
# заголовок (регулярное выражение) -> кнопки по порядку предпочтения
$Dialogs = [ordered]@{
    '^Safe Mode$'            = @($IDNO)
    # у окна-уведомления единственная кнопка «ОК» имеет номер 2 (IDCANCEL), а не 1
    '^Mod change detected$'  = @($IDOK, $IDCANCEL)
    'RGL WARNING'            = @($IDOK, $IDCANCEL, $IDYES)
    '^\*_\*$'                = @($IDNO)
    'Always Ignore'          = @($IDOK, $IDCANCEL, $IDYES)
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

# ---------------------------------------------------------------- закрыть открытый редактор
$running = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and $_.Path.StartsWith($EditorBin, [StringComparison]::OrdinalIgnoreCase)
}
if ($running) {
    Write-Host "== закрываю открытый редактор" -ForegroundColor Cyan
    $running | ForEach-Object { try { $_ | Stop-Process -Force -ErrorAction Stop } catch { } }
    Start-Sleep -Seconds 2
}

# ---------------------------------------------------------------- сборка (кладёт DLL и в папку редактора)
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ModRoot "run.ps1") -NoLaunch | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) { Write-Host "ИТОГ: СБОРКА НЕ ПРОШЛА" -ForegroundColor Red; exit 2 }

# ---------------------------------------------------------------- запуск
$engineConfig = "$env:USERPROFILE\Documents\Mount and Blade II Bannerlord\Configs\engine_config.txt"
if (Test-Path $engineConfig) {
    $text = [IO.File]::ReadAllText($engineConfig)
    [IO.File]::WriteAllText($engineConfig, ($text -replace 'safely_exited\s*=\s*0', 'safely_exited = 1'))
}
$gameArgs = "/singleplayer _MODULES_*" + ($Modules -join "*") + "*_ /eqeditor"
Write-Host "== запуск редактора" -ForegroundColor Cyan
Start-Process -FilePath (Join-Path $EditorBin "Bannerlord.exe") -ArgumentList $gameArgs -WorkingDirectory $EditorBin
$started = Get-Date

# ---------------------------------------------------------------- окна и ожидание
$handled = @{}
$result = "timeout"
while (((Get-Date) - $started).TotalSeconds -lt $Timeout) {
    foreach ($entry in [EditorWin]::Visible().GetEnumerator()) {
        $title = $entry.Value
        foreach ($pattern in $Dialogs.Keys) {
            if ($title -match $pattern) {
                $pressed = [EditorWin]::Click($entry.Key, [int[]]$Dialogs[$pattern])
                if ($pressed -and -not $handled.ContainsKey($entry.Key)) {
                    Write-Host "окно «$title» — нажата кнопка $pressed"
                    $handled[$entry.Key] = $true
                }
            }
        }
        if ($title -eq "Edit Mode") { $result = "ready" }
    }
    if ($result -eq "ready") { break }
    if (-not (Get-Process Bannerlord -ErrorAction SilentlyContinue)) {
        if (((Get-Date) - $started).TotalSeconds -gt 15) { $result = "gone"; break }
    }
    Start-Sleep -Milliseconds 600
}

switch ($result) {
    "ready" {
        Write-Host "ИТОГ: РЕДАКТОР ОТКРЫТ ($([int]((Get-Date) - $started).TotalSeconds) с)" -ForegroundColor Green
        if ($Shot) { Start-Sleep -Seconds 5; Save-Screenshot $Shot; Write-Host "СНИМОК: $Shot" }
        exit 0
    }
    "gone" {
        Write-Host "ИТОГ: РЕДАКТОР ЗАКРЫЛСЯ" -ForegroundColor Red
        if (Test-Path $ExceptionLog) { Get-Content $ExceptionLog -Encoding UTF8 | Select-Object -Last 20 | ForEach-Object { Write-Host $_ } }
        exit 1
    }
    default {
        if ($Shot) { Save-Screenshot $Shot; Write-Host "СНИМОК: $Shot" }
        Write-Host "ИТОГ: НЕ ДОЖДАЛСЯ РЕДАКТОРА за $Timeout с" -ForegroundColor Yellow
        if (Test-Path $ExceptionLog) { Get-Content $ExceptionLog -Encoding UTF8 | Select-Object -Last 20 | ForEach-Object { Write-Host $_ } }
        exit 3
    }
}
