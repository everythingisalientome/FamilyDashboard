<#
.SYNOPSIS
  Stop and remove the Family Wall Dashboard Windows service, and its firewall rule.

.DESCRIPTION
  The inverse of install-service.ps1. Leaves the code, venv, .env, logs and the
  SQLite cache in data\ untouched - it only removes the service registration and
  the inbound firewall rule. Run from an ELEVATED PowerShell.

.EXAMPLE
  .\scripts\uninstall-service.ps1
#>
[CmdletBinding()]
param(
    [string]$ServiceName = "FamilyDashboard",
    [int]$Port = 8000,
    [string]$Nssm = ""
)

$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this in an elevated PowerShell (Run as Administrator) - removing a Windows service needs admin rights."
}

if (-not $Nssm) {
    $cmd = Get-Command nssm -ErrorAction SilentlyContinue
    if ($cmd) {
        $Nssm = $cmd.Source
    } elseif (Test-Path (Join-Path $PSScriptRoot "nssm.exe")) {
        $Nssm = Join-Path $PSScriptRoot "nssm.exe"
    } else {
        throw "nssm.exe not found. Put it at scripts\nssm.exe, on PATH, or pass -Nssm <path>."
    }
}

& $Nssm status $ServiceName *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Service '$ServiceName' is not installed - nothing to remove."
} else {
    Write-Host "Stopping '$ServiceName'."
    & $Nssm stop $ServiceName *> $null       # fine if already stopped
    # 'confirm' removes without the interactive prompt.
    & $Nssm remove $ServiceName confirm
    if ($LASTEXITCODE -ne 0) { throw "nssm remove failed (exit $LASTEXITCODE)" }
    Write-Host "Removed service '$ServiceName'."
}

$ruleName = "FamilyDashboard ($Port/tcp)"
$rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($rule) {
    $rule | Remove-NetFirewallRule
    Write-Host "Removed firewall rule '$ruleName'."
}
