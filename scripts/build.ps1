# Build a presentation folder into ONE self-contained HTML file that opens by double-click
# (file://, offline, no Python / no server / no install needed on the presenting computer).
#
#   powershell -ExecutionPolicy Bypass -File build.ps1 -Project <folder> [-Entry main.html] [-Out <name>.html]
#
# Step 1: every <Project>\assets\models\*.glb is converted to *.glb.js
#         ( (window.GLB=window.GLB||{})['<name>']='<base64>'; ) when missing or older than the .glb.
#         After this step <Project>\main.html itself also works by double-click (dev preview).
# Step 2: every local <script src="..."></script> in the entry HTML is replaced by the file's content
#         and the result is written to -Out (default: <Project>\dist\<page title>.html).
# Remote (http/https) scripts are left untouched and reported, because they would need a network.
param(
  [Parameter(Mandatory = $true)][string]$Project,
  [string]$Entry = 'main.html',
  [string]$Out = ''
)
$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$Project = (Resolve-Path -LiteralPath $Project).Path

# ---- step 1: GLB -> GLB.js ----
$models = Join-Path $Project 'assets\models'
if (Test-Path -LiteralPath $models) {
  Get-ChildItem -LiteralPath $models -Filter *.glb | ForEach-Object {
    $js = $_.FullName + '.js'
    if ((Test-Path -LiteralPath $js) -and ((Get-Item -LiteralPath $js).LastWriteTime -ge $_.LastWriteTime)) { return }
    $name = $_.BaseName -replace "\\", "\\\\" -replace "'", "\'"
    $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($_.FullName))
    [IO.File]::WriteAllText($js, "(window.GLB=window.GLB||{})['$name']='$b64';`n", $utf8)
    "model  : $($_.Name) -> $($_.Name).js"
  }
}

# ---- step 2: inline local scripts ----
$entryPath = Join-Path $Project $Entry
if (-not (Test-Path -LiteralPath $entryPath)) { throw "Entry not found: $entryPath" }
$html = [IO.File]::ReadAllText($entryPath, [Text.Encoding]::UTF8)
$base = Split-Path -Parent $entryPath
$missing = New-Object System.Collections.Generic.List[string]
$remote = New-Object System.Collections.Generic.List[string]

$evaluator = [System.Text.RegularExpressions.MatchEvaluator] {
  param($m)
  $src = $m.Groups[1].Value
  if ($src -match '^(https?:)?//') { $remote.Add($src); return $m.Value }
  $path = Join-Path $base ([Uri]::UnescapeDataString(($src -split '[?#]')[0]) -replace '/', '\')
  if (-not (Test-Path -LiteralPath $path)) { $missing.Add($src); return $m.Value }
  $code = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8)
  # a literal "</script" inside inlined code would end the tag early
  $code = [regex]::Replace($code, '</(script)', '<\/$1', 'IgnoreCase')
  "<script>/* inlined: $src */`n$code`n</script>"
}
$html = [regex]::Replace($html, '<script\s+src="([^"]+)"\s*>\s*</script>', $evaluator, 'IgnoreCase')

if ($missing.Count) { throw "Local script(s) not found: $($missing -join ', ')" }
if ($remote.Count) { "warning: remote script(s) still need a network: $($remote -join ', ')" }
if ($html -match '<script\s+type="importmap"') { "warning: importmap found - ES module imports from a CDN will fail offline" }

if (-not $Out) {
  $title = 'presentation'
  if ($html -match '<title>([^<]+)</title>') { $title = ($Matches[1] -split '[|\uFF5C]')[0].Trim() }
  $title = $title -replace '[\\/:*?"<>|]', '_'
  $Out = Join-Path (Join-Path $Project 'dist') "$title.html"
}
New-Item -ItemType Directory -Force (Split-Path -Parent $Out) | Out-Null
[IO.File]::WriteAllText($Out, $html, $utf8)
"output : $Out ($([math]::Round((Get-Item -LiteralPath $Out).Length / 1MB, 2)) MB)"
