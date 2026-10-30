# Headless screenshots of main.html slides + one contact sheet, for visual QA.
# Uses Edge (always present on Windows) with SwiftShader so WebGL works without a GPU window.
# Usage:
#   powershell -ExecutionPolicy Bypass -File screenshot_slides.ps1 -Url <project>\dist\<title>.html -Slides 1,2,2.2,3 -OutDir <scratch dir>
# Slides use the page's "#<slide>.<step>" hash; "?still" freezes animation so shots are deterministic.
param(
  [Parameter(Mandatory=$true)][string]$Url,
  [Parameter(Mandatory=$true)][string[]]$Slides,
  [Parameter(Mandatory=$true)][string]$OutDir,
  [int]$Width = 1600,
  [int]$Height = 900
)
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw 'Microsoft Edge not found' }
# "powershell -File" passes -Slides 1,2,3 as ONE string; split it
$Slides = @($Slides | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
# -Url may also be a local file path (the built single HTML or main.html); open it via file://
if (Test-Path -LiteralPath $Url) { $Url = ([Uri](Resolve-Path -LiteralPath $Url).Path).AbsoluteUri }
New-Item -ItemType Directory -Force $OutDir | Out-Null

foreach ($s in $Slides) {
  & $edge --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --hide-scrollbars `
    --window-size=$Width,$Height --virtual-time-budget=15000 --user-data-dir="$OutDir\profile" `
    --screenshot="$OutDir\s$s.png" "$($Url)?still#$s" 2>$null | Out-Null
}

# Contact sheet: 2 columns of 640x360 thumbnails, labelled with the slide hash
Add-Type -AssemblyName System.Drawing
$W = 640; $H = 360; $rows = [math]::Ceiling($Slides.Count / 2)
$bmp = New-Object Drawing.Bitmap ($W * 2), ($H * $rows)
$g = [Drawing.Graphics]::FromImage($bmp)
$font = New-Object Drawing.Font 'Arial', 16, ([Drawing.FontStyle]::Bold)
for ($i = 0; $i -lt $Slides.Count; $i++) {
  $f = "$OutDir\s$($Slides[$i]).png"
  if (-not (Test-Path $f)) { continue }
  $im = [Drawing.Image]::FromFile($f)
  $x = ($i % 2) * $W; $y = [math]::Floor($i / 2) * $H
  $g.DrawImage($im, $x, $y, $W, $H)
  $g.FillRectangle([Drawing.Brushes]::Yellow, $x, $y, 70, 26)
  $g.DrawString("#" + $Slides[$i], $font, [Drawing.Brushes]::Black, $x + 2, $y + 2)
  $im.Dispose()
}
$bmp.Save("$OutDir\contact-sheet.png"); $g.Dispose(); $bmp.Dispose()
"Saved $OutDir\contact-sheet.png"
