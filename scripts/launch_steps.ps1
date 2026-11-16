# Start run_steps.ps1 hidden and detached. Usage: launch_steps.ps1 "mwall panel" "mwall features --audit"
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Steps)
$repo = Split-Path -Parent $PSScriptRoot
$quoted = $Steps | ForEach-Object { '"' + $_ + '"' }
$p = Start-Process -FilePath "powershell.exe" -ArgumentList (@("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "run_steps.ps1")) + $quoted) -WindowStyle Hidden -PassThru
Set-Content -Path (Join-Path $repo "data\state\steps.pid") -Value $p.Id
"started steps pid $($p.Id); log: $(Join-Path $repo 'data\state\steps.log')"
