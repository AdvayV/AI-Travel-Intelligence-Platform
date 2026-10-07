param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(1, 2)]
    [int]$Version,
    [int]$StartupTimeoutSeconds = 300
)

$ErrorActionPreference = 'Stop'
$processEnvironment = [Environment]::GetEnvironmentVariables('Process')
$pathKeys = @($processEnvironment.Keys | Where-Object { $_ -ieq 'Path' })
if ($pathKeys.Count -gt 1) {
    $combinedPath = ($pathKeys | ForEach-Object { $processEnvironment[$_] } | Select-Object -Unique) -join ';'
    foreach ($pathKey in $pathKeys) {
        [Environment]::SetEnvironmentVariable($pathKey, $null, 'Process')
    }
    [Environment]::SetEnvironmentVariable('Path', $combinedPath, 'Process')
}
$workspace = Split-Path -Parent $PSScriptRoot
$projectFolder = if ($Version -eq 1) { 'travelsols' } else { 'travelsolsv2' }
$projectPath = Join-Path $workspace $projectFolder
$backendPort = 7999 + $Version
$frontendPort = 5172 + $Version
$backendUrl = "http://127.0.0.1:$backendPort"
$frontendUrl = "http://127.0.0.1:$frontendPort"
$logFolder = Join-Path $workspace '.startup-logs'
New-Item -ItemType Directory -Path $logFolder -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$env:TRAVELROUTE_NO_PAUSE = '1'

function Test-Endpoint {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Start-ServiceProcess {
    param([string]$Name, [string]$Launcher, [int]$Port, [string]$HealthUrl)

    if (Test-Endpoint $HealthUrl) {
        Write-Host "$Name already responds on port $Port; reusing it."
        return $null
    }
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Port $Port is occupied but $HealthUrl is not ready. Stop the existing process and retry."
    }

    $stdout = Join-Path $logFolder "v$Version-$Name-$stamp.out.log"
    $stderr = Join-Path $logFolder "v$Version-$Name-$stamp.err.log"
    $launcherPath = Join-Path $projectPath $Launcher
    $process = Start-Process -FilePath $env:ComSpec -ArgumentList "/d /c `"`"$launcherPath`"`"" -WorkingDirectory $projectPath -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    Write-Host "Started $Name process $($process.Id). Logs: $stdout"
    return [pscustomobject]@{ Process = $process; Stdout = $stdout; Stderr = $stderr }
}

function Wait-ServiceReady {
    param([string]$Name, [string]$Url, $Service)

    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    $lastNotice = (Get-Date).AddSeconds(-15)
    while ((Get-Date) -lt $deadline) {
        if (Test-Endpoint $Url) {
            Write-Host "$Name ready: $Url"
            return
        }
        if ($Service -and $Service.Process.HasExited) {
            $Service.Process.Refresh()
            Get-Content -LiteralPath $Service.Stdout -Tail 15 -ErrorAction SilentlyContinue | Write-Host
            Get-Content -LiteralPath $Service.Stderr -Tail 15 -ErrorAction SilentlyContinue | Write-Host
            throw "$Name exited with code $($Service.Process.ExitCode). See .startup-logs."
        }
        if (((Get-Date) - $lastNotice).TotalSeconds -ge 15) {
            Write-Host "Waiting for $Name initialization..."
            $lastNotice = Get-Date
        }
        Start-Sleep -Seconds 2
    }
    throw "$Name did not become ready within $StartupTimeoutSeconds seconds. See .startup-logs."
}

try {
    Write-Host "Starting TravelRoute v$Version"
    $backend = Start-ServiceProcess 'backend' 'start_backend.bat' $backendPort "$backendUrl/api/health"
    $frontend = Start-ServiceProcess 'frontend' 'start_frontend.bat' $frontendPort $frontendUrl
    Wait-ServiceReady 'Backend' "$backendUrl/api/health" $backend
    Wait-ServiceReady 'Frontend' $frontendUrl $frontend
    Wait-ServiceReady 'Frontend API proxy' "$frontendUrl/api/health" $frontend
    Write-Host "TravelRoute v$Version is ready. Open $frontendUrl"
    Write-Host "Backend API documentation: $backendUrl/docs"
    Write-Host 'Servers continue running after this launcher closes.'
} catch {
    Write-Host "Startup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
