# Closes the question dialogs Bannerlord shows before the main menu.
#
#   .\dismiss_dialogs.ps1 -Seconds 90
#
# Why: when launched from a script, the game asks every time about the mod change and about safe mode,
# and loads nothing until answered. By hand this is tolerable, but for self-checks it is a blocker.
#
# What we do with each:
#   "Mod change detected" - just OK, it is a notice about the shader cache reset;
#   "Safe Mode"          - Esc, i.e. "No": we do not need safe mode.
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

# window title -> which key to send
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
