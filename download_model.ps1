$ErrorActionPreference = "Continue"
$url = "https://hf-mirror.com/bartowski/Qwen_Qwen3.5-9B-GGUF/resolve/main/Qwen_Qwen3.5-9B-Q4_K_M.gguf"
$out = "D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf"
$target = 6169341984
$log = "D:\llama\model_download.log"

for ($i = 1; $i -le 100; $i++) {
    $size = if (Test-Path $out) { (Get-Item $out).Length } else { 0 }
    if ($size -ge $target) {
        Add-Content $log "DONE size=$size"
        break
    }
    Add-Content $log "attempt=$i start=$size"
    & curl.exe -L -C - --retry 3 --retry-all-errors --connect-timeout 20 --max-time 900 -sS -o $out $url 2>&1 | Out-Null
    Add-Content $log "attempt=$i exit=$LASTEXITCODE size=$((Get-Item $out -ErrorAction SilentlyContinue).Length)"
    Start-Sleep -Seconds 5
}
Add-Content $log "SCRIPT_END"
