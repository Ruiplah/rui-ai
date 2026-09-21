Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap 800,300
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::White)
$font1 = New-Object System.Drawing.Font("Microsoft YaHei", 36)
$font2 = New-Object System.Drawing.Font("Arial", 24)
$brush = [System.Drawing.Brushes]::Black
$g.DrawString("你好，Rui AI 智能助手", $font1, $brush, 40, 50)
$g.DrawString("Hello World 12345", $font2, $brush, 40, 160)
$g.Dispose()
$bmp.Save("D:\llama\ocr_test.png")
$bmp.Dispose()
Write-Output "test image created"
