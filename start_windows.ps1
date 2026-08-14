$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3 -m venv .venv
    & .venv\Scripts\python.exe -m pip install -r requirements.txt
}
if (-not $env:HAMLOG_AES_KEY) {
    Write-Warning "HAMLOG_AES_KEY is not set. AES encryption cannot be enabled."
}
& .venv\Scripts\python.exe run.py
