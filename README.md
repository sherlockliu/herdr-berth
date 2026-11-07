# Berth

A roll-call for your machine: everything listening on a port — the process, the repo it
belongs to, the Docker container behind it, whether it answers — and, unlike a port
list, what your projects said should be running but isn't.

![Berth](preview.png)

**Open it with `cmd-shift-o`** — or `herdr-app do mod.open '{"name":"berth"}'` from any
shell. Herdr maps the `cmd-` prefix to ctrl away from macOS, so the same chord works as
`ctrl-shift-o` on Linux and Windows.

```
Berth   7 listening · 2 missing            [Mine 7] [All 11]  demo  ⟳  ×

acme-store  ·  2
  ⚡ Acme Store — Checkout                       200  ↗  ×
     localhost:3000 · node · start.js · up 2d 4h
  ▶ search                                       down     [ Start ]
     expected :9200 · acme-store · docker compose up -d search · docker-compose.yml
atlas-dashboard  ·  1
  ⚡ Atlas — Feature flags                        200  ↗  ×
     localhost:5173 · node · vite.js · up 43m
ledger-api  ·  2
  ⚡ ledger-api                                  200  ↗  ×
     localhost:8000 · python3.11 · app.py · up 3h 12m
  ▶ worker                                       down     [ Start ]
     expected :8010 · ledger-api · pnpm run worker · package.json
Docker  ·  4
  ⚡ acme_kong                                   404  ↗  ×
     localhost:54321 · acme_kong · up 5d 22h
```

## Install

> Read ~/.config/herdr-app/AGENTS.md, then add this mod: `mods/berth/` from this repo,
> plus the `keys.json` snippet.

Or by hand:

```sh
cp -R mods/berth ~/.config/herdr-app/mods/
herdr-app check ~/.config/herdr-app/mods/berth
```

Then merge `keys.json` (it binds `cmd-shift-o` globally to `mod.open:berth`), or open
it from anywhere with `herdr-app do mod.open '{"name":"berth"}'`.

Removing the folder removes the mod; remove the key line too.

## What you get

| | |
| --- | --- |
| Open / close | `cmd-shift-o`, or `mod.open berth` from the CLI |
| Every listener | port, bind address, process, pid(s), working directory, full command line |
| Grouped | by your Herdr space (longest matching folder), then `Docker`, then the Mac's own daemons |
| Named | the page title for HTTP servers, the project folder, or the container name — not just `python3.11` |
| Status | HTTP code pill (`200`, `404`, `302`) or `tcp` for Mongo/Postgres/Redis |
| Docker | containers mapped to their published ports by name; containers with **no published port** counted in the footer, so you stop hunting for them |
| Click | open the URL in your browser |
| Right-click | copy `http://localhost:PORT` |
| `×` twice | stop every process holding that port (`TERM`), then rescan |
| **Drift** | a service your repo declares but nothing is listening on shows as a `down` row with its port, its command and where it came from |
| **Start** | that row's `Start` button runs the project's own command (`pnpm run dev`, `make api`, `docker compose up -d db`) in a new Herdr tab, in its space |
| **Uptime** | `up 24m` on every row, from `ps` elapsed time |
| **Expected** | rows that satisfy a declaration get a check mark; a declared port held by someone else is marked amber |
| **Daemon names** | `:5000`/`:7000` read "AirPlay Receiver", not `ControlCenter` |

### Keys

| Key | Does |
| --- | --- |
| `cmd-shift-o` (`ctrl-shift-o`) | open the panel; again, or **`Esc`**, closes it |
| `Esc` | close the window. It focuses itself when it opens, so this works straight away — a click inside takes focus back if it ever goes behind |
| `a` | toggle **Mine** (dev servers + containers) / **All** (plus macOS daemons) |
| `r` | rescan now (it also polls every 5s) |
| click · right-click | open the URL · copy `http://localhost:PORT` |
| `×` twice | stop every process holding that port, then rescan |

## What counts as declared

For every repo inside each of your spaces' folders (the folder itself and its
immediate children that hold a marker file), in this order:

| Source | Gives |
| --- | --- |
| `.berth.json` | `{"services":[{"name":"api","port":8001,"run":"make api","health":"/healthz"}]}` — wins over everything |
| `package.json` | the `dev` / `start` / `serve` script, run with the repo's package manager (`pnpm`, `yarn`, `bun`, else `npm`); the port from `.env*` (`PORT=`, `*_PORT=`), from `--port N` in the script, or the framework default (vite 5173, next 3000, astro 4321, CRA 3000) |
| `Procfile` | the `web:` command |
| `Makefile` | a `dev` / `serve` / `api` / `start` target |
| `docker-compose.y*ml`, `compose.y*ml` | each service and its published host port — always added, beside the app |

A port counts as "up" only when something is listening on it. A declared port held
by a process outside the repo is flagged, not counted.

## What it runs and reads

- Runs: `lsof` (listeners, working dirs), `ps` (command lines), `docker ps` (container
  names), and `python3` on the bundled `mods/berth/probe.py`.
- Reads: the files in the table above, inside your spaces' folders — nothing else.
  No dotfiles outside a repo root, no home-directory scans.
- Network: `127.0.0.1` only — one `GET /` per unknown port to label it (`200`, page
  title). No telemetry, no remote calls, nothing sent anywhere.
- Writes: nothing outside `~/.config/herdr-app`.

## Requirements and platforms

Herdr desktop app, and `python3` on `PATH`. Docker is optional — without it the `Docker`
group is simply absent.

| | Ports come from | Working directory (grouping, drift match) | Browser / copy / stop / start |
| --- | --- | --- | --- |
| **macOS** (tested) | `lsof` | `lsof -d cwd` | `open` · `pbcopy` · `kill -TERM` · `/bin/zsh -lc` |
| **Linux** | `ss -ltnp`, `lsof` as a fallback | `/proc/<pid>/cwd` | `xdg-open` · `wl-copy`/`xclip` · `kill -TERM` · `/bin/sh -lc` |
| **Windows** | `netstat -ano` + `tasklist` | **not available** — no command line either | `cmd /c start` · `clip` · `taskkill /T /F` · `powershell -Command` |

Windows therefore lists ports, processes and containers, but rows group by process name
instead of project, and a declaration can only be matched by port number, not by repo.
That path is written but untested — `python3 mods/berth/probe.py --selftest` checks the
`ss`/`netstat`/`lsof` parsers on all three, and issues with a real Windows box are
welcome.

## Preview data (how `preview.png` was made)

The screenshot ships with no real project names. Copy the bundled demo document next to
the mod and it draws that instead of your machine, with a `demo` chip in the header:

```sh
cp fixtures/demo.json ~/.config/herdr-app/mods/berth/demo.json   # turn it on
rm ~/.config/herdr-app/mods/berth/demo.json                      # back to real data
```

The file is a whole `probe.py` document (`listeners`, `containers`, `expected`, and the
`spaces` to group by) named with `/Users/demo/src/...` paths, so it also works as a test
fixture for the panel's rendering. `install.sh` never copies it.

## Develop

`probe.py` is standalone; run it in a terminal to see exactly what the panel draws:

```sh
python3 mods/berth/probe.py | python3 -m json.tool
herdr-app check ~/.config/herdr-app/mods/berth     # after each edit
```

Live edits: the app reloads a mod when its files are saved; the panel reopens with the
key (`cmd-shift-o`).

See `docs/PRODUCT.md` for the product design, the gallery comparison (Space Ports, Port
Manager, Servers, run-scripts) and the roadmap — the next milestone is **drift**: what
your repos declare versus what is actually listening.

## License

MIT.
