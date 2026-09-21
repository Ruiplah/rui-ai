# 本地 AI 服务守护：检查 8080(llama-server) 和 8082(agent_server)，挂了自动拉起
$ErrorActionPreference = "Continue"
$log = "D:\llama\keeper.log"
$llama = "D:\llama\llama-server.exe"
$model = "D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf"
$webui = "D:\llama\webui"
$agentPy = "C:\Users\123\AppData\Local\Doubao\User Data\sandbox_runtime\bases\c98c5042338ed152c6f10ecd8591889f\python\python.exe"
$agentScript = "D:\llama\agent_server.py"

function Test-Port($port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect("127.0.0.1", $port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(2000)) { $c.Close(); return $false }
        $c.EndConnect($iar); $c.Close(); return $true
    } catch { return $false }
}

if (-not (Test-Port 8080)) {
    Start-Process -FilePath $llama -ArgumentList '-m',$model,'-c','32768','--port','8080','--host','127.0.0.1','--path',$webui -WindowStyle Hidden
    Add-Content $log ("restart llama-server ctx=32768 " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
}
if (-not (Test-Port 8082)) {
    Start-Process -FilePath $agentPy -ArgumentList $agentScript -WindowStyle Hidden
    Add-Content $log ("restart agent_server " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
}
