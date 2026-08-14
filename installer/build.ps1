[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$SkipInstaller,
    [string]$Python = "py"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$InstallerDir = $PSScriptRoot
$RepoRoot = Split-Path -Parent $InstallerDir
$BuildEnvironment = Join-Path $InstallerDir ".build-venv"
$BuildDir = Join-Path $InstallerDir "build"
$DistDir = Join-Path $InstallerDir "dist"
$VenvPython = Join-Path $BuildEnvironment "Scripts\python.exe"
$SpecFile = Join-Path $InstallerDir "HamLog.spec"
$InnoScript = Join-Path $InstallerDir "HamLog.iss"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath"
    }
}

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $BuildDir, $DistDir
}

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    if ($Python -eq "py") {
        Invoke-Checked -FilePath "py" -ArgumentList @("-3", "-m", "venv", $BuildEnvironment)
    } else {
        Invoke-Checked -FilePath $Python -ArgumentList @("-m", "venv", $BuildEnvironment)
    }
}

Invoke-Checked -FilePath $VenvPython -ArgumentList @(
    "-m", "pip", "install", "--disable-pip-version-check",
    "-r", (Join-Path $RepoRoot "requirements.txt"),
    "-r", (Join-Path $InstallerDir "requirements-build.txt")
)
Invoke-Checked -FilePath $VenvPython -ArgumentList @(
    "-m", "PyInstaller", "--noconfirm", "--clean",
    "--distpath", $DistDir,
    "--workpath", $BuildDir,
    $SpecFile
)

if ($SkipInstaller) {
    Write-Host "PyInstaller bundle: $(Join-Path $DistDir 'HamLog\HamLog.exe')"
    return
}

$IsccCommand = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
$IsccPath = if ($null -ne $IsccCommand) { $IsccCommand.Source } else { $null }
$Candidates = @()
if (${env:ProgramFiles(x86)}) {
    $Candidates += Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
}
if ($env:ProgramFiles) {
    $Candidates += Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"
}
if ($env:LOCALAPPDATA) {
    $Candidates += Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
}
if (-not $IsccPath) {
    $IsccPath = $Candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $IsccPath) {
    throw "Inno Setup 6 was not found. Install it or rerun with -SkipInstaller."
}

Invoke-Checked -FilePath $IsccPath -ArgumentList @("/Qp", $InnoScript)
Write-Host "Installer: $(Join-Path $DistDir 'HamLog-2.0.0-Setup.exe')"
