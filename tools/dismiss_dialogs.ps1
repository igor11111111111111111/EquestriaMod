# Закрывает окна-вопросы, которые Bannerlord показывает до главного меню.
#
#   .\dismiss_dialogs.ps1 -Seconds 90
#
# Зачем: при запуске из скрипта игра каждый раз спрашивает про смену модов и про безопасный режим,
# и до тех пор ничего не грузит. Руками это терпимо, а для самопроверки — стоп-кран.
#
# Что с чем делаем:
#   "Mod change detected" — просто OK, это уведомление о сбросе кэша шейдеров;
#   "Safe Mode"          — Esc, то есть "Нет": безопасный режим нам не нужен.
param([int]$Seconds = 90)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win {
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr FindWindow(string cls, string title);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr h);
}
"@

# заголовок окна -> какую клавишу отправить
$dialogs = @{
    "Mod change detected" = "{ENTER}"
    "Safe Mode"           = "{ESC}"
}

$deadline = (Get-Date).AddSeconds($Seconds)
$closed = @{}
while ((Get-Date) -lt $deadline) {
    foreach ($title in $dialogs.Keys) {
        $handle = [Win]::FindWindow($null, $title)
        if ($handle -ne [IntPtr]::Zero) {
            [void][Win]::SetForegroundWindow($handle)
            Start-Sleep -Milliseconds 250
            [System.Windows.Forms.SendKeys]::SendWait($dialogs[$title])
            if (-not $closed.ContainsKey($title)) {
                Write-Host "закрыто окно: $title"
                $closed[$title] = $true
            }
            Start-Sleep -Milliseconds 400
        }
    }
    Start-Sleep -Milliseconds 500
}
if ($closed.Count -eq 0) { Write-Host "окон-вопросов не было" }
