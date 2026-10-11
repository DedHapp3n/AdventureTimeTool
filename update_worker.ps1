param(
    [Parameter(Mandatory=$true)][int]$ParentPid,
    [Parameter(Mandatory=$true)][string]$Payload,
    [Parameter(Mandatory=$true)][string]$InstallDir,
    [switch]$SkipRestart
)

$ErrorActionPreference = 'Stop'
$payloadRoot = (Resolve-Path -LiteralPath $Payload).Path
$installRoot = (Resolve-Path -LiteralPath $InstallDir).Path
$stageRoot = Split-Path -Parent $payloadRoot
$logFile = Join-Path $stageRoot 'updater.log'

try {
    if (-not (Test-Path -LiteralPath (Join-Path $payloadRoot 'AdventureTimeTool.exe') -PathType Leaf)) { throw 'Missing application executable' }
    if (-not (Test-Path -LiteralPath (Join-Path $payloadRoot '_internal') -PathType Container)) { throw 'Missing _internal directory' }
    if (-not $payloadRoot.StartsWith((Join-Path $installRoot 'data') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Payload must be staged under data' }

    $deadline = (Get-Date).AddMinutes(2)
    while (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {
        if ((Get-Date) -ge $deadline) { throw 'Application did not exit' }
        Start-Sleep -Milliseconds 500
    }

    $protected = @('data', 'texturepacks')
    $entries = @(Get-ChildItem -LiteralPath $payloadRoot -Force)
    foreach ($entry in $entries) {
        if ($protected -contains $entry.Name.ToLowerInvariant()) { throw "Protected entry in payload: $($entry.Name)" }
        if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse point in payload' }
        if ($entry.Name -in @('.', '..') -or $entry.Name.Contains('/') -or $entry.Name.Contains('\') -or $entry.Name.Contains(':')) { throw 'Invalid destination name' }
    }

    $backup = Join-Path $stageRoot 'backup'
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    $installed = @()
    $backedUp = @()
    try {
        foreach ($entry in $entries) {
            $destination = Join-Path $installRoot $entry.Name
            if (Test-Path -LiteralPath $destination) {
                $old = Join-Path $backup $entry.Name
                Move-Item -LiteralPath $destination -Destination $old -ErrorAction Stop
                $backedUp += $entry.Name
            }
            $installed += $entry.Name
            Copy-Item -LiteralPath $entry.FullName -Destination $destination -Recurse -Force -ErrorAction Stop
        }
    } catch {
        foreach ($name in $installed) {
            $destination = Join-Path $installRoot $name
            if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Recurse -Force }
        }
        foreach ($name in $backedUp) {
            $old = Join-Path $backup $name
            if (Test-Path -LiteralPath $old) { Move-Item -LiteralPath $old -Destination (Join-Path $installRoot $name) -Force }
        }
        throw
    }
    if (-not $SkipRestart) {
        Start-Process -FilePath (Join-Path $installRoot 'AdventureTimeTool.exe') -WorkingDirectory $installRoot
    }
    'Update installed successfully' | Set-Content -LiteralPath $logFile
} catch {
    $_ | Out-String | Set-Content -LiteralPath $logFile
    exit 1
}
