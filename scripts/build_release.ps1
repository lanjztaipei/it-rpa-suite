$ErrorActionPreference = "Stop"

# 以 $PSScriptRoot 推導專案根目錄，絕不包含任何個人電腦絕對路徑
$ScriptDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path -Path $ScriptDir -ChildPath "..")).Path

# 優先載入本機 .venv\Scripts
$VenvScripts = Join-Path -Path $ProjectRoot -ChildPath ".venv\Scripts"
if (Test-Path -LiteralPath $VenvScripts) {
    $env:PATH = "$VenvScripts;$env:PATH"
}

$SpecFile = Join-Path -Path $ScriptDir -ChildPath "app.spec"
$UpdaterScript = Join-Path -Path $ProjectRoot -ChildPath "tools\updater\updater.py"
$UpdaterDir = Join-Path -Path $ProjectRoot -ChildPath "tools\updater"

$BuildDir = Join-Path -Path $ProjectRoot -ChildPath "build"
$DistDir = Join-Path -Path $ProjectRoot -ChildPath "dist"
$SourceFolder = Join-Path -Path $DistDir -ChildPath "ITRPASuite"

$ReleaseFolder = Join-Path -Path $ProjectRoot -ChildPath "released"
$TargetZip = Join-Path -Path $ReleaseFolder -ChildPath "ITRPASuite.zip"

function Check-ExitCode {
    param(
        [Parameter(Mandatory)]
        [string]$StepName
    )

    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed. ExitCode: $LASTEXITCODE"
    }
}

try {
    Write-Host "Step 1: Check required specification and updater scripts"

    if (-not (Test-Path -LiteralPath $SpecFile -PathType Leaf)) {
        throw "Spec file not found: $SpecFile"
    }

    if (-not (Test-Path -LiteralPath $UpdaterScript -PathType Leaf)) {
        throw "Updater script not found: $UpdaterScript"
    }

    if (-not (Test-Path -LiteralPath $ReleaseFolder -PathType Container)) {
        New-Item -ItemType Directory -Path $ReleaseFolder -Force | Out-Null
    }

    Write-Host "Step 2: Clean old build and dist folders"

    if (Test-Path -LiteralPath $BuildDir) {
        Remove-Item -LiteralPath $BuildDir -Recurse -Force
    }

    if (Test-Path -LiteralPath $DistDir) {
        Remove-Item -LiteralPath $DistDir -Recurse -Force
    }

    Write-Host "Step 3: Build standalone updater.exe (onefile)"

    Push-Location -LiteralPath $ProjectRoot
    try {
        pyinstaller --noconfirm --onefile --console `
            --name updater `
            --distpath $UpdaterDir `
            --workpath (Join-Path -Path $BuildDir -ChildPath "updater_work") `
            --specpath (Join-Path -Path $BuildDir -ChildPath "updater_spec") `
            $UpdaterScript
        Check-ExitCode "PyInstaller (updater.exe)"
    }
    finally {
        Pop-Location
    }

    Write-Host "Step 4: Build ITRPASuite (onedir)"

    Push-Location -LiteralPath $ProjectRoot
    try {
        pyinstaller --noconfirm `
            --distpath $DistDir `
            --workpath $BuildDir `
            $SpecFile
        Check-ExitCode "PyInstaller (ITRPASuite)"
    }
    finally {
        Pop-Location
    }

    Write-Host "Step 5: Verify output folder"

    if (-not (Test-Path -LiteralPath $SourceFolder -PathType Container)) {
        throw "Output folder not found: $SourceFolder"
    }

    Write-Host "Step 6: Create ./released/ITRPASuite.zip (top-level ITRPASuite.exe + _internal/)"

    if (Test-Path -LiteralPath $TargetZip) {
        Remove-Item -LiteralPath $TargetZip -Force
    }

    Compress-Archive `
        -Path (Join-Path -Path $SourceFolder -ChildPath "*") `
        -DestinationPath $TargetZip `
        -Force

    if (-not (Test-Path -LiteralPath $TargetZip -PathType Leaf)) {
        throw "Release zip was not created: $TargetZip"
    }

    $TargetSha256File = "$TargetZip.sha256"
    $ZipHash = (Get-FileHash -LiteralPath $TargetZip -Algorithm SHA256).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText($TargetSha256File, "$ZipHash  ITRPASuite.zip`n")
    Write-Host "Generated SHA-256 checksum: $TargetSha256File"

    Write-Host "Step 7: Clean local build and dist artifacts"

    if (Test-Path -LiteralPath $BuildDir) {
        Remove-Item -LiteralPath $BuildDir -Recurse -Force
    }

    if (Test-Path -LiteralPath $DistDir) {
        Remove-Item -LiteralPath $DistDir -Recurse -Force
    }

    Write-Host "Release package created successfully: $TargetZip" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "Build release failed." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "The build and dist folders were retained for troubleshooting." -ForegroundColor Yellow
    exit 1
}
