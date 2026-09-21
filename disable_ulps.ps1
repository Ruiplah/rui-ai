$amdPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000"
Set-ItemProperty -Path $amdPath -Name "EnableUlps" -Value 0 -Type DWord
Set-ItemProperty -Path $amdPath -Name "PP_GPUPowerDownEnabled" -Value 0 -Type DWord
Write-Output "ULPS已禁用"
