# Щелчок мышью по экрану — для управления редактором, у которого нет программного интерфейса.
#
#   .\click.ps1 -X 182 -Y 104                 левый щелчок
#   .\click.ps1 -X 182 -Y 104 -Right          правый щелчок
#   .\click.ps1 -X 182 -Y 104 -Double         двойной щелчок
#   .\click.ps1 -Keys "{ENTER}"               нажать клавиши (формат SendKeys)
#   .\click.ps1 ... -Shot shot.png -Wait 1    после действия подождать и снять экран
#
# Перед действием окно редактора (заголовок "Edit Mode") выводится на передний план.
param(
    [int]$X = -1,
    [int]$Y = -1,
    [switch]$Right,
    [switch]$Double,
    [string]$Keys = "",
    [string]$Shot = "",
    [double]$Wait = 0.8,
    [string]$Window = "Edit Mode",
    # развернуть окно на весь экран: иначе оно двигается, и координаты уплывают
    [switch]$Maximize,
    # только навести курсор (чтобы прочитать всплывающую подсказку), без щелчка
    [switch]$Move,
    # прокрутка колесом в точке (X, Y): >0 — от себя, <0 — на себя; по одному «щелчку» колеса за раз
    [int]$Wheel = 0
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Mouse {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(int flags, int dx, int dy, int data, IntPtr extra);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindow(string c, string t);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    public static void Click(int x, int y, bool right, bool twice) {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(80);
        int down = right ? 0x0008 : 0x0002, up = right ? 0x0010 : 0x0004;
        for (int i = 0; i < (twice ? 2 : 1); i++) {
            mouse_event(down, 0, 0, 0, IntPtr.Zero);
            System.Threading.Thread.Sleep(40);
            mouse_event(up, 0, 0, 0, IntPtr.Zero);
            System.Threading.Thread.Sleep(90);
        }
    }
}
"@

$process = Get-Process | Where-Object { $_.MainWindowTitle -like $Window } | Select-Object -First 1
if ($process) {
    if ($Maximize) { [void][Mouse]::ShowWindow($process.MainWindowHandle, 3) }
    [void][Mouse]::SetForegroundWindow($process.MainWindowHandle)
    Start-Sleep -Milliseconds 250
}

if ($X -ge 0 -and $Y -ge 0 -and $Wheel -ne 0) {
    [void][Mouse]::SetCursorPos($X, $Y)
    Start-Sleep -Milliseconds 100
    for ($i = 0; $i -lt [Math]::Abs($Wheel); $i++) {
        [Mouse]::mouse_event(0x0800, 0, 0, [Math]::Sign($Wheel) * 120, [IntPtr]::Zero)
        Start-Sleep -Milliseconds 60
    }
    Write-Host "колесо ($X, $Y): $Wheel"
}
elseif ($X -ge 0 -and $Y -ge 0 -and $Move) {
    [void][Mouse]::SetCursorPos($X, $Y)
    Write-Host "курсор ($X, $Y)"
}
elseif ($X -ge 0 -and $Y -ge 0) {
    [Mouse]::Click($X, $Y, [bool]$Right, [bool]$Double)
    Write-Host "щелчок ($X, $Y)$(if ($Right) {' правый'})$(if ($Double) {' двойной'})"
}
if ($Keys) {
    [System.Windows.Forms.SendKeys]::SendWait($Keys)
    Write-Host "клавиши: $Keys"
}

if ($Shot) {
    Start-Sleep -Milliseconds ([int]($Wait * 1000))
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    $bitmap.Save($Shot, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bitmap.Dispose()
    Write-Host "снимок: $Shot"
}
