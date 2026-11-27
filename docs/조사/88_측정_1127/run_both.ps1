# Task 88: run 90 questions, old path (VCC_ASK_FULL=0) then A (=1). ASCII only (PowerShell 5.1 reads non-BOM files as ANSI).
# Usage: run_both.ps1 [prefix]   (prefix "re_" for the 11/27 re-run after #407 -> re_old/, re_A/)
param([string]$prefix = "")
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Resolve-Path "$here/../../..")
$env:VCC_TELL_CHAT = "0"; $env:VCC_ASK_CHAT = "0"; $env:VCC_ASK_OVERLAP = "1"; $env:PYTHONUNBUFFERED = "1"
"commit $(git rev-parse --short HEAD)"
foreach ($p in @(@{flag="0"; dir="old"}, @{flag="1"; dir="A"})) {
    $env:VCC_ASK_FULL = $p.flag
    "=== VCC_ASK_FULL=$($p.flag) start $(Get-Date -Format s)"
    python -X utf8 tools/run_eval.py --all90 --pause 4 --why --out "$here/$prefix$($p.dir)"
    "=== VCC_ASK_FULL=$($p.flag) end $(Get-Date -Format s)"
}
