<#
.SYNOPSIS
  Install (or reconfigure) the Family Wall Dashboard as a Windows service via NSSM.

.DESCRIPTION
  Runs uvicorn from the project's virtualenv as an auto-starting Windows service.
  Re-running is safe: an existing service is stopped, reconfigured, and started
  again (so this doubles as "apply new settings"). Configures, specifically:
    - AppDirectory = repo root, so config.py's load_dotenv() finds .env. Without
      this the service boots on defaults and silently ignores your .env.
    - Auto-start at boot, auto-restart on crash (throttled against crash loops).
    - stdout/stderr captured to data\logs\ with daily + size-based rotation.
    - An inbound firewall rule so the Pi (and any LAN browser) can reach the port.

  Run from an ELEVATED PowerShell (installing a service needs admin rights).

.EXAMPLE
  # From an elevated PowerShell, in the project root:
  .\scripts\install-service.ps1

.EXAMPLE
  .\scripts\install-service.ps1 -Port 8080 -Nssm C:\tools\nssm.exe
#>
[CmdletBinding()]
param(
    [string]$ServiceName = "FamilyDashboard",
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [string]$Nssm = "",          # path to nssm.exe; auto-detected when empty
    [switch]$SkipFirewall,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"

# --- Require elevation -----------------------------------------------------
$principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this in an elevated PowerShell (Run as Administrator) - installing a Windows service needs admin rights."
}

# --- Locate repo root + venv Python ----------------------------------------
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Venv Python not found at $python`nCreate it first:`n  python -m venv .venv`n  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

# --- Locate nssm.exe -------------------------------------------------------
if (-not $Nssm) {
    $cmd = Get-Command nssm -ErrorAction SilentlyContinue
    if ($cmd) {
        $Nssm = $cmd.Source
    } elseif (Test-Path (Join-Path $PSScriptRoot "nssm.exe")) {
        $Nssm = Join-Path $PSScriptRoot "nssm.exe"
    } else {
        throw "nssm.exe not found. Download it from https://nssm.cc/download, then either put nssm.exe next to this script (scripts\nssm.exe), add it to PATH, or pass -Nssm <path>."
    }
}

function Invoke-Nssm {
    param([Parameter(ValueFromRemainingArguments = $true)]$Args)
    & $Nssm @Args
    if ($LASTEXITCODE -ne 0) { throw "nssm $($Args -join ' ') failed (exit $LASTEXITCODE)" }
}

function Wait-ServiceRunning {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
        if (-not $service) {
            Start-Sleep -Milliseconds 300
            continue
        }
        if ($service.Status -eq [System.ServiceProcess.ServiceControllerStatus]::Running) {
            return $true
        }
        if ($service.Status -eq [System.ServiceProcess.ServiceControllerStatus]::Stopped) {
            return $false
        }
        Start-Sleep -Milliseconds 500
    }

    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    return ($service -and $service.Status -eq [System.ServiceProcess.ServiceControllerStatus]::Running)
}

# --- Ensure the log directory ----------------------------------------------
$logDir = Join-Path $repoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$outLog = Join-Path $logDir "dashboard.out.log"
$errLog = Join-Path $logDir "dashboard.err.log"

$appParams = "-m uvicorn app.main:app --host $BindHost --port $Port"

# --- Install or reconfigure ------------------------------------------------
& $Nssm status $ServiceName *> $null
$exists = ($LASTEXITCODE -eq 0)

if ($exists) {
    Write-Host "Service '$ServiceName' already exists - stopping to reconfigure."
    & $Nssm stop $ServiceName *> $null    # fine if it was already stopped
} else {
    Write-Host "Installing service '$ServiceName'."
    Invoke-Nssm install $ServiceName $python
}

Invoke-Nssm set $ServiceName Application $python
Invoke-Nssm set $ServiceName AppParameters $appParams
Invoke-Nssm set $ServiceName AppDirectory $repoRoot
Invoke-Nssm set $ServiceName DisplayName "Family Wall Dashboard"
Invoke-Nssm set $ServiceName Description "Serves the family wall dashboard (FastAPI/uvicorn) and runs its scheduled fetch jobs."
Invoke-Nssm set $ServiceName Start SERVICE_AUTO_START

# Logs: append to a rotating file, roll daily or at 10 MB.
Invoke-Nssm set $ServiceName AppStdout $outLog
Invoke-Nssm set $ServiceName AppStderr $errLog
Invoke-Nssm set $ServiceName AppRotateFiles 1
Invoke-Nssm set $ServiceName AppRotateOnline 1
Invoke-Nssm set $ServiceName AppRotateSeconds 86400
Invoke-Nssm set $ServiceName AppRotateBytes 10485760

# Crash handling: restart, but throttle so a boot-failure can't spin the CPU.
Invoke-Nssm set $ServiceName AppExit Default Restart
Invoke-Nssm set $ServiceName AppRestartDelay 2000
Invoke-Nssm set $ServiceName AppThrottle 5000

# --- Firewall: let the LAN (and the Pi) reach the port ---------------------
if (-not $SkipFirewall) {
    $ruleName = "FamilyDashboard ($Port/tcp)"
    Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow `
        -Protocol TCP -LocalPort $Port -Profile Private, Domain | Out-Null
    Write-Host "Firewall: allowed inbound TCP $Port (Private/Domain profiles)."
    Write-Host "  If the Pi still can't connect, confirm this network is set to 'Private', not 'Public'."
}

# --- Start -----------------------------------------------------------------
if ($NoStart) {
    Write-Host "Configured but not started (-NoStart). Start it with: nssm start $ServiceName"
} else {
    & $Nssm start $ServiceName *> $null
    if ($LASTEXITCODE -ne 0) {
        if (-not (Wait-ServiceRunning -Name $ServiceName -TimeoutSeconds 30)) {
            throw "nssm start $ServiceName failed (exit $LASTEXITCODE)"
        }
        Write-Host "Service reached RUNNING despite non-zero nssm start exit code; continuing."
    } elseif (-not (Wait-ServiceRunning -Name $ServiceName -TimeoutSeconds 30)) {
        throw "Service '$ServiceName' did not reach RUNNING within timeout."
    }

    $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "169.*" -and $_.IPAddress -ne "127.0.0.1" } |
        Select-Object -First 1 -ExpandProperty IPAddress)
    if (-not $ip) { $ip = "<this-machine-ip>" }
    Write-Host ""
    Write-Host "Started '$ServiceName'."
    Write-Host "  Dashboard : http://${ip}:$Port/"
    Write-Host "  Admin     : http://${ip}:$Port/admin"
    Write-Host "  Logs      : $logDir"
}
