#!/usr/bin/env python3
"""What is listening on this Mac, and what your repos say should be.

Read by mods/muster/main.js (the Muster window). Prints:

  {"at": <unix>, "listeners": [...], "containers": [...], "expected": [...],
   "folders": [...], "error": null}

Each listener: port, addr, pid, pids, proc, cmd, cwd, kind, container, http,
title, uptime.

Each expected service (from .muster.json, package.json, .env*, Procfile,
Makefile, docker-compose* in a repo folder passed with --folder):
name, port, run, folder, source, health.

Nothing here is Herdr-specific: `python3 probe.py --folder ~/src/api` in a
terminal prints the same document.
"""

import http.client
import json
import os
import re
import shutil
import subprocess
import threading
import time

HOME = os.path.expanduser("~")
ENV = dict(os.environ)
ENV["PATH"] = ":".join(
    [ENV.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin", HOME + "/.local/bin"]
)

# Ports that are never HTTP: probing them with a GET only makes noise.
NOT_HTTP = {27017, 5432, 54322, 6379, 3306, 11211, 9092, 5672, 636, 993, 995}

DEV_PROC = re.compile(
    r"^(node|python|bun|deno|ruby|java|go|php|dotnet|beam\.smp|elixir|mix|"
    r"puma|uvicorn|gunicorn|rails|vite|next|astro|ng|httpd|nginx|postgres|"
    r"mysqld|redis-server|mongod|supabase|sam|func|air|nodemon|tsx|ts-node)",
    re.I,
)
SYSTEM_ROOTS = ("/System/", "/usr/libexec/", "/usr/sbin/", "/Library/Apple/", "/System")
APP_ROOTS = ("/Applications/", "/Library/")


def run(cmd, timeout=8, cwd=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV, cwd=cwd)
        return p.stdout or ""
    except Exception:
        return ""


def read(path):
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()[:200_000]
    except Exception:
        return None


# ---------------------------------------------------------------- listeners


def listening():
    """[(pid, proc, addr, port)] from lsof's field output."""
    out = run(["/usr/sbin/lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-F", "pcn"])
    rows, pid, proc = [], None, ""
    for line in out.splitlines():
        if not line:
            continue
        tag, val = line[0], line[1:]
        if tag == "p":
            pid, proc = int(val), ""
        elif tag == "c":
            proc = val
        elif tag == "n" and pid is not None:
            m = re.match(r"^(.*):(\d+)$", val)
            if m:
                rows.append((pid, proc, m.group(1) or "*", int(m.group(2))))
    return rows


def commands(pids):
    """pid -> (full command line, elapsed time)."""
    found = {}
    pids = [str(p) for p in pids]
    for i in range(0, len(pids), 120):
        out = run(["ps", "-o", "pid=,etime=,command=", "-p", ",".join(pids[i:i + 120])])
        for line in out.splitlines():
            m = re.match(r"^\s*(\d+)\s+(\S+)\s+(.*)$", line)
            if m:
                found[int(m.group(1))] = (m.group(3).strip(), m.group(2))
    return found


def cwds(pids):
    """pid -> working directory (what tells a dev server from a daemon)."""
    found = {}
    pids = [str(p) for p in pids]
    for i in range(0, len(pids), 120):
        out = run(["/usr/sbin/lsof", "-nP", "-a", "-p", ",".join(pids[i:i + 120]), "-d", "cwd", "-F", "pn"])
        pid = None
        for line in out.splitlines():
            if not line:
                continue
            if line[0] == "p":
                pid = int(line[1:])
            elif line[0] == "n" and pid is not None:
                found[pid] = line[1:]
    return found


def containers():
    """Docker's published ports: host port -> container name."""
    if not shutil.which("docker", path=ENV["PATH"]):
        return [], {}
    out = run(["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"], timeout=6)
    names, by_port = [], {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name, status, ports = parts[0], parts[1], parts[2]
        names.append({"name": name, "status": status, "ports": ports})
        for host, _cont in re.findall(r"(?:[\d.]+|\[::\]|\*):(\d+)->(\d+)/(?:tcp|udp)", ports):
            by_port[int(host)] = name
    return names, by_port


def probe(port):
    """(status, title) for an HTTP answer, else (None, None)."""
    if port in NOT_HTTP:
        return None, None
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.45)
        conn.request("GET", "/", headers={"User-Agent": "herdr-muster", "Accept": "text/html,*/*"})
        resp = conn.getresponse()
        body = b""
        if "html" in (resp.getheader("content-type") or ""):
            body = resp.read(8192)
        conn.close()
        title = None
        if body:
            m = re.search(rb"<title[^>]*>(.*?)</title>", body, re.I | re.S)
            if m:
                title = re.sub(r"\s+", " ", m.group(1).decode("utf-8", "replace")).strip()[:80]
        return resp.status, title
    except Exception:
        return None, None


def kind_of(proc, cwd, container):
    if container or re.search(r"docker|orbstack|colima", proc, re.I):
        return "docker"
    # An editor extension's language server lives in ~/.vscode or ~/Library:
    # it is a hidden helper, not the server someone forgot about.
    if cwd and re.search(r"/(\.vscode|\.cursor|\.windsurf|Library)/", cwd):
        return "app"
    if cwd and cwd.startswith(HOME + "/"):
        return "dev"
    if cwd and (cwd.startswith(SYSTEM_ROOTS) or cwd.startswith(APP_ROOTS)):
        return "app"
    if DEV_PROC.match(proc):
        return "dev"
    if cwd and cwd.startswith("/Volumes/"):
        return "dev"
    return "app"


# ---------------------------------------------------------------- declarations


def package_manager(folder):
    for lock, cmd in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun")):
        if os.path.exists(os.path.join(folder, lock)):
            return cmd
    return "npm"


def env_ports(folder):
    """PORT-ish values from .env files: {NAME: (port, filename)}."""
    found = {}
    for name in (".env", ".env.local", ".env.development", ".env.development.local"):
        text = read(os.path.join(folder, name))
        if not text:
            continue
        for line in text.splitlines():
            m = re.match(r"^\s*(?:export\s+)?([A-Z0-9_]*PORT[A-Z0-9_]*)\s*=\s*[\"']?(\d{2,5})", line)
            if m:
                found.setdefault(m.group(1), (int(m.group(2)), name))
    return found


def package_json(folder):
    """A runnable command and port from package.json, or None."""
    text = read(os.path.join(folder, "package.json"))
    if not text:
        return None
    try:
        doc = json.loads(text)
    except Exception:
        return None
    scripts = doc.get("scripts") or {}
    script = next((s for s in ("dev", "start", "serve") if s in scripts), None)
    deps = set(doc.get("dependencies") or {}) | set(doc.get("devDependencies") or {})
    env = env_ports(folder)
    port = env.get("PORT", (None, ""))[0]
    if port is None and script:
        m = re.search(r"(?:--port[= ]|-p )(\d{2,5})", scripts[script])
        if m:
            port = int(m.group(1))
    if port is None:
        for dep, default in (("vite", 5173), ("next", 3000), ("astro", 4321), ("nuxt", 3000),
                             ("react-scripts", 3000), ("@craco/craco", 3000)):
            if dep in deps:
                port = default
                break
    return {
        "name": doc.get("name") or os.path.basename(folder),
        "run": f"{package_manager(folder)} run {script}" if script else None,
        "port": port,
        "source": "package.json" + (f" + {env['PORT'][1]}" if "PORT" in env else ""),
    }


def procfile(folder):
    text = read(os.path.join(folder, "Procfile"))
    if not text:
        return None
    for line in text.splitlines():
        m = re.match(r"^(\w+)\s*:\s*(.+)$", line)
        if m and m.group(1) in ("web", "server"):
            cmd = m.group(2).strip()
            pm = re.search(r"(?:--port[= ]|-p )(\d{2,5})", cmd)
            return {"name": "web", "run": cmd, "port": int(pm.group(1)) if pm else None, "source": "Procfile"}
    return None


def makefile(folder):
    text = read(os.path.join(folder, "Makefile"))
    if not text:
        return None
    for target in ("dev", "serve", "api", "start"):
        if re.search(rf"^{target}\s*:", text, re.M):
            return {
                "name": target,
                "run": f"make {target}",
                "port": env_ports(folder).get("PORT", (None, ""))[0],
                "source": "Makefile",
            }
    return None


def compose(folder):
    """Best-effort docker-compose read: service names and their published ports."""
    name = next((n for n in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
                 if os.path.exists(os.path.join(folder, n))), None)
    if not name:
        return []
    text = read(os.path.join(folder, name)) or ""
    out, service, in_ports = [], None, False
    for line in text.splitlines():
        m = re.match(r"^\s{2}([A-Za-z0-9_.-]+):\s*$", line)
        if m:
            service, in_ports = m.group(1), False
            continue
        if re.match(r"^\s+ports:\s*$", line):
            in_ports = True
            continue
        if not in_ports:
            continue
        p = re.match(r"^\s+-\s*[\"']?(?:[\d.]+:)?(\d{2,5}):(\d{2,5})[\"']?\s*$", line)
        if p:
            out.append({"name": service, "port": int(p.group(1)), "run": f"docker compose up -d {service}",
                        "source": name})
            in_ports = False
        elif re.match(r"^\s+[a-z_]+:", line):
            in_ports = False
    return out


def declarations(folder):
    """Every service this repo says should be running."""
    found = []
    explicit = read(os.path.join(folder, ".muster.json"))
    if explicit:
        try:
            for s in json.loads(explicit).get("services") or []:
                if s.get("port"):
                    found.append({"name": s.get("name") or "service", "port": int(s["port"]),
                                  "run": s.get("run"), "health": s.get("health"),
                                  "source": ".muster.json"})
        except Exception:
            pass
    if not found:
        pkg = package_json(folder)
        if pkg and pkg.get("port"):
            found.append(pkg)
        for reader in (procfile, makefile):
            entry = reader(folder)
            if entry and entry.get("port"):
                found.append(entry)
        # Containers are declared beside the app, not instead of it: a repo
        # with package.json and a compose file has both.
        found.extend(compose(folder))
    seen, out = set(), []
    for e in found:
        if e["port"] in seen:
            continue
        seen.add(e["port"])
        e["folder"] = folder
        out.append(e)
    return out


MARKERS = (
    "package.json", ".muster.json", "docker-compose.yml", "docker-compose.yaml",
    "compose.yml", "compose.yaml", "Procfile", "Makefile", "pyproject.toml",
    "requirements.txt", "go.mod", "Cargo.toml", "Gemfile",
)
SKIP = {"node_modules", "dist", "build", "vendor", "__pycache__", ".git", "target", ".venv", "venv"}


def looks_like_project(folder):
    return any(os.path.exists(os.path.join(folder, m)) for m in MARKERS)


def expand(base):
    """The base folder and its immediate children that look like projects.

    Herdr spaces are usually a parent folder holding several repos, so one
    space is not one project.
    """
    out = [base]
    try:
        children = sorted(os.listdir(base))
    except Exception:
        return out
    for name in children[:200]:
        if name.startswith(".") or name in SKIP:
            continue
        path = os.path.join(base, name)
        if os.path.isdir(path) and looks_like_project(path):
            out.append(path)
        if len(out) >= 40:
            break
    return out


def scan_folders(bases):
    expected, scanned = [], []
    for base in bases:
        base = os.path.abspath(os.path.expanduser(base))
        if not os.path.isdir(base):
            continue
        for folder in expand(base):
            if folder in scanned:
                continue
            scanned.append(folder)
            expected.extend(declarations(folder))
    return expected, scanned


# ---------------------------------------------------------------- main


def main(argv):
    folders = [argv[i + 1] for i, a in enumerate(argv) if a == "--folder" and i + 1 < len(argv)]
    doc = {"at": int(time.time()), "listeners": [], "containers": [], "expected": [], "folders": [], "error": None}
    try:
        rows = listening()
        dockers, by_port = containers()
        doc["containers"] = dockers

        # One row per port: SO_REUSEPORT servers show twice, and so do a
        # process and the docker proxy in front of it.
        grouped = {}
        for pid, proc, addr, port in rows:
            grouped.setdefault(port, []).append((pid, proc, addr))

        pids = {port: [r[0] for r in rs] for port, rs in grouped.items()}
        all_pids = sorted({p for rs in pids.values() for p in rs})
        info, dirs = commands(all_pids), cwds(all_pids)

        def rank(entry):
            # A row with a working directory beats one without: the proxy
            # in front of a container has none, the real server has one.
            pid, proc, addr = entry
            return (dirs.get(pid) is None, addr.startswith("*"))

        probed = {}
        threads = [threading.Thread(target=lambda p=p: probed.__setitem__(p, probe(p)), daemon=True) for p in grouped]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)

        for port in sorted(grouped):
            pid, proc, addr = sorted(grouped[port], key=rank)[0]
            cwd = dirs.get(pid)
            status, title = probed.get(port, (None, None))
            cmd, elapsed = info.get(pid, ("", ""))
            container = by_port.get(port)
            doc["listeners"].append(
                {
                    "port": port,
                    "addr": addr,
                    "pid": pid,
                    "pids": pids[port],
                    "proc": proc,
                    "cmd": cmd[:400],
                    "cwd": cwd,
                    "kind": kind_of(proc, cwd, container),
                    "container": container,
                    "http": status,
                    "title": title,
                    "uptime": elapsed,
                }
            )

        doc["expected"], doc["folders"] = scan_folders(folders)
    except Exception as e:  # the window shows this instead of an empty list
        doc["error"] = f"{type(e).__name__}: {e}"
    print(json.dumps(doc))


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
