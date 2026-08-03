# Deploying as a Windows service (NSSM)

The dashboard runs as an always-on Windows service so it survives reboots and
restarts itself if it crashes. We use [NSSM](https://nssm.cc/) (the
"Non-Sucking Service Manager") to wrap the uvicorn process as a service.

Everything below assumes the project lives at its repo root (e.g.
`D:\VisualStudioCodeWrkSpce\FamilyDashboard`) with a working virtualenv in
`.venv\` and a filled-in `.env`. If you can run the dev server
(`python -m uvicorn app.main:app`) and see the dashboard, you're ready.

## 1. One-time prerequisites

1. **Virtualenv + dependencies**, if not already done:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
2. **`.env` configured** — copy `.env.example` to `.env` and fill in your feeds
   and location. The service reads this from the repo root; see the note below.
3. **NSSM** — download the zip from <https://nssm.cc/download>, and either:
   - drop `nssm.exe` (the 64-bit one, from `win64\`) into `scripts\` next to the
     install script, **or**
   - put it anywhere on your `PATH`, **or**
   - pass its full path to the installer with `-Nssm C:\path\to\nssm.exe`.

## 2. Install

Open **PowerShell as Administrator**, `cd` to the project root, then:

```powershell
.\scripts\install-service.ps1
```

That's it. The script is idempotent — re-run it any time to apply changes (it
stops, reconfigures, and restarts the service). Useful switches:

| Switch | Default | Purpose |
|---|---|---|
| `-Port <n>` | `8000` | Port to serve on (updates the firewall rule too). |
| `-BindHost <ip>` | `0.0.0.0` | Interface to bind; `0.0.0.0` = all (needed for the LAN). |
| `-ServiceName <name>` | `FamilyDashboard` | Windows service name. |
| `-Nssm <path>` | auto-detect | Explicit path to `nssm.exe`. |
| `-SkipFirewall` | off | Don't touch Windows Firewall. |
| `-NoStart` | off | Configure but don't start yet. |

When it finishes it prints the dashboard and admin URLs and the log location.

### What it configures (and why)

- **`AppDirectory` = repo root.** `config.py` calls `load_dotenv()` with no path,
  so it reads `.env` relative to the working directory. If the service ran from
  anywhere else it would boot on built-in defaults and **silently ignore your
  `.env`** — no feeds, wrong location. This is the single most important setting.
- **`Application` = `.venv\Scripts\python.exe`**, `AppParameters` =
  `-m uvicorn app.main:app --host 0.0.0.0 --port 8000`. No `--reload`, single
  process — APScheduler runs *inside* this process, so a second worker would
  double every scheduled fetch.
- **Start = auto (at boot).**
- **Restart on exit**, with a 2 s delay and a 5 s throttle so a crash-on-boot
  can't spin into a tight restart loop.
- **Logs** → `data\logs\dashboard.out.log` and `dashboard.err.log`, rotated
  daily or at 10 MB. (`data\` is git-ignored, so logs never get committed.)

  There are **two independent log streams**, both under `data\logs\`:
  - `dashboard.log` — the **app's own** rotating log (startup, fetch results,
    admin actions), rolled at local midnight, keeping `LOG_RETENTION_DAYS` past
    days. This is what the **/admin** page shows and lets you download, and it's
    written whether you run the dev server or the service. Configure it with
    `LOG_DIR` / `LOG_LEVEL` / `LOG_RETENTION_DAYS` in `.env`.
  - `dashboard.out.log` / `dashboard.err.log` — NSSM's capture of the process's
    raw stdout/stderr, a backstop for anything printed *outside* the logger (e.g.
    a hard crash before logging is set up). Service-only.
- **Firewall** → an inbound "allow TCP `<port>`" rule on the Private/Domain
  profiles, so the Pi and other LAN devices can reach it.

## 3. Verify

```powershell
nssm status FamilyDashboard          # -> SERVICE_RUNNING
Invoke-RestMethod http://localhost:8000/healthz   # -> status = ok
```

Then browse from another device on the LAN to `http://<server-ip>:8000/` (the
wall display) and `http://<server-ip>:8000/admin` (feed health + manual refresh).
Find `<server-ip>` with `ipconfig`.

## 4. Day-to-day operations

```powershell
# Start / stop / restart
nssm start   FamilyDashboard
nssm stop    FamilyDashboard
nssm restart FamilyDashboard

# Tail the logs
Get-Content .\data\logs\dashboard.out.log -Tail 50 -Wait
Get-Content .\data\logs\dashboard.err.log -Tail 50 -Wait

# Edit any service setting interactively, then restart
nssm edit FamilyDashboard
```

- **After a code update** (`git pull`): `nssm restart FamilyDashboard`.
- **After a dependency change**: reinstall into the venv, then restart:
  ```powershell
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  nssm restart FamilyDashboard
  ```
- **After editing `.env`**: `nssm restart FamilyDashboard` to pick it up. (The
  Phase 5 admin "Save & restart" button will do exactly this `nssm restart` for
  you once feed-editing lands.)
- **Change the port**: re-run `.\scripts\install-service.ps1 -Port <n>` (it
  updates both the service and the firewall rule).

## 5. Uninstall

```powershell
.\scripts\uninstall-service.ps1
```

Removes the service and its firewall rule. Your code, venv, `.env`, logs, and the
SQLite cache in `data\` are left untouched.

## 6. Manual install (no script)

If you'd rather not use the script, these are the exact equivalents. Run each in
an elevated prompt, from the repo root, substituting real paths:

```powershell
$svc  = "FamilyDashboard"
$root = (Get-Location).Path
$py   = "$root\.venv\Scripts\python.exe"

nssm install $svc $py
nssm set $svc AppParameters "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"
nssm set $svc AppDirectory  $root
nssm set $svc DisplayName   "Family Wall Dashboard"
nssm set $svc Start         SERVICE_AUTO_START
nssm set $svc AppStdout     "$root\data\logs\dashboard.out.log"
nssm set $svc AppStderr     "$root\data\logs\dashboard.err.log"
nssm set $svc AppRotateFiles 1
nssm set $svc AppRotateOnline 1
nssm set $svc AppRotateSeconds 86400
nssm set $svc AppRotateBytes 10485760
nssm set $svc AppExit Default Restart
nssm set $svc AppRestartDelay 2000
nssm set $svc AppThrottle 5000

New-Item -ItemType Directory -Force -Path "$root\data\logs" | Out-Null
New-NetFirewallRule -DisplayName "FamilyDashboard (8000/tcp)" -Direction Inbound `
    -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private,Domain

nssm start $svc
```

## Troubleshooting

- **Service starts then stops immediately.** Read `data\logs\dashboard.err.log`.
  Common causes: the venv is missing a dependency, or the port is already in use.
- **Dashboard shows defaults / no feeds.** `AppDirectory` isn't the repo root, so
  `.env` wasn't found. Re-run the installer, or `nssm set FamilyDashboard
  AppDirectory <repo-root>` and restart.
- **The Pi can't reach it.** Check the firewall rule exists and that the server's
  network is set to **Private** (not Public) in Windows network settings. Confirm
  the server's IP with `ipconfig` and that both devices are on the same subnet.
- **Port already in use.** Something else holds 8000 (maybe a stray dev server).
  Reinstall with `-Port <other>` or free the port.
