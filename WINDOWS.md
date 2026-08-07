# Running FleetPulse on Windows

**Project:** FleetPulse — Transportation Monitoring System
**Student:** Hafsa Aqeel · **Roll Number:** 53317

Two ways to run it. **Route A (Docker) is strongly recommended** — one command, nothing to
install but Docker Desktop. Route B runs it natively if Docker is unavailable on the machine.

Every command below is for **PowerShell**. Open it with `Win` → type `powershell` → Enter.
Do not use the old `cmd.exe`; some commands differ.

---

## Before you start — the one Windows-specific trap

Git for Windows converts text files to Windows line endings (CRLF) on checkout. That is fatal
for `docker/entrypoint.sh`: Linux inside the container reads the trailing carriage return as
part of the filename and fails with the famously unhelpful

```
exec /usr/local/bin/entrypoint.sh: no such file or directory
```

**The repository now contains a `.gitattributes` that prevents this**, so a fresh clone is
safe. You only need the fix below if you are using an older copy of the project, or if you
hit that error.

<details>
<summary>Fix if you hit the CRLF error</summary>

```powershell
git config --global core.autocrlf input
git rm --cached -r .
git reset --hard
docker compose build --no-cache
```

Or, without git, convert the one file in place:

```powershell
$p = "docker\entrypoint.sh"
$t = [IO.File]::ReadAllText($p).Replace("`r`n", "`n")
[IO.File]::WriteAllText($p, $t)
```
</details>

If you copied the project to Windows on a **USB stick or as a ZIP** rather than cloning it,
line endings are preserved as-is and nothing needs fixing.

---

# Route A — Docker (recommended)

## A1. Install Docker Desktop

1. Download **Docker Desktop for Windows** from <https://www.docker.com/products/docker-desktop/>
2. Run the installer and keep **"Use WSL 2 instead of Hyper-V"** ticked.
3. Restart when prompted. If Windows asks to install the **WSL 2 kernel update**, accept it.
4. Launch Docker Desktop and wait for the whale icon in the system tray to stop animating —
   it must read **"Engine running"** before you continue.

Verify:

```powershell
docker --version
docker compose version
docker info
```

All three must succeed. If `docker info` reports a pipe or daemon error, Docker Desktop has
not finished starting.

## A2. Get to the project folder

```powershell
cd C:\path\to\hafsa-gen-ai-final
dir
```

You should see `Dockerfile`, `docker-compose.yml`, `backend`, `frontend`, `docs`.

## A3. Build and run — one command

```powershell
docker compose --profile sim up --build
```

The first build takes **3–6 minutes** (it downloads Node and Python base images and installs
dependencies). Later runs start in seconds.

You will see, in order:

```
fleetpulse-api        | INFO: seeded 3 routes, 12 vehicles, 8 deliveries
fleetpulse-api        | INFO: offline sweeper started (every 20s)
fleetpulse-api        | INFO: Uvicorn running on http://0.0.0.0:8000
fleetpulse-simulator  | waiting for http://api:8000 ...
fleetpulse-simulator  | API is up
fleetpulse-simulator  | tick 1  sent 12  accepted 12  new alerts 0  (total 0)
```

## A4. Open the dashboard

```powershell
start http://localhost:8000
```

Leave the PowerShell window open — closing it stops the containers.

## A5. Watch the alerts appear

Faults ramp rather than jumping, so you watch each value climb through its threshold:

| Time | What appears |
|---|---|
| ~5 s | All 12 vehicles turn from `offline` to `ok` and start moving |
| ~50 s | `ENGINE_OVERHEAT` **warning** on BUS-03 |
| ~60 s | `ROUTE_DEVIATION` on BUS-05 · `CARGO_TEMP_EXCURSION` on TRK-01 |
| ~90 s | BUS-03 escalates to **critical** · `LOW_FUEL` on BUS-02 |
| ~2.5 min | `VEHICLE_OFFLINE` on BUS-07, raised by the background sweeper |

Expect **five alerts from five armed faults** — the other seven vehicles stay green.

## A6. Stop it

Press `Ctrl+C` in the PowerShell window, then:

```powershell
docker compose --profile sim down       # stop, keep the database
docker compose --profile sim down -v    # stop and wipe the database (clean re-demo)
```

## A7. Run the tests inside the container

```powershell
docker compose run --rm tests
```

Expect **290 passed**, with the coverage table printed underneath.

---

# Route B — Native install (no Docker)

Use this only if Docker Desktop cannot be installed (some lab machines block it).

## B1. Install Python 3.11+

Download from <https://www.python.org/downloads/windows/>.
**Tick "Add python.exe to PATH" on the first installer screen** — this is the single most
common cause of "python is not recognized" later.

```powershell
python --version
```

## B2. Install Node.js 18+

Download the **LTS** installer from <https://nodejs.org/>. Accept the defaults.

```powershell
node --version
npm --version
```

Close and reopen PowerShell after installing, so the new PATH is picked up.

## B3. Create the virtual environment

```powershell
cd C:\path\to\hafsa-gen-ai-final
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell refuses with *"running scripts is disabled on this system"*:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

That only affects the current window. Your prompt should now start with `(.venv)`.

## B4. Install dependencies

```powershell
pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
```

## B5. Create the demo data

```powershell
cd backend
python -m app.seed --reset
```

Expected: `seeded 3 routes, 12 vehicles, 8 deliveries`

## B6. Run — three PowerShell windows

**Window 1 — API** (activate the venv first)

```powershell
cd C:\path\to\hafsa-gen-ai-final
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --reload
```

**Window 2 — dashboard**

```powershell
cd C:\path\to\hafsa-gen-ai-final\frontend
npm run dev
```

**Window 3 — simulator** (activate the venv first)

```powershell
cd C:\path\to\hafsa-gen-ai-final
.\.venv\Scripts\Activate.ps1
cd backend
python -m app.simulate --scenario BUS-03=overheat --scenario TRK-01=cargo_spike --scenario BUS-05=deviation --scenario BUS-07=dropout --scenario BUS-02=fuel_drain
```

> **PowerShell note:** the backslash `\` used to split long commands across lines in Linux
> guides does **not** work here. Either keep the command on one line as above, or use a
> backtick `` ` `` at the end of each line.

Then open:

```powershell
start http://localhost:5173
```

Note the port: **5173** for the native route (Vite dev server), **8000** for Docker.

## B7. Run the tests

```powershell
cd C:\path\to\hafsa-gen-ai-final\backend
.\..\.venv\Scripts\Activate.ps1
pytest
```

Expect **290 passed**.

---

## Checking the API from PowerShell

⚠️ In PowerShell, `curl` is an **alias for `Invoke-WebRequest`** and takes different
arguments, so Linux-style `curl` commands from the other docs will fail. Use either:

```powershell
curl.exe http://localhost:8000/api/health
```

or the native cmdlet, which pretty-prints JSON:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod "http://localhost:8000/api/alerts?limit=10" | Select-Object -Expand items |
    Format-Table vehicle_code, rule_code, severity, occurrences
```

Useful endpoints:

| URL | What it shows |
|---|---|
| <http://localhost:8000> | The dashboard (Docker route) |
| <http://localhost:8000/docs> | Interactive Swagger API explorer |
| <http://localhost:8000/api/health> | Service health and counters |
| <http://localhost:8000/api/fleet/snapshot> | Every vehicle's live state |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `exec /usr/local/bin/entrypoint.sh: no such file or directory` | CRLF line endings from Git for Windows | See **the trap** at the top of this file |
| `docker: error during connect` / pipe error | Docker Desktop not running | Start Docker Desktop, wait for "Engine running" |
| `Ports are not available: 0.0.0.0:8000` | Something already uses port 8000 | `netstat -ano \| findstr :8000` to find the PID, or change the mapping in `docker-compose.yml` to `"8080:8000"` and use port 8080 |
| `python is not recognized` | Python not on PATH | Reinstall Python with "Add python.exe to PATH" ticked |
| `running scripts is disabled on this system` | PowerShell execution policy | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `npm is not recognized` | PATH not refreshed | Close and reopen PowerShell after installing Node |
| Dashboard loads but nothing moves | Simulator not running | Docker: use `--profile sim`. Native: start window 3 |
| Dashboard says "polling (ws down)" | API restarting, or a proxy blocking WebSockets | It keeps working via polling; it reconnects on its own |
| Every bus shows `SCHEDULE_DELAY` at once | Stale database from an older build | `docker compose down -v` then start again |
| WSL 2 installation errors | Virtualisation disabled in BIOS | Enable Intel VT-x / AMD-V in BIOS, or use Route B |
| Build very slow the first time | Downloading base images | Normal — 3–6 minutes once, seconds thereafter |

---

## Which route for the demonstration?

**Use Route A (Docker).** One command, one URL, no chance of a missing dependency in front of
an examiner, and the dashboard and API share a single port. Route B is a fallback and needs
three windows and two ports.

Whichever you use, do a **full dry run on the actual machine** before the demonstration —
including the first Docker build, which is the slow part.

Full demonstration script: `docs/11-demo-script.md`.
Docker detail and a verified run: `docs/12-docker-guide.md`.
