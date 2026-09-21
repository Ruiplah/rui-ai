$amdPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000"
Set-ItemProperty -Path $amdPath -Name "EnableUlps" -Value 1 -Type DWord
Set-ItemProperty -Path $amdPath -Name "PP_GPUPowerDownEnabled" -Value 1 -Type DWord
Write-Output "ULPS已恢复启用"
