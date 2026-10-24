# Screenshot - so the game can be looked at without distracting the person.
#
#   .\screenshot.ps1 -Wait 60 -Out shot.png
#
# Important: in exclusive fullscreen mode (display_mode = 1 in engine_config.txt) a normal
# screenshot comes out black. Borderless windowed is needed - display_mode = 2.
param(
    [int]$Wait = 0,
    [string]$Out = "$env:TEMP\bannerlord_shot.png"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

if ($Wait -gt 0) {
    Write-Host "Жду $Wait с, пока игра дойдёт до карты..."
    Start-Sleep -Seconds $Wait
}

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()

# A fully black frame means the game is in exclusive fullscreen mode after all.
$check = New-Object System.Drawing.Bitmap($Out)
$bright = 0
for ($x = 0; $x -lt $check.Width; $x += 97) {
    for ($y = 0; $y -lt $check.Height; $y += 89) {
        $p = $check.GetPixel($x, $y)
        if ($p.R + $p.G + $p.B -gt 30) { $bright++ }
    }
}
$check.Dispose()
Write-Host "Снимок: $Out ($($screen.Width)x$($screen.Height)), непустых точек в выборке: $bright"
if ($bright -eq 0) { Write-Host "Кадр чёрный — игра в исключительном полноэкранном режиме." }
