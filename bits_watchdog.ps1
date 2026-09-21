$ErrorActionPreference = "Continue"
Import-Module BitsTransfer -ErrorAction SilentlyContinue

$url = "https://hf-mirror.com/bartowski/Qwen_Qwen3.5-9B-GGUF/resolve/main/Qwen_Qwen3.5-9B-Q4_K_M.gguf"
$out = "D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf"
$target = 6169341984
$jobName = "qwen35_9b"
$log = "D:\llama\bits_watchdog.log"

for ($n = 1; $n -le 10000; $n++) {
    $size = if (Test-Path $out) { (Get-Item $out).Length } else { 0 }
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    if ($size -ge $target) {
        Add-Content $log "DONE size=$size time=$ts"
        break
    }

    $job = Get-BitsTransfer -Name $jobName -ErrorAction SilentlyContinue | Select-Object -First 1

    if ($job) {
        if ($job.JobState -eq "Transferred") {
            try {
                Complete-BitsTransfer -BitsJob $job -ErrorAction Stop
                Add-Content $log "COMPLETED time=$ts"
            } catch { Add-Content $log "COMPLETE_ERR $($_.Exception.Message) time=$ts" }
        } elseif ($job.JobState -eq "Error" -or $job.JobState -eq "TransientError") {
            Add-Content $log "JOB_ERROR resume time=$ts"
            Resume-BitsTransfer -BitsJob $job -ErrorAction SilentlyContinue
        }
    } else {
        Add-Content $log "NO_JOB recreate time=$ts"
        try {
            Start-BitsTransfer -Source $url -Destination $out -DisplayName $jobName -Asynchronous -ErrorAction Stop | Out-Null
            Add-Content $log "RECREATED time=$ts"
        } catch { Add-Content $log "RECREATE_ERR $($_.Exception.Message) time=$ts" }
    }

    Start-Sleep -Seconds 60
}
Add-Content $log "WATCHDOG_END time=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
