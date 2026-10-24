# Снимок экрана — чтобы можно было посмотреть на игру, не отвлекая человека.
#
#   .\screenshot.ps1 -Wait 60 -Out shot.png
#
# Важно: из исключительного полноэкранного режима (display_mode = 1 в engine_config.txt) обычный
# снимок выходит чёрным. Нужен оконный без рамки — display_mode = 2.
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

# Полностью чёрный кадр означает, что игра всё же в исключительном полноэкранном режиме.
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
