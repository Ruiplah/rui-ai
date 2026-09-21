$ErrorActionPreference = "Continue"
$out = "D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf"
$target = 6169341984
$dlScript = "D:\llama\download_model.ps1"
$log = "D:\llama\watchdog.log"
$prevSize = -1

for ($n = 1; $n -le 10000; $n++) {
    $size = if (Test-Path $out) { (Get-Item $out).Length } else { 0 }
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    if ($size -ge $target) {
        Add-Content $log "DONE size=$size time=$ts"
        break
    }

    # 检测文件回退（可能由 curl 断点续传异常导致）：大小明显变小 -> 杀掉 curl 和下载脚本后重启，避免反复回退
    if ($prevSize -gt 0 -and ($prevSize - $size) -gt 104857600) { # >100MB 回退
        Add-Content $log "REGRESSION prev=$prevSize size=$size time=$ts -> kill & restart"
        Get-Process curl -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*download_model.ps1*' -and $_.ProcessId -ne $PID } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 3
        Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$dlScript -WindowStyle Hidden
        Add-Content $log "REGRESSION restart launched time=$ts"
        $prevSize = $size
        Start-Sleep -Seconds 60
        continue
    }

    # 检测下载停滞：进程全死 -> 重启
    $curlAlive = @(Get-Process curl -ErrorAction SilentlyContinue).Count -gt 0
    $dlAlive = $false
    try {
        $dlAlive = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction Stop |
            Where-Object { $_.CommandLine -like '*download_model.ps1*' -and $_.ProcessId -ne $PID }).Count -gt 0
    } catch {}
    if (-not $curlAlive -and -not $dlAlive) {
        Add-Content $log "RESTART size=$size time=$ts"
        Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$dlScript -WindowStyle Hidden
    }

    $prevSize = $size
    Start-Sleep -Seconds 60
}
Add-Content $log "WATCHDOG_END time=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
