param([switch]$PrepareOnly)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
$uvVersion = '0.13.10'
$archiveHash = '297b3881fe1adfb922becc2c1613202abb41dc83ea5ff43d472aa087ca1f8683'

try {
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw 'QR Generator requires 64-bit Windows.'
    }
    # Per-user tools; no administrator rights, registry changes or PATH edits.
    $tools = Join-Path $env:LOCALAPPDATA "QRGenerator\tools\uv-$uvVersion"
    $uv = Join-Path $tools 'uv.exe'
    if (-not (Test-Path -LiteralPath $uv -PathType Leaf)) {
        Write-Host 'Installing the Python setup tool (first run only)...'
        New-Item -ItemType Directory -Force -Path $tools | Out-Null
        $staging = Join-Path $tools ([Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $staging | Out-Null
        $archive = Join-Path $staging 'uv.zip'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/astral-sh/uv/releases/download/$uvVersion/uv-x86_64-pc-windows-msvc.zip" -OutFile $archive
        $stream = [IO.File]::OpenRead($archive)
        $hasher = [Security.Cryptography.SHA256]::Create()
        try { $actualHash = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
        finally { $stream.Dispose(); $hasher.Dispose() }
        if ($actualHash -ne $archiveHash) {
            throw 'Setup download checksum mismatch. Please retry; the download was not run.'
        }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead($archive)
        $unpacked = Join-Path $staging 'uv.exe'
        try {
            $entry = $zip.GetEntry('uv.exe')
            if ($null -eq $entry) { throw 'Setup archive does not contain uv.exe.' }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $unpacked)
        } finally { $zip.Dispose() }
        # Publish a complete executable only after archive verification/extraction.
        try { [IO.File]::Move($unpacked, $uv) }
        catch {
            if (-not (Test-Path -LiteralPath $uv -PathType Leaf)) { throw }
            # Another simultaneous first launch published the same version.
            [IO.File]::Delete($unpacked)
        }
        Remove-Item -LiteralPath $archive
        [IO.Directory]::Delete($staging)
    }
    Set-Location -LiteralPath $root
    $python = Join-Path $root '.python-env\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        Write-Host 'Preparing Python 3.13 (downloaded automatically if needed)...'
        & $uv --no-config venv --python 3.13 (Join-Path $root '.python-env')
        if ($LASTEXITCODE -ne 0) { throw 'Python setup failed. Check internet access and folder permissions, then retry run.bat.' }
    }
    Write-Host 'Checking and installing application dependencies...'
    & $uv --no-config pip install --python $python -r (Join-Path $root 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check internet access, then retry run.bat.' }
    & $uv --no-config pip check --python $python
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Repairing incomplete dependencies...'
        & $uv --no-config pip install --reinstall --python $python -r (Join-Path $root 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Dependency repair failed. Please retry run.bat.' }
        & $uv --no-config pip check --python $python
        if ($LASTEXITCODE -ne 0) { throw 'Dependencies are still inconsistent. Please see the setup output above.' }
    }
    if ($PrepareOnly) { Write-Host 'Ready. Open run.bat to start QR Generator.'; exit 0 }
    Write-Host 'Starting QR Generator using Python...'
    & $python (Join-Path $root 'src\main.py')
    exit $LASTEXITCODE
} catch {
    [Console]::Error.WriteLine("QR Generator setup/start failed: $($_.Exception.Message)")
    [Console]::Error.WriteLine($_.ScriptStackTrace)
    exit 1
}
