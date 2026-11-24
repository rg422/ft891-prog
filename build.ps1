# Builds a single-file Windows executable: dist\FT891Programmer.exe
#
#   .\build.ps1            # create/refresh .venv, run tests, build
#   .\build.ps1 -SkipTests
#
# Output: dist\FT891Programmer.exe and dist\FT891Programmer-v<version>-win64.zip

param([switch]$SkipTests)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment (.venv)..."
    Invoke-Checked "python" @("-m", "venv", ".venv")
}
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Invoke-Checked $py @("-m", "pip", "install", "--quiet", "--upgrade", "pip")
Invoke-Checked $py @("-m", "pip", "install", "--quiet", "-r", "requirements.txt", "-r", "requirements-dev.txt")

if (-not $SkipTests) {
    Write-Host "Running tests..."
    Invoke-Checked $py @("-m", "pytest", "-q")
}

$version = (& $py -c "import ft891prog; print(ft891prog.__version__)").Trim()
Write-Host "Building FT891Programmer $version ..."

Invoke-Checked $py @(
    "-m", "PyInstaller",
    "--noconfirm", "--clean",
    "--onefile", "--windowed",
    "--name", "FT891Programmer",
    "--icon", "assets\ft891.ico",
    "--add-data", "assets\ft891.ico;assets",
    "run_ft891prog.py"
)

$zip = "dist\FT891Programmer-v$version-win64.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "dist\FT891Programmer.exe", "README.md" -DestinationPath $zip

Write-Host ""
Write-Host "Done:"
Write-Host "  dist\FT891Programmer.exe"
Write-Host "  $zip"
