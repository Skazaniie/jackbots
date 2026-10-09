Add-Type -AssemblyName System.Drawing
$dir = 'C:\new\jackbox-ai\assets'
$outDir = Join-Path $dir 'web'
New-Item -ItemType Directory -Force $outDir | Out-Null
Get-ChildItem $dir -File | ForEach-Object {
  $src = [System.Drawing.Image]::FromFile($_.FullName)
  $s = [Math]::Min(1.0, 1400.0 / $src.Width)
  $w = [int][Math]::Round($src.Width * $s); $h = [int][Math]::Round($src.Height * $s)
  $bmp = New-Object System.Drawing.Bitmap -ArgumentList $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.DrawImage($src, 0, 0, $w, $h)
  $g.Dispose(); $src.Dispose()
  $out = Join-Path $outDir $_.Name
  if ($_.Extension -eq '.jpg') { $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Jpeg) } else { $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png) }
  $bmp.Dispose()
  "{0} {1}x{2} {3}KB" -f $_.Name, $w, $h, [int]((Get-Item $out).Length / 1024)
}
