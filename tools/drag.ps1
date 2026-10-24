# Перетаскивание мышью с зажатой левой кнопкой — например, чтобы повернуть модель на экране отряда.
#
#   .\tools\drag.ps1 -X 960 -Y 600 -DX 300              протянуть вправо на 300 пикселей
#   .\tools\drag.ps1 -X 960 -Y 600 -DX 300 -Shot a.png  и снять экран
param(
    [Parameter(Mandatory)] [int]$X,
    [Parameter(Mandatory)] [int]$Y,
    [int]$DX = 0,
    [int]$DY = 0,
    [int]$Steps = 30,
    [string]$Window = "Mount and Blade II Bannerlord",
    [string]$Shot = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices; using System.Text;
public static class DragWin {
  delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(int f, int dx, int dy, int d, IntPtr e);
  public static IntPtr Find(string prefix) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, p) => {
      var sb = new StringBuilder(512); GetWindowText(h, sb, 512);
      if (IsWindowVisible(h) && sb.ToString().StartsWith(prefix)) { found = h; return false; }
      return true; }, IntPtr.Zero);
    return found;
  }
}
"@

$h = [DragWin]::Find($Window)
if ($h -ne [IntPtr]::Zero) { [DragWin]::SetForegroundWindow($h) | Out-Null; Start-Sleep -Milliseconds 300 }
[DragWin]::SetCursorPos($X, $Y) | Out-Null
Start-Sleep -Milliseconds 100
[DragWin]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)  # LEFTDOWN
for ($i = 1; $i -le $Steps; $i++) {
    [DragWin]::SetCursorPos($X + [int]($DX * $i / $Steps), $Y + [int]($DY * $i / $Steps)) | Out-Null
    Start-Sleep -Milliseconds 20
}
[DragWin]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)  # LEFTUP
Write-Output "протянуто ($X, $Y) на ($DX, $DY)"
if ($Shot) {
    Start-Sleep -Milliseconds 800
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bmp.Save($Shot, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Write-Output "снимок: $Shot"
}
