# Berth — product notes

A berth roll is the list of who is present and who is missing. That is the whole
product: **what the machine is running on which port, and what your repos said should
be running but isn't.**

Panel name: `berth` · repo: `herdr-berth` · key: `cmd-shift-o`.

---

## 1. The problem

Local development is a pile of long-lived processes nobody owns any more:

- A dev server on `:3000` started three days ago, still holding the port; the new one
  silently moved to `:3001`.
- Six Supabase containers with published ports you cannot remember, and four more with
  no published port at all, which is why the browser shows nothing.
- macOS daemons squatting the interesting ports: AirPlay Receiver on `:5000`, `:7000`;
  `rapportd` on `:56202`; Spotify, Sonos, VS Code language servers.
- Two microservices that failed to start *because* the port was taken, so the failure
  never shows up anywhere except one scrolled-away terminal.

`lsof` answers "who holds :3000" if you already know to ask. Nothing answers:

> "Which of my projects is running, on which ports, and what did I forget to start?"

## 2. Who it is for

A developer running several services across several repos on one laptop — the Herdr
target user, exactly: parallel agent sessions, multiple repos, docker for infra, a
browser open on half of it.

The job to be done, in one sentence: *when I come back to a repo after a day, tell me
in five seconds what is up, what is down and where to click.*

## 3. What already exists in the gallery (honest read)

Fetched 2026-11-07 from herdr.dev/gallery?type=mods:

| Mod | Does | What it does not do |
| --- | --- | --- |
| **Space Ports** (teknologist) | A line under each space in the sidebar: that space's TCP ports; click opens localhost, or starts `ssh -L` for a remote space | No process or container detail, no status/health, no stop, not a place to look at the whole machine |
| **Port Manager** (unickhow) | Right panel: every listening port, who holds it, stop one or several, share a port via tunnel | No project awareness, no declared-vs-running, no HTTP health, no containers by name |
| **Servers** (obrunogonzaga) | Every machine + CPU/mem/disk, docker containers, unhealthy-first, logs/restart, down/up notifications, `cmd-shift-m` | Container-centric: no arbitrary host processes, no ports as the primary axis, no project drift |
| **run-scripts** (cybertron288) | Run a `package.json` script in a new tab | Only JS, only scripts, does not know what is running |
| **Run / mprocs-style mods** | Declared processes as herdr-core terminals, start/stop/restart/peek | Declares its own list; does not read the machine, so it cannot see what is already up |

So "list the ports" is **solved twice**, and "run things" is solved from the declaration
side only. Nobody joins the two. That is the gap Berth sits in.

## 4. Positioning

> **The roll-call.** Everything listening on this machine — process, project, container,
> health — beside everything your repos say should be listening, with the difference
> spelled out.

Three claims no other mod can make:

1. **Expected vs running.** Reads `package.json`, `.env*`, `docker-compose.yml`,
   `Procfile`, `Makefile`, `.berth.json` in each space's folder, so a stopped service
   is a row you can see and start, not an absence you have to notice.
2. **Uptime and memory.** "up 2h 14m" · "died 4m ago after 3h" · a crash notification
   with a restart action. A port list is a photograph; Berth is a record.
3. **Conflicts explained.** "expected by `salmon-api`, held by ControlCenter (AirPlay
   Receiver)" beats `EADDRINUSE`.

## 5. Feature map

### v0.1 — in this repo now (parity-plus)

| # | Feature | State |
| --- | --- | --- |
| 1 | Every TCP listener: port, process, pid(s), working dir, full command | shipped |
| 2 | Grouped by herdr space → Docker → macOS daemons; "Mine / All" filter (`a`) | shipped |
| 3 | HTTP status pill per port (200/404/302/`tcp`), page `<title>` as the row name | shipped |
| 4 | Docker containers named per published port; unpublished containers listed in the footer | shipped |
| 5 | Click a row → opens the URL; right-click → copies it (`pbcopy`) | shipped |
| 6 | Stop a process holding a port, two-click confirm, TERM to every pid on the port | shipped |
| 7 | Rescan every 5s, `r` to force, `Esc` to close, JSON from a standalone `probe.py` | shipped |
| 8 | Zero network beyond `127.0.0.1`; nothing written outside the mod folder | shipped |

### v0.2 — shipped in this repo (items 9, 10, 11, 14)

| # | Feature | Effort | Why |
| --- | --- | --- | --- |
| 9 | **Drift: declared vs running.** Per space folder, read `package.json` scripts + `PORT=`, `.env*`, `docker-compose.yml` ports, `Procfile`, `Makefile`, `.berth.json`; show "3 expected · 2 up · 1 missing (:8001 `npm run dev`)" | M | The reason to install it over Port Manager |
| 10 | **Start / restart a missing service** in a new herdr tab using its own command (`pane.split` + `argv`, or `hc run`) | S | Turns the panel into the switcher |
| 11 | **Uptime + first-seen + last-seen**: `up 2h14m`, and a dim "died 4m ago" row for a service that was up in this session | S | The forgotten-server case |
| 12 | **Health, not just a status code**: optional path (`/healthz`), latency ms, consecutive failures, crash `notify()` with a Restart action | M | Catches "process alive, app dead" |
| 13 | **Search box** (port, name, project, container) + `j/k`/arrows + `⏎` to open + `x` to stop | S | 20 rows is fine; 40 is not |
| 14 | **Plain-English daemon labels**: :5000/:7000 AirPlay Receiver, :548, :56202 Handoff, :57621 Spotify, VS Code servers + a "turn it off" hint for AirPlay | S | The most common "why is 5000 taken" |
| 15 | **Conflict flag**: an expected port held by a different owner, named on both sides | S | Depends on 9 |
| 16 | **Copy as…**: URL · `PORT=3000` · `curl -s localhost:3000` · `.env` line · `ssh -L` for a remote space | S | Daily friction |

### v0.3 — depth and reach

| # | Feature | Effort | Why |
| --- | --- | --- | --- |
| 13b | **Search box** + `j/k` selection; `⏎` opens the selected row | S | Still open: 15 rows fit, 40 don't |
| 17 | **Remote spaces**: `exec(..., {on: space.machine})` so a VPS's ports appear in the same list, with the `ssh -L` command generated for you | M | Herdr users run agents on a VPS; Port Manager has tunnels, none has one list |
| 18 | **Docker depth**: compose project grouping, health state, uptime, "Logs in a pane", restart | M | Containers are half the answer at your setup |
| 19 | **Focus the terminal that holds it** (⌘-click): PID → cwd → pane via `hc ls`, `pane.focus` | M | Half the time you want the logs, not the page |
| 20 | **Docked layout variant** (`layouts/berth.json`): panel always visible on the right | S | Some people hate popups |
| 21 | **Linux `ss -ltnp` fallback**; Windows `netstat -ano` with a visible "not supported yet" state | S/M | Gallery reach |
| 22 | **History strip**: a sparkline of up/down per service for the last hour | L | Nice, not needed |

### Not doing

- Being a process manager for everything (no CPU/RAM charts — Servers owns that).
- Docker orchestration beyond logs/restart of what already runs.
- Writing into repos without consent: `.berth.json` is opt-in, created only when the
  person asks Berth to record a declaration.

## 6. Drift detection — the design (v0.2)

Sources, in order of confidence (a later source only fills gaps):

| Source | Read | Declaration |
| --- | --- | --- |
| `.berth.json` | `{"services":[{"name":"api","port":8001,"run":"make api","health":"/healthz"}]}` | explicit, wins over everything |
| `docker-compose.yml` | `services.*.ports`, `container_name` | container service + host port |
| `package.json` | `scripts.*`, `config.port`, `PORT` in `.env*` | runnable script + port if declared |
| `Procfile` | `web:`, `worker:` | name + command |
| `Makefile` | targets named `dev`, `api`, `start` | runnable command |
| `.env`, `.env.local` | `PORT=`, `*_PORT=`, `DATABASE_URL` | expected port |

Matching rules, so the panel never lies:

- A declaration is "up" when **some listener's cwd is inside the declaring repo** and
  its port matches. Port alone is not enough (two repos both default to 3000).
- A declaration with no port can still be "up" by process identity (command contains
  the script name) but is shown as "up (port unknown)".
- A declared port whose holder is *not* in the repo is a **conflict**, not "up".
- Declarations are cached per folder and re-read on file change (`watchFolder`), not
  every poll.

False-positive policy: drift is shown as a quiet "1 missing" line, never a notification.
Only *crash* (was up, now gone) notifies, once.

## 7. Interaction spec

| Input | Where | Does |
| --- | --- | --- |
| `cmd-shift-o` | global | open/close the panel |
| click row | any row with HTTP < 400 | open `http://localhost:PORT` |
| right-click row | any row | copy the URL |
| click `↗` | HTTP row | same as click |
| click `×` once | any row | arm ("stop?") |
| click `×` again | armed row | `kill -TERM` every pid on the port, refresh after 700ms |
| `a` | panel | toggle Mine / All |
| `r` | panel | rescan now |
| `Esc` | panel | close |
| `j` / `k`, `⏎`, `x` | panel (v0.2) | move / open / stop the selected row |
| `/` | panel (v0.2) | focus search |

## 8. Data model

`probe.py` prints one JSON document (nothing app-specific, so it is testable in a
terminal):

```json
{
  "at": 1794077728,
  "listeners": [{
    "port": 3000, "addr": "*", "pid": 39176, "pids": [39176],
    "proc": "node", "cmd": "node .../craco/dist/scripts/start.js",
    "cwd": "/Users/me/src/salmon-web", "kind": "dev|docker|app",
    "container": null, "http": 200, "title": "SME.works — ..."
  }],
  "containers": [{"name": "supabase_db_x", "status": "Up 2 hours", "ports": "0.0.0.0:54322->5432/tcp"}],
  "error": null
}
```

v0.2 adds `first_seen`, `last_ok`, `rtt_ms`, `failures`, and a sibling
`declared.json` from the declaration reader.

## 9. Risks

| Risk | Mitigation |
| --- | --- |
| `lsof` is ~0.6s; a 5s poll is a visible CPU blip | one spawn per poll, probe HTTP in parallel threads with a 0.45s cap, 15s TTL on probes, slow the poll when the panel is hidden |
| Drift false positives destroy trust | cwd-scoped matching, `.berth.json` override, quiet presentation |
| Gallery is crowded; "another port list" gets 5 stars | lead the README and the preview with the drift line, not the list |
| Remote `exec` on an offline machine hangs | `exec` rejects; the row shows "machine offline" instead of blocking the poll |
| Cross-platform | v0.1 states macOS + Linux(`ss`); Windows is a follow-up, not a silent break |
| Privacy | no network but `127.0.0.1`, documented; no telemetry; nothing written outside the mod folder |

## 10. Done when (acceptance for a shareable build)

1. `herdr-app check mods/berth` passes; `status` shows no errors; no `*.error` files.
2. A screenshot at 660×640 shows: header with counts, at least one space group, one
   Docker group, one daemon row under All, and a row with a 4xx pill.
3. Stop a throwaway `python3 -m http.server 8123` from the panel: the row disappears on
   the next poll and the port is free (`lsof -i :8123` empty).
4. A missing declared service appears as "missing" and Start brings it up in a new tab.
5. `python3 mods/berth/probe.py | python3 -m json.tool` is valid with no listeners.
6. README states what it runs (`lsof`, `ps`, `docker ps`, `python3`), what it reads, and
   that it talks to nothing but localhost.
