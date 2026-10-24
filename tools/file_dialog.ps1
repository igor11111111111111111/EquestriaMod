# Type a path into the standard Windows file selection dialog and press "Open".
#
#   .\tools\file_dialog.ps1 -Title "Open Scene" -Path "D:\...\scene.xscene"
#
# SendKeys is no good for this: it treats the brackets in "Program Files (x86)" as special, and Ctrl+A
# does not work in this field. So we put the text directly into the file name field (WM_SETTEXT).
param(
    [Parameter(Mandatory)] [string]$Title,
    [Parameter(Mandatory)] [string]$Path
)

Add-Type @"
using System; using System.Runtime.InteropServices; using System.Text;
public static class FileDialogWin {
  delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr p);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern IntPtr GetDlgItem(IntPtr h, int id);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, int m, IntPtr w, string l);
  [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, int m, IntPtr w, IntPtr l);

  public static string Open(string title, string path) {
    IntPtr dialog = IntPtr.Zero;
    EnumWindows((h, p) => {
      var text = new StringBuilder(256); GetWindowText(h, text, 256);
      var cls = new StringBuilder(64); GetClassName(h, cls, 64);
      if (IsWindowVisible(h) && text.ToString() == title && cls.ToString() == "#32770") dialog = h;
      return true;
    }, IntPtr.Zero);
    if (dialog == IntPtr.Zero) return "окно не найдено";
    // 1148 — выпадающий список «Имя файла», внутри него обычное поле ввода
    IntPtr combo = GetDlgItem(dialog, 1148);
    IntPtr edit = IntPtr.Zero;
    if (combo != IntPtr.Zero) EnumChildWindows(combo, (h, p) => {
      var cls = new StringBuilder(64); GetClassName(h, cls, 64);
      if (cls.ToString() == "Edit") edit = h;
      return true;
    }, IntPtr.Zero);
    if (edit == IntPtr.Zero) return "поле имени файла не найдено";
    SendMessage(edit, 0x000C, IntPtr.Zero, path);                              // WM_SETTEXT
    SendMessage(GetDlgItem(dialog, 1), 0x00F5, IntPtr.Zero, IntPtr.Zero);      // «Открыть»
    return "открыто";
  }
}
"@

$deadline = (Get-Date).AddSeconds(10)
do {
    $result = [FileDialogWin]::Open($Title, $Path)
    if ($result -eq "открыто") { break }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)
Write-Host "окно «$Title»: $result"
