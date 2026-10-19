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

- **`AppDirectory` = repo root.** uvicorn imports `app.main` from the working
  directory, so the service can't start from anywhere else. (`.env` itself is
  read from the repo root by absolute path — `app/config/env.py`, overridable
  with `APP_DOTENV_PATH` — so it no longer depends on the working directory.)
- **`Application` = `.venv\Scripts\python.exe`**, `AppParameters` =
  `-m uvicorn app.main:app --host 0.0.0.0 --port 8000`. No `--reload`, single
  process — APScheduler runs *inside* this process, so a second worker would
  double every scheduled fetch.
- **Start = auto (at boot).**
- **`AppEnvironmentExtra FAMILY_WALL_SERVICE=1`.** Tells the admin page it is
  running under NSSM, which enables the **Restart now** button on its "Settings
  saved — restart to apply" banner (it exits the process and NSSM's
  restart-on-exit relaunches it). A dev server lacks the marker, so the button is
  disabled there with a tooltip saying to restart by hand.
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
wall display) and `http://<server-ip>:8000/admin` (tabs: Status · Add events ·
Settings · Logs; `#status`, `#events`, `#settings`, `#logs` link straight to one).
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
- **After editing `.env`**: `nssm restart FamilyDashboard` to pick it up, or
  edit it from the admin page instead (below), which restarts for you.
- **Change the port**: re-run `.\scripts\install-service.ps1 -Port <n>` (it
  updates both the service and the firewall rule).

### Editing settings from `/admin`

The admin page's **Settings** tab edits the same `.env` (no second config
store). It has one sub-tab per `.env.example` section. Values are shown
read-only with their help text; ✎ turns a row into an input, ✓ stages that
one edit and ✕ cancels it. The Calendar feeds and Persons sub-tabs also have
an **Add calendar feed** / **Add person** helper. Each helper stages only its
fixed `CAL_<key>_*` / `PERSON_<key>_*` keys, where `<key>` is lowercase letters
and digits and must not already exist. Each feed or person also has a
**Remove** button. There is no way to type an arbitrary new key.

- **Save** (per sub-tab) dry-runs the change: a fresh Python imports
  `app.config` from the candidate file in strict mode (a bad number, colour,
  URL, `HH:MM` or calendar schedule fails it, and the error is shown inline).
  Only if it passes is the current file copied to
  `data\env-backups\.env.<UTC stamp>` (the last 10 are kept) and `.env`
  replaced atomically. Only the staged keys change; every other line is left
  byte-for-byte. **Revert** drops that sub-tab's staged edits.
- Leaving a sub-tab or the Settings tab with staged edits asks **Save /
  Discard / Stay** in the page, and closing the page warns too.
- The **drift banner** lists `.env.example` keys that `.env` lacks; **Add
  missing keys with defaults** writes them (same dry-run + backup) in one click.
- Whenever `.env` on disk differs from the one the server booted with, a
  banner above the tabs says **Settings saved — restart to apply**. **Restart
  now** exits the process so NSSM relaunches it; the page waits for the new
  process and reloads itself. The wall keeps showing cached data throughout.
  Hand edits to `.env` raise the banner too.

Each save is logged (`dashboard.admin`) with the changed keys; values of
`*_URL` and `GCAL_*` keys are redacted in the log line.

**One-time after upgrading to this version:** re-run
`.\scripts\install-service.ps1` (elevated) once so the service gets the
`FAMILY_WALL_SERVICE=1` marker. Until then **Restart now** stays disabled, so
run `nssm restart FamilyDashboard` yourself after saving.

**If a save ever bricks the config**, restore the newest good backup and
restart:

```powershell
Get-ChildItem data\env-backups -Force | Sort-Object Name   # newest last
Copy-Item data\env-backups\.env.<stamp> .env
nssm restart FamilyDashboard
```

### Updating the wall

After `git pull` on the server, from the repo root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
nssm restart FamilyDashboard
```

Run the `pip install` even when you don't think dependencies changed. Phase 7
pinned `tzdata`, which `zoneinfo` needs on Windows; Phase 4 imports
`google-api-python-client`, `google-auth` and `google-auth-httplib2` for the
family Google Calendar.

#### New `.env` keys on deploy

The deployment `.env` is **separate** from the dev one and is never in git, so
a pull that adds a setting doesn't add it on the server. After every pull,
compare it with `.env.example` and copy over any new keys (this bit us on the
Phase 7 deploy). The admin page's drift banner lists them for you ("Add with
defaults" stages them); the manual check is:

```powershell
# Keys in .env.example that the deployment .env lacks
$have = (Get-Content .env) -replace '=.*' | Where-Object { $_ -match '^[A-Z]' }
(Get-Content .env.example) -replace '=.*' | Where-Object { $_ -match '^[A-Z]' -and $_ -notin $have }
```

Then `nssm restart FamilyDashboard`.

The Pi's kiosk URL doesn't change. `http://<server-ip>:8000/` is now the light
per-person wall (Phase 7). The previous dark wall is still at
**`http://<server-ip>:8000/v1`** if the household wants it back for a day: point
the kiosk at it, or just open it on any screen.

Everything under `static/` — the HTML pages and every `/css`, `/js`, `/fonts`
and `/img` asset — is served with `Cache-Control: no-cache`. The browser
revalidates each file on every load and gets a `304 Not Modified` when it is
unchanged, so on the LAN the cost is a header exchange. A deploy is therefore
live on the next page load (on the wall: the next kiosk launch or the nightly
3 AM self-reload). New HTML can't be paired with stale cached scripts, and no
`?v=` cache-busting is needed. (`/photos` keeps default caching; photo URLs
carry their own `?v=<size>`.)

### Google Calendar (service account)

The family feed (`family`) reads the household Google Calendar through the
Calendar API with a **service account**: no OAuth consent screen, no token
that expires. It is read on the nightly calendar schedule, at boot, and on
`/admin` → refresh *calendars*. One-time setup:

1. **Create the service account.** In the [Google Cloud console](https://console.cloud.google.com/),
   pick (or create) a project, enable the **Google Calendar API**, then
   *IAM & Admin → Service accounts → Create service account* (no roles
   needed). Note its email, `…@….iam.gserviceaccount.com`.
2. **Download a key.** On the service account: *Keys → Add key → Create new
   key → JSON*. Move the file out of Downloads to **`data\gcal-sa.json`** in
   the repo (git-ignored; never under `static\`). Treat it like a password.
3. **Share the calendar with it.** In Google Calendar: *Settings → the family
   calendar → Share with specific people → Add* the service-account email
   with **Make changes to events** (needed later by the importer; reading
   works with it too). The app asks only for the `calendar.events` scope.
4. **Copy the calendar id.** Same settings page → *Integrate calendar* →
   **Calendar ID**. Use that explicit id, never `primary` (for a service
   account `primary` is its own empty calendar).
5. **Set the two `.env` keys:**
   ```ini
   GCAL_CALENDAR_ID=<the calendar id>
   GCAL_SERVICE_ACCOUNT_FILE=data/gcal-sa.json
   ```
   Remove any old `CAL_FAMILY_URL` (it is ignored now and logs a warning).
   Keep `CAL_FAMILY_LABEL/_COLOR/_ORDER`; they still style the feed.
6. **Check it:** `.\.venv\Scripts\python.exe scripts\test_calendar.py` from the repo
   root prints the service-account email and the next 10 events. Add `--write`
   to also insert and immediately delete a test event (proves the share is
   *Make changes to events*).
7. **Restart:** `nssm restart FamilyDashboard`. `/admin` shows an
   `events:family` row with the calendar id as its source.

A failure (key missing, share removed, Google unreachable) shows as an error on
that row; the wall keeps the last good family events.

### Adding events from a photo

For the household: daycare calendars, appointment emails, flyers. It takes
about two minutes from a phone and nobody types dates.

1. **Take a photo** (or a screenshot) of the calendar page or email.
2. **Get the JSON.** Open any chat app (ChatGPT, Claude, Gemini…). Paste the
   prompt from `docs/event-extraction-prompt.md`, fill in today's date and who
   it is for, attach the photo, and send. Copy the JSON it replies with.
3. **On the home Wi-Fi**, open **`http://192.168.0.68:8000/admin`** on the
   phone. *Add events* is at the top.
4. Pick **who it is for**, paste the JSON, tap **Validate**.
5. **Review the list.** Fix a date or title if the photo was misread.
   - *past* rows are unticked; tick one if you want it anyway.
   - *already on calendar* rows are skipped. Pasting the same JSON twice adds
     nothing.
   - Red rows have a problem (shown on the row) and can't be added.
   - A rescheduled appointment shows **"replaces <date> — delete old"**.
     Leave it ticked to remove the old appointment.
6. Tap **Add N events to calendar**. They are in the family Google Calendar
   right away (on everyone's phones), and on the wall within a few minutes.

To undo, delete the event in Google Calendar as usual; the wall follows on its
next refresh. The importer only ever deletes events it created itself.

Events whose title contains an `EVENT_EXCLUDE_KEYWORDS` phrase (board
meetings, bond forums…) never show on the wall. Edit that line in `.env` and
restart to change what is hidden; nothing needs refetching.

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
nssm set $svc AppEnvironmentExtra FAMILY_WALL_SERVICE=1
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

## 7. Pi kiosk (the wall display)

The Pi's only job is to open one URL full-screen. Nothing from this repo runs on
it. This is what worked on a **Raspberry Pi 3 B+ running Raspberry Pi OS Trixie**
(desktop image), whose session is **labwc (Wayland)** — so the kiosk lives in
labwc's autostart, not the old X11/LXDE files.

**Flash a clean card (removes DAKBoard / any prior OS).** With Raspberry Pi
Imager (<https://www.raspberrypi.com/software/>): choose *Raspberry Pi OS (with
desktop)*, then **Edit Settings** before writing and set — hostname (e.g.
`familywall`), a **username + password you choose**, **enable SSH** (password
auth), and your **WiFi** SSID/password + country. This guarantees SSH access on
first boot with known credentials; no keyboard/monitor needed.

**First boot, then SSH in** (hostname avoids needing to know the DHCP IP):
```bash
ssh pi@familywall.local
curl -sI http://<server-ip>:8000/ | head -1     # expect HTTP/1.1 200 OK
```

**Auto-login to the desktop and stop screen blanking:**
```bash
sudo raspi-config nonint do_boot_behaviour B4    # desktop autologin
sudo raspi-config nonint do_blanking 1           # disable screen blank
```

**Create the kiosk autostart.** The file is `~/.config/labwc/autostart`, and its
Chromium line must be **one unbroken line** ending in the URL:
```bash
#!/bin/bash
while true; do
  chromium --kiosk --noerrdialogs --disable-infobars --no-first-run --disable-session-crashed-bubble --disable-features=Translate --password-store=basic --ozone-platform=wayland "http://<server-ip>:8000/"
  sleep 5
done &
```
- The `while … sleep 5 … done &` loop relaunches Chromium if it ever exits (power
  blip), so the wall self-heals.
- `--password-store=basic` avoids the GNOME-keyring "unlock" prompt.
- `--ozone-platform=wayland` runs Chromium natively under labwc.

> **Paste gotcha (this bit us):** SSH terminals often mangle a paste — indenting
> lines (which breaks a heredoc's closing `EOF`) or inserting newlines into a long
> line (which split the `chromium` command off from its URL, so it opened the
> default page). The reliable way to write the file is to edit it in `nano`, or
> pipe a base64 blob (whitespace-tolerant):
> `echo '<base64-of-the-file>' | base64 -d > ~/.config/labwc/autostart`.
> Always `cat` the file afterward and confirm the URL is on the same line as
> `chromium`.

```bash
chmod +x ~/.config/labwc/autostart
sudo reboot
```

After reboot it auto-logs in and opens the dashboard full-screen. If a keyring
dialog still appears, `rm -rf ~/.local/share/keyrings` and reboot once. Detach the
mouse for the final install so no cursor shows (Wayland has no simple
`unclutter`).

### Nightly Chromium restart

The page reloads itself at 3 AM (`NIGHTLY_RELOAD_HOUR`), but a reload does not
give back the memory the Chromium process has grown over days; on a Pi 3 B+ with
1 GB that matters. So once a night, kill Chromium and let the autostart loop
above relaunch it 5 seconds later with a fresh process. In the Pi's **user**
crontab (`crontab -e` as the kiosk user, not root):
```text
5 3 * * * /usr/bin/pkill -f chromium
```
3:05 is after the page's own 3:00 reload and in the middle of night mode, so
nobody sees the 5-second gap. Cron runs on the Pi's own clock, so confirm its
timezone is the household's:
```bash
timedatectl                                          # "Time zone: America/New_York (EDT, -0400)"
sudo timedatectl set-timezone America/New_York      # only if it is not
```
Installed on the wall Pi (`familywall`) as of 2026-10-19.

## Troubleshooting

- **Service starts then stops immediately.** Read `data\logs\dashboard.err.log`.
  Common causes: the venv is missing a dependency, or the port is already in use.
- **Dashboard shows defaults / no feeds.** `.env` is missing from the repo root
  (or `APP_DOTENV_PATH` points elsewhere), or a value is unparseable and fell
  back to its default. To find a bad value, open `/admin` → Settings, stage
  any harmless change and Save. The dry-run checks the whole file, not just the
  changed key, so it names the bad value and writes nothing. A bad save can be
  undone from `data\env-backups\`.
- **The Pi can't reach it.** Check the firewall rule exists and that the server's
  network is set to **Private** (not Public) in Windows network settings. Confirm
  the server's IP with `ipconfig` and that both devices are on the same subnet.
- **Port already in use.** Something else holds 8000 (maybe a stray dev server).
  Reinstall with `-Port <other>` or free the port.
