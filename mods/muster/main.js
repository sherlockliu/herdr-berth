// Muster: every TCP port listening on this Mac, who is holding it, and the
// space it belongs to — so a forgotten dev server is a glance, not `lsof`.
// The probing is probe.py (next to this file); this draws what it returns.
//
// Open with `mod.open muster` (or the key bound in keys.json -> cmd-shift-o).

import { View, div, svg } from "gpui-kit";
import { v_flex, h_flex } from "gpui-base";
import { appHome, closeOverlay, exec, home, notify, props, run, spaces, theme } from "herdr";

const MONO = "Menlo";
const ICON = (n) => `icons/${n}.svg`;
const CHROME = (n) => `mods/workspace-chrome/${n}.svg`;
const OWN = (n) => `mods/muster/${n}.svg`;
const LOCAL = ICON("program");

// A row's icon, from what the process looks like from outside.
function iconFor(e) {
  const s = `${e.container ?? ""} ${e.proc ?? ""} ${e.cmd ?? ""} ${e.cwd ?? ""}`.toLowerCase();
  if (e.container) {
    if (s.includes("supabase")) return ICON("supabase");
    if (s.includes("mongo")) return ICON("mongosh");
    if (s.includes("postgres") || s.includes("_db_")) return ICON("psql");
    if (s.includes("redis")) return ICON("redis-cli");
    return ICON("docker");
  }
  if (s.includes("vite") || s.includes("craco") || s.includes("webpack") || s.includes("react-scripts")) return ICON("vite");
  if (/\bnext\b/.test(s)) return ICON("next");
  if (s.includes("astro")) return ICON("astro");
  if (s.includes("nuxt")) return ICON("nuxt");
  if (s.includes("expo")) return ICON("expo");
  if (s.includes("uvicorn") || s.includes("fastapi")) return ICON("fastapi");
  if (s.includes("runserver") || s.includes("django")) return ICON("django-admin");
  if (s.includes("flask")) return ICON("flask");
  if (s.includes("vitest") || s.includes("jest")) return ICON("vitest");
  if (/\/uv\b|\buv run\b/.test(s)) return ICON("uv");
  if (s.includes("cargo")) return ICON("cargo");
  if (/\bgo run\b|go-build/.test(s)) return ICON("go");
  if (s.includes("ollama")) return ICON("ollama");
  if (s.includes("playwright") || s.includes("hermes")) return ICON("hermes");
  if (/^python|python\d/.test(e.proc ?? "") || s.includes(".py")) return ICON("python");
  if (/^(node|npm|npx|yarn|pnpm)/.test(e.proc ?? "") || s.includes("node ")) return ICON("node");
  if (s.includes("bun")) return ICON("bun");
  if (s.includes("deno")) return ICON("deno");
  if (s.includes("psql") || s.includes("postgres")) return ICON("psql");
  if (s.includes("redis")) return ICON("redis-cli");
  if (s.includes("mysql")) return ICON("mysql");
  if (e.kind === "app") return ICON("program");
  return LOCAL;
}

const shortPath = (p, h) => (p && h && p.startsWith(h) ? `~${p.slice(h.length)}` : p ?? "");

// A shell-quoted one-liner is the only way to hand pbcopy a string: exec has
// no stdin.
const shq = (s) => `'${String(s).replace(/'/g, `'\\''`)}'`;

export default class Ports extends View {
  init(_props, cx) {
    this.data = null; // probe.py's document
    this.loading = false;
    this.filter = "mine"; // "mine" (dev + docker) | "all"
    this.armed = null; // {port} after one click on stop
    this.note = null; // transient line under the list
    this.handle = cx.focus_handle();
    this.refresh(cx);
    cx.timer.every(5000, (cx) => this.refresh(cx));
  }

  refresh(cx) {
    if (this.loading) return;
    this.loading = true;
    cx.spawn(async (cx) => {
      try {
        const r = await exec("python3", [`${appHome()}/mods/muster/probe.py`]);
        if (r.code !== 0 && !r.stdout.trim()) throw new Error((r.stderr || "probe failed").trim());
        const doc = JSON.parse(r.stdout);
        if (doc.error) throw new Error(doc.error);
        this.data = doc;
        this.error = null;
      } catch (e) {
        this.error = String(e?.message ?? e);
      } finally {
        this.loading = false;
        cx.notify();
      }
    });
  }

  // Which Herdr space a working directory belongs to (deepest folder wins).
  spaceFor(cwd) {
    if (!cwd) return null;
    let best = null;
    const h = home();
    for (const s of spaces()) {
      if (!s.folder || s.machine) continue;
      // A space rooted at home (or /) would claim every listener there.
      if (s.folder === h || s.folder === "/") continue;
      if (cwd === s.folder || cwd.startsWith(`${s.folder}/`)) {
        if (!best || s.folder.length > best.folder.length) best = s;
      }
    }
    return best?.name ?? null;
  }

  rows() {
    const h = home();
    const list = (this.data?.listeners ?? []).map((e) => {
      const space = e.kind === "docker" ? null : this.spaceFor(e.cwd);
      // A 404 page's <title> ("Error") is not the app's name.
      const title = e.http != null && e.http < 400 ? e.title || null : null;
      const dir = e.cwd && e.cwd !== "/" ? shortPath(e.cwd, h) : null;
      // The project folder names a server better than the space it sits in,
      // and the space header above the row already says where it belongs.
      const label =
        title || (e.container ? e.container : null) || (dir ? dir.split("/").pop() : null) || space || e.proc;
      const group = space || (e.kind === "docker" ? "Docker" : e.kind === "app" ? "macOS apps and daemons" : dir || e.proc);
      return { ...e, space, title, label, group, rank: e.kind === "app" ? 2 : e.kind === "docker" ? 1 : 0 };
    });
    const shown = this.filter === "all" ? list : list.filter((e) => e.kind !== "app");
    return shown.sort((a, b) => a.rank - b.rank || a.group.localeCompare(b.group) || a.port - b.port);
  }

  act(e, what, cx) {
    if (what === "open") {
      exec("open", [`http://localhost:${e.port}/`]).catch(() => {});
      return;
    }
    if (what === "copy") {
      const url = `http://localhost:${e.port}`;
      exec("sh", ["-c", `printf %s ${shq(url)} | pbcopy`])
        .then(() => notify({ title: "Copied", body: url, level: "info", timeout: 1500 }))
        .catch(() => {});
      return;
    }
    if (what === "stop") {
      if (this.armed !== e.port) {
        this.armed = e.port;
        cx.notify();
        return;
      }
      this.armed = null;
      cx.notify();
      cx.spawn(async (cx) => {
        for (const pid of e.pids ?? [e.pid]) await exec("kill", ["-TERM", String(pid)]).catch(() => {});
        this.note = `Sent stop to ${e.proc}${e.container ? ` (${e.container})` : ""} on :${e.port}`;
        notify({ title: `Stopped :${e.port}`, body: this.note, level: "info", timeout: 2000 });
        cx.timer.after(700, (cx) => this.refresh(cx));
        cx.notify();
      });
      return;
    }
  }

  pill(t, label, color, extra) {
    return div()
      .px(6)
      .h(18)
      .flex()
      .items_center()
      .rounded(5)
      .bg(extra ?? t.raised)
      .text_size(10.5)
      .font_family(MONO)
      .text_color(color)
      .child(label);
  }

  row(t, e, cx) {
    const h = home();
    const ok = e.http != null && e.http < 400;
    const statusColor = e.http == null ? t.dim : e.http >= 500 ? t.ansi1 : e.http >= 400 ? t.ansi3 : t.ansi2;
    const armed = this.armed === e.port;
    const script = (e.cmd ?? "")
      .split(/\s+/)
      .filter((a) => /\.(js|mjs|cjs|ts|py|rb|php|jar|go)$/.test(a))
      .pop();
    const sub = [`localhost:${e.port}`, e.container ?? e.proc, script ? script.split("/").pop() : null]
      .filter(Boolean)
      .join("  ·  ");
    const button = (id, icon, on, tint) =>
      div()
        .id(id)
        .w(22)
        .h(22)
        .flex()
        .items_center()
        .justify_center()
        .rounded(6)
        .cursor_pointer()
        .hover((s) => s.bg(t.hover))
        .on_mouse_down("left", (_e, cx) => cx.stop_propagation())
        .on_click((_e, cx) => on(cx))
        .child(svg(icon).size(12).text_color(tint));
    return h_flex()
      .id(`port-${e.port}`)
      .h(44)
      .px(8)
      .gap(9)
      .items_center()
      .rounded(8)
      .when(ok, (el) => el.cursor_pointer())
      .hover((s) => s.bg(t.hover))
      .when(ok, (el) => el.on_click((_e, cx) => this.act(e, "open", cx)))
      .on_mouse_down("right", (_e, cx) => this.act(e, "copy", cx))
      .child(svg(iconFor(e)).size(16).text_color(e.kind === "app" ? t.dim : t.foreground))
      .child(
        v_flex()
          .flex_1()
          .min_w(0)
          .gap(1)
          .child(div().truncate().text_size(12.5).font_medium().text_color(e.kind === "app" ? t.muted : t.foreground).child(e.label ?? e.proc))
          .child(div().truncate().text_size(11).font_family(MONO).text_color(t.dim).child(sub)),
      )
      .child(this.pill(t, e.http == null ? "tcp" : String(e.http), statusColor))
      .when(ok, (el) => el.child(button(`pt-open-${e.port}`, OWN("open"), (cx) => this.act(e, "open", cx), t.muted)))
      .child(button(`pt-stop-${e.port}`, CHROME("x"), (cx) => this.act(e, "stop", cx), armed ? t.ansi1 : t.dim));
  }

  chip(t, label, value, count) {
    const on = this.filter === value;
    return div()
      .id(`pt-chip-${value}`)
      .px(9)
      .h(22)
      .flex()
      .items_center()
      .gap(5)
      .rounded(6)
      .bg(on ? t.raised : t.popover)
      .border(1)
      .border_color(on ? t.border : t.popover)
      .text_size(11.5)
      .text_color(on ? t.foreground : t.muted)
      .cursor_pointer()
      .on_click((_e, cx) => {
        this.filter = value;
        cx.notify();
      })
      .child(label)
      .child(div().text_size(10.5).font_family(MONO).text_color(t.dim).child(String(count)));
  }

  render(cx) {
    const t = theme();
    const all = this.data?.listeners ?? [];
    const mine = all.filter((e) => e.kind !== "app").length;
    const rows = this.rows();
    const groups = [];
    for (const e of rows) {
      const last = groups[groups.length - 1];
      if (last && last.name === e.group) last.rows.push(e);
      else groups.push({ name: e.group, rows: [e] });
    }
    const hidden = all.filter((e) => e.kind === "app").length;
    const quiet = (this.data?.containers ?? []).filter((c) => !all.some((e) => e.container === c.name));
    return v_flex()
      .id("muster")
      .track_focus(this.handle)
      .on_key_down((e, cx) => {
        if (e.key === "escape" && props()?.overlay) closeOverlay(props().overlay);
        else if (e.key === "r") this.refresh(cx);
        else if (e.key === "a") {
          this.filter = this.filter === "all" ? "mine" : "all";
          cx.notify();
        }
      })
      .size_full()
      .min_h(0)
      .p(14)
      .gap(10)
      .bg(t.popover)
      .text_color(t.foreground)
      .child(
        h_flex()
          .items_center()
          .gap(8)
          .child(div().text_size(14).font_semibold().child("Muster"))
          .child(div().text_size(11).font_family(MONO).text_color(t.dim).child(`${mine} listening`))
          .child(div().flex_1())
          .child(this.chip(t, "Mine", "mine", mine))
          .child(this.chip(t, "All", "all", all.length))
          .child(
            div()
              .id("pt-refresh")
              .w(24)
              .h(22)
              .flex()
              .items_center()
              .justify_center()
              .rounded(6)
              .cursor_pointer()
              .hover((s) => s.bg(t.hover))
              .on_click((_e, cx) => this.refresh(cx))
              .child(svg(this.loading ? CHROME("spinner") : OWN("refresh")).size(13).text_color(t.muted)),
          )
          .when(Boolean(props()?.overlay), (el) =>
            el.child(
              div()
                .id("pt-close")
                .w(24)
                .h(22)
                .flex()
                .items_center()
                .justify_center()
                .rounded(6)
                .cursor_pointer()
                .hover((s) => s.bg(t.hover))
                .on_click(() => closeOverlay(props().overlay))
                .child(svg(CHROME("x")).size(12).text_color(t.muted)),
            ),
          ),
      )
      .when(Boolean(this.error), (el) =>
        el.child(div().text_size(12).text_color(t.ansi1).child(`probe failed: ${this.error}`)),
      )
      .child(
        v_flex()
          .id("pt-list")
          .flex_1()
          .min_h(0)
          .overflow_y_scrollbar()
          .gap(1)
          .children(
            this.data === null
              ? [div().p(10).text_size(12).text_color(t.dim).child("Looking at what's listening…")]
              : rows.length === 0
                ? [div().p(10).text_size(12).text_color(t.dim).child(this.filter === "mine" ? "Nothing of yours is listening. `a` shows the Mac's own daemons." : "Nothing is listening on TCP.")]
                : groups.flatMap((g) => [
                    div()
                      .pt(8)
                      .pb(3)
                      .px(8)
                      .text_size(10)
                      .font_family(MONO)
                      .font_semibold()
                      .text_color(t.dim)
                      .child(`${g.name}  ·  ${g.rows.length}`),
                    ...g.rows.map((e) => this.row(t, e, cx)),
                  ]),
          ),
      )
      .child(
        h_flex()
          .items_center()
          .gap(8)
          .child(
            div()
              .flex_1()
              .min_w(0)
              .truncate()
              .text_size(10.5)
              .text_color(t.dim)
              .child(
                this.note ??
                  [
                    hidden && this.filter === "mine" ? `${hidden} app daemons hidden (a)` : null,
                    quiet.length ? `${quiet.length} docker containers unpublished: ${quiet.slice(0, 3).map((c) => c.name).join(", ")}${quiet.length > 3 ? "…" : ""}` : null,
                    "click a row to open · right-click to copy",
                  ]
                    .filter(Boolean)
                    .join("  ·  "),
              ),
          ),
      );
  }
}
