$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$packRoot = Join-Path $projectRoot '.packaging\windows'
New-Item -ItemType Directory -Path $packRoot -Force | Out-Null
Push-Location $packRoot
try {
    # flet pack clears ./build; run in an isolated directory to preserve APK work.
    & (Join-Path $projectRoot '.venv\Scripts\flet.exe') pack `
        (Join-Path $projectRoot 'src\main.py') `
        --name QRGenerator --onedir --yes `
        --icon (Join-Path $projectRoot 'src\assets\icon.ico') `
        --add-data "$(Join-Path $projectRoot 'src\assets'):assets" `
            "$(Join-Path $projectRoot '.venv\Lib\site-packages\flet_web\web'):flet_web/web" `
        --distpath (Join-Path $packRoot 'dist') `
        --product-name 'QR Generator' --product-version 1.1.2 `
        --file-version 1.1.2.0 --company-name 'Jirawat Pratuangtip'
    if ($LASTEXITCODE -ne 0) { throw 'Windows packaging failed.' }
    $releaseRoot = Join-Path $projectRoot 'dist'
    New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $packRoot 'dist\QRGenerator') -Destination $releaseRoot -Recurse -Force
} finally {
    Pop-Location
}
