# Detached chain for the full-universe build (Gate 1 data). Resumable: every
# stage skips work already done. Waits for a running download to finish first.
#   1. EX-102 download (resumes if interrupted)
#   2. 10-D distribution statements for the balance reconciliation
#   3. parse -> clean -> whole loans -> tag census -> QA report
# Log: data/state/chain.log
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
$log = Join-Path $repo "data\state\chain.log"
Set-Location $repo
function Step($name, $argList) {
    Add-Content $log "[$(Get-Date -Format s)] START $name"
    & $py -u -W ignore -m mwall @argList *>> $log
    Add-Content $log "[$(Get-Date -Format s)] END $name (exit $LASTEXITCODE)"
}
$pidFile = Join-Path $repo "data\state\download.pid"
if (Test-Path $pidFile) {
    $dl = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*mwall download*' }
    foreach ($p in $dl) { Add-Content $log "[$(Get-Date -Format s)] waiting for download pid $($p.ProcessId)"; Wait-Process -Id $p.ProcessId -ErrorAction SilentlyContinue }
}
Step "download" @("download", "--workers", "8", "--rate", "7")
Step "tend" @("tend", "--workers", "8", "--rate", "7")
Step "parse" @("parse", "--workers", "3")
Step "clean" @("clean", "--workers", "3")
Step "wholeloans" @("wholeloans")
Step "census" @("census", "--per-group", "3")
Step "qa" @("qa")
Add-Content $log "[$(Get-Date -Format s)] CHAIN DONE"
