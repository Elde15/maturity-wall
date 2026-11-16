# Run python module commands in order, stopping at the first failure. Usage:
#   run_steps.ps1 "mwall panel" "mwall features --audit" "mwall.model.select"
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Steps)
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
$log = Join-Path $repo "data\state\steps.log"
Set-Location $repo
foreach ($s in $Steps) {
    "[$(Get-Date -Format HH:mm:ss)] START $s" | Out-File -Append -Encoding utf8 $log
    $argv = @("-m") + ($s -split " ")
    & $py @argv *>> $log
    if ($LASTEXITCODE -ne 0) { "[$(Get-Date -Format HH:mm:ss)] FAILED $s (exit $LASTEXITCODE)" | Out-File -Append -Encoding utf8 $log; exit 1 }
    "[$(Get-Date -Format HH:mm:ss)] DONE $s" | Out-File -Append -Encoding utf8 $log
}
"[$(Get-Date -Format HH:mm:ss)] ALL DONE" | Out-File -Append -Encoding utf8 $log
