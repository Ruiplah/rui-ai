$ErrorActionPreference = "Continue"
Import-Module BitsTransfer -ErrorAction SilentlyContinue

$url = "https://hf-mirror.com/bartowski/Qwen_Qwen3.5-9B-GGUF/resolve/main/Qwen_Qwen3.5-9B-Q4_K_M.gguf"
$out = "D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf"
$target = 6169341984
$jobName = "qwen35_9b"
$log = "D:\llama\bits_download.log"

for ($i = 1; $i -le 1000; $i++) {
    # 1) 已完成？
    $size = if (Test-Path $out) { (Get-Item $out).Length } else { 0 }
    if ($size -ge $target) {
        Add-Content $log "DONE size=$size time=$(Get-Date -Format 'HH:mm:ss')"
        Get-BitsTransfer -Name $jobName -ErrorAction SilentlyContinue | ForEach-Object { if ($_.JobState -eq "Transferred") { Complete-BitsTransfer -BitsJob $_ -ErrorAction SilentlyContinue }; Remove-BitsTransfer -BitsJob $_ -ErrorAction SilentlyContinue }
        break
    }

    # 2) 找到已有 BITS 任务（可在系统服务中持久存在，断了可续传）
    $job = Get-BitsTransfer -Name $jobName -ErrorAction SilentlyContinue | Where-Object { $_.JobState -ne "Transferred" } | Select-Object -First 1

    # 3) 没有任务就新建
    if (-not $job) {
        try {
            $job = Start-BitsTransfer -Source $url -Destination $out -DisplayName $jobName -Asynchronous -ErrorAction Stop
            Add-Content $log "NEWJOB time=$(Get-Date -Format 'HH:mm:ss')"
        } catch {
            Add-Content $log "NEWJOB_ERR $($_.Exception.Message) time=$(Get-Date -Format 'HH:mm:ss')"
            Start-Sleep -Seconds 30
            continue
        }
    }

    # 4) 轮询任务状态
    $job = Get-BitsTransfer -Name $jobName -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($job) {
        $bt = $job.BytesTransferred; $btot = $job.BytesTotal
        $p = if ($btot -gt 0) { [math]::Round($bt / $btot * 100, 1) } else { 0 }
        Add-Content $log "poll state=$($job.JobState) $p% ($bt/$btot) time=$(Get-Date -Format 'HH:mm:ss')"

        if ($job.JobState -eq "Transferred") {
            Complete-BitsTransfer -BitsJob $job -ErrorAction SilentlyContinue
            Add-Content $log "COMPLETED time=$(Get-Date -Format 'HH:mm:ss')"
        } elseif ($job.JobState -eq "Error" -or $job.JobState -eq "TransientError") {
            Add-Content $log "ERROR resume time=$(Get-Date -Format 'HH:mm:ss')"
            Resume-BitsTransfer -BitsJob $job -ErrorAction SilentlyContinue
        }
    }

    Start-Sleep -Seconds 30
}
Add-Content $log "BITS_SCRIPT_END time=$(Get-Date -Format 'HH:mm:ss')"
