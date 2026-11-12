# Start run_full_ingest.ps1 as a hidden, detached process.
$repo = Split-Path -Parent $PSScriptRoot
$p = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "run_full_ingest.ps1")) -WindowStyle Hidden -PassThru
Set-Content -Path (Join-Path $repo "data\state\chain.pid") -Value $p.Id
"started chain pid $($p.Id); log: $(Join-Path $repo 'data\state\chain.log')"
