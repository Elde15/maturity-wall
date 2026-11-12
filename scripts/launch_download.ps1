# Launch the full-universe EX-102 download as a detached, hidden Windows process.
# It is resumable: rerun this script after any interruption and it picks up
# where the state database left off. Progress goes to data/state/download.log.
#
# SEC_CONTACT must be set in the user environment (never in this repo).
param(
    [int]$Workers = 4,
    [double]$Rate = 7.0
)
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
$log = Join-Path $repo "data\state\download.log"
$err = Join-Path $repo "data\state\download.err.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
$p = Start-Process -FilePath $py `
    -ArgumentList @("-u", "-m", "mwall", "download", "--workers", $Workers, "--rate", $Rate) `
    -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError $err
"started download pid $($p.Id); log: $log"
Set-Content -Path (Join-Path $repo "data\state\download.pid") -Value $p.Id
