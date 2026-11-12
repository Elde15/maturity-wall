# Detached chain for the full-universe build (Gate 1 data). Resumable: every
# stage skips work already done. Waits for a running download to finish first.
#   1. EX-102 download (resumes if interrupted)
#   2. 10-D distribution statements, in parallel with step 3 (network-bound
#      beside CPU-bound work; log data/state/tend.log)
#   3. parse -> clean -> whole loans -> geography
#   4. once step 2 is done: tag census -> QA report
# Log: data/state/chain.log
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
$state = Join-Path $repo "data\state"
$log = Join-Path $state "chain.log"
Set-Location $repo
function Step($name, $argList) {
    Add-Content $log "[$(Get-Date -Format s)] START $name"
    & $py -u -W ignore -m mwall @argList *>> $log
    Add-Content $log "[$(Get-Date -Format s)] END $name (exit $LASTEXITCODE)"
}
$dl = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*mwall download*' }
foreach ($p in $dl) { Add-Content $log "[$(Get-Date -Format s)] waiting for download pid $($p.ProcessId)"; Wait-Process -Id $p.ProcessId -ErrorAction SilentlyContinue }
Step "download" @("download", "--workers", "8", "--rate", "7")

Add-Content $log "[$(Get-Date -Format s)] START tend (parallel; log data/state/tend.log)"
$tend = Start-Process -FilePath $py -ArgumentList @("-u", "-W", "ignore", "-m", "mwall", "tend", "--workers", "8", "--rate", "7") `
    -RedirectStandardOutput (Join-Path $state "tend.log") -RedirectStandardError (Join-Path $state "tend.err.log") `
    -WindowStyle Hidden -PassThru -WorkingDirectory $repo
Step "parse" @("parse", "--workers", "3")
Step "clean" @("clean", "--workers", "3")
Step "wholeloans" @("wholeloans")
Step "geo" @("geo")
Add-Content $log "[$(Get-Date -Format s)] waiting for tend pid $($tend.Id)"
Wait-Process -Id $tend.Id -ErrorAction SilentlyContinue
Add-Content $log "[$(Get-Date -Format s)] END tend"
Step "census" @("census", "--per-group", "3")
Step "qa" @("qa")
Add-Content $log "[$(Get-Date -Format s)] CHAIN DONE"
