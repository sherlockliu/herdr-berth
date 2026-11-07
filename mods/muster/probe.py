#!/usr/bin/env python3
"""What is listening on this Mac, in one JSON document.

Read by mods/ports/main.js (the Ports window). Prints:

  {"at": <unix>, "listeners": [...], "containers": [...], "error": null}

Each listener: port, addr, pid, pids, proc, cmd, cwd, kind, container,
http (status code or null), title (page <title>, if any), iface.

Nothing here is Herdr-specific: `python3 probe.py` in a terminal prints the
same document.
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


def run(cmd, timeout=8):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV)
        return p.stdout or ""
    except Exception:
        return ""


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
    """pid -> full command line."""
    found = {}
    pids = [str(p) for p in pids]
    for i in range(0, len(pids), 120):
        out = run(["ps", "-o", "pid=,command=", "-p", ",".join(pids[i:i + 120])])
        for line in out.splitlines():
            m = re.match(r"^\s*(\d+)\s+(.*)$", line)
            if m:
                found[int(m.group(1))] = m.group(2).strip()
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
    host = "127.0.0.1"
    try:
        conn = http.client.HTTPConnection(host, port, timeout=0.45)
        conn.request("GET", "/", headers={"User-Agent": "herdr-ports", "Accept": "text/html,*/*"})
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


def main():
    doc = {"at": int(time.time()), "listeners": [], "containers": [], "error": None}
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
        cmds, dirs = commands(all_pids), cwds(all_pids)

        def rank(entry):
            # A row with a working directory beats one without: the proxy
            # in front of a container has none, the real server has one.
            pid, proc, addr = entry
            return (dirs.get(pid) is None, addr.startswith("*"))

        probed = {}

        def work(port):
            probed[port] = probe(port)

        threads = [threading.Thread(target=work, args=(p,), daemon=True) for p in grouped]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)

        for port in sorted(grouped):
            pid, proc, addr = sorted(grouped[port], key=rank)[0]
            cwd = dirs.get(pid)
            status, title = probed.get(port, (None, None))
            container = by_port.get(port)
            doc["listeners"].append(
                {
                    "port": port,
                    "addr": addr,
                    "pid": pid,
                    "pids": pids[port],
                    "proc": proc,
                    "cmd": (cmds.get(pid) or "")[:400],
                    "cwd": cwd,
                    "kind": kind_of(proc, cwd, container),
                    "container": container,
                    "http": status,
                    "title": title,
                }
            )
    except Exception as e:  # the window shows this instead of an empty list
        doc["error"] = f"{type(e).__name__}: {e}"
    print(json.dumps(doc))


if __name__ == "__main__":
    main()
