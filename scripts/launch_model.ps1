# Start a Gate 3 model stage as a hidden, detached process. Usage: launch_model.ps1 rolling [ablations family]
param([string[]]$Stages = @("rolling"))
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
$log = Join-Path $repo "data\state\model.log"
$argsList = @("-m", "mwall", "model") + ($Stages | ForEach-Object { @("--stage", $_) })
$p = Start-Process -FilePath $py -ArgumentList $argsList -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError (Join-Path $repo "data\state\model.err")
Set-Content -Path (Join-Path $repo "data\state\model.pid") -Value $p.Id
"started model pid $($p.Id); log: $log"
