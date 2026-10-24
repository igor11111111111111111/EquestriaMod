# Запуск редактора со СНЯТИЕМ ТЕКСТА всех всплывающих окон.
#
#   .\tools\editor_errors.ps1                 запустить, собрать текст окон, закрыть их
#   .\tools\editor_errors.ps1 -Timeout 600    ждать дольше
#
# Зачем отдельно от tools/editor.ps1: тот молча жмёт кнопки по списку известных заголовков, и
# текст ошибки («RGL CONTENT WARNING: ... meta mesh ... not found») пропадает не прочитанным.
# Здесь каждое окно сначала читается целиком (заголовок + все надписи внутри), пишется в журнал,
# и только потом закрывается — так видно ВСЕ ошибки подряд, а не первую.
param(
    [int]$Timeout = 300,
    [string]$Log = ""
)

$ErrorActionPreference = "Stop"
$ModRoot = Split-Path $PSScriptRoot -Parent
$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
$EditorBin = Join-Path $Game "bin\Win64_Shipping_wEditor"
$Modules = @("Native", "SandBoxCore", "BirthAndDeath", "CustomBattle", "Sandbox", "StoryMode", "EquestriaMod")
if (-not $Log) { $Log = Join-Path $ModRoot "tools\editor_errors.txt" }

Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class DlgRead {
    delegate bool EnumProc(IntPtr h, IntPtr p);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr p);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetDlgItem(IntPtr h, int id);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr w, IntPtr l);

    static string TextOf(IntPtr h) {
        var sb = new StringBuilder(4096);
        GetWindowText(h, sb, 4096);
        return sb.ToString();
    }
    public static string ClassOf(IntPtr h) {
        var sb = new StringBuilder(256);
        GetClassName(h, sb, 256);
        return sb.ToString();
    }
    // Все видимые окна верхнего уровня: указатель -> "класс|заголовок"
    public static Dictionary<IntPtr, string> Windows() {
        var result = new Dictionary<IntPtr, string>();
        EnumWindows((h, p) => {
            if (IsWindowVisible(h)) {
                var title = TextOf(h);
                if (title.Length > 0) result[h] = ClassOf(h) + "|" + title;
            }
            return true;
        }, IntPtr.Zero);
        return result;
    }
    // Надписи и кнопки внутри окна — здесь и лежит сам текст ошибки
    public static List<string> Contents(IntPtr dialog) {
        var lines = new List<string>();
        EnumChildWindows(dialog, (h, p) => {
            var text = TextOf(h);
            if (text.Length > 0) lines.Add(ClassOf(h) + ": " + text);
            return true;
        }, IntPtr.Zero);
        return lines;
    }
    // Жмём первую существующую кнопку (1 OK, 2 Отмена/ОК, 6 Да, 7 Нет)
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

# Порядок кнопок: «Нет» для вопросов о безопасном режиме и падении, «ОК» для предупреждений.
$ByTitle = [ordered]@{
    '^Safe Mode$'           = @(7)
    '^\*_\*$'               = @(7)
    '^Mod change detected$' = @(1, 2)
}
$Default = @(1, 2, 6, 7)

$running = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and $_.Path.StartsWith($EditorBin, [StringComparison]::OrdinalIgnoreCase)
}
if ($running) {
    Write-Host "== закрываю открытый редактор" -ForegroundColor Cyan
    $running | ForEach-Object { try { $_ | Stop-Process -Force -ErrorAction Stop } catch { } }
    Start-Sleep -Seconds 2
}

$engineConfig = "$env:USERPROFILE\Documents\Mount and Blade II Bannerlord\Configs\engine_config.txt"
if (Test-Path $engineConfig) {
    $text = [IO.File]::ReadAllText($engineConfig)
    [IO.File]::WriteAllText($engineConfig, ($text -replace 'safely_exited\s*=\s*0', 'safely_exited = 1'))
}

Write-Host "== запуск редактора" -ForegroundColor Cyan
$gameArgs = "/singleplayer _MODULES_*" + ($Modules -join "*") + "*_ /eqeditor"
Start-Process -FilePath (Join-Path $EditorBin "Bannerlord.exe") -ArgumentList $gameArgs -WorkingDirectory $EditorBin
$started = Get-Date
$seen = @{}
$found = 0
"Запуск редактора $(Get-Date -Format 'dd.MM.yyyy HH:mm:ss')" | Set-Content -Encoding UTF8 $Log

while (((Get-Date) - $started).TotalSeconds -lt $Timeout) {
    foreach ($entry in [DlgRead]::Windows().GetEnumerator()) {
        $class, $title = $entry.Value.Split('|', 2)
        if ($class -ne "#32770") { continue }          # только диалоговые окна
        $key = "$title|" + ([DlgRead]::Contents($entry.Key) -join "~")
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        $found++
        $block = @("", "=== окно $found : $title") + ([DlgRead]::Contents($entry.Key) | ForEach-Object { "    $_" })
        $block | ForEach-Object { Write-Host $_ }
        $block | Add-Content -Encoding UTF8 $Log

        $buttons = $Default
        foreach ($pattern in $ByTitle.Keys) {
            if ($title -match $pattern) { $buttons = $ByTitle[$pattern]; break }
        }
        [void][DlgRead]::Click($entry.Key, [int[]]$buttons)
    }
    if ([DlgRead]::Windows().Values -contains "#32770|Edit Mode" -or
        ([DlgRead]::Windows().Values | Where-Object { $_ -like "*|Edit Mode" })) {
        Write-Host "== редактор открылся" -ForegroundColor Green
        break
    }
    if (-not (Get-Process Bannerlord -ErrorAction SilentlyContinue) -and
        ((Get-Date) - $started).TotalSeconds -gt 15) {
        Write-Host "== редактор завершился" -ForegroundColor Yellow
        break
    }
    Start-Sleep -Milliseconds 400
}

Write-Host ""
Write-Host "окон с текстом: $found, журнал: $Log" -ForegroundColor Cyan
