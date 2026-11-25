#!/usr/bin/env python3
"""Generates the SVG assets used by the profile README.

build_assets.py bars                      static section bars, written to assets/
build_assets.py session OUT.svg           live session card, built from public GitHub data
build_assets.py session OUT.svg --still   the same card without animation

GH_TOKEN and GH_OWNER are optional. Without a token the public API allows
60 requests an hour, which is enough for one build.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

OWNER = os.environ.get("GH_OWNER", "PaswanRaunak")
API = "https://api.github.com"

GREEN, WHITE, TEXT, SOFT, DIM, FAINT = "#00FF41", "#f2f7f2", "#d7e8d7", "#7ee88c", "#5fae72", "#4f9e63"
FONT = "Consolas,'JetBrains Mono',Menlo,'DejaVu Sans Mono',monospace"
PROMPT = "raunak@github:~$ "

SIZE = 19
CW = SIZE * 0.6
X0 = 56
PER_CHAR = 0.055

ABOUT = (
    "android apps and web tools",
    "learning kotlin, astro and web dev in public",
    "linux and git basics",
)

# Forks are skipped automatically. These are not forks, but they are not
# what the profile is about.
SKIPPED = ("android_", "build_")


# ---------- data ----------

def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-assets"}
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(API + path, headers=headers), timeout=20) as response:
        return json.load(response)


def is_bot(commit):
    login = (commit.get("author") or {}).get("login") or ""
    name = (commit.get("commit", {}).get("author") or {}).get("name") or ""
    return "github-actions" in login.lower() or "github-actions" in name.lower() or "[bot]" in name.lower()


def subject(message, limit=40):
    first = next((row for row in message.splitlines() if row.strip()), "")
    first = re.sub(r"\s+", " ", re.sub(r"[^\x20-\x7e]", "", first)).strip()
    return first if len(first) <= limit else first[: limit - 3].rstrip() + "..."


def ago(date, now):
    seconds = (now - date).total_seconds()
    if seconds < 3600:
        return "just now"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    days = int(seconds // 86400)
    if days < 7:
        return f"{days}d ago"
    if days < 30:
        return f"{days // 7}w ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


def latest_commits(count=3):
    """Latest human commit per public, non-fork repository."""
    found = []
    for repo in api(f"/users/{OWNER}/repos?per_page=100&type=owner&sort=pushed"):
        name = repo["name"]
        if repo.get("fork") or not repo.get("pushed_at"):
            continue
        if name.lower() == OWNER.lower() or name.startswith(SKIPPED):
            continue
        try:
            commits = api(f"/repos/{OWNER}/{name}/commits?per_page=5")
        except urllib.error.HTTPError:
            continue
        for commit in commits:
            if is_bot(commit):
                continue
            stamp = commit["commit"]["committer"]["date"]
            date = dt.datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
            found.append({
                "repo": name if len(name) <= 17 else name[:14] + "...",
                "sha": commit["sha"][:7],
                "subject": subject(commit["commit"]["message"]),
                "ago": ago(date, dt.datetime.now(dt.timezone.utc)),
                "date": date,
            })
            break
    found.sort(key=lambda item: item["date"], reverse=True)
    if not found:
        raise RuntimeError("no public commits found")
    return found[:count]


# ---------- drawing ----------

def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def text(x, y, content, fill, anchor=None, length=True):
    attrs = f'x="{x:g}" y="{y}" font-size="{SIZE}" fill="{fill}"'
    if anchor:
        attrs += f' text-anchor="{anchor}"'
    if length:
        attrs += f' textLength="{len(content) * CW:.1f}"'
    return f"<text {attrs}>{esc(content)}</text>"


def dots():
    return "".join(
        f'<circle cx="{36 + offset * 24}" cy="24" r="7" fill="{GREEN}" fill-opacity="{opacity}"/>'
        for offset, opacity in enumerate((1, 0.5, 0.25))
    )


def gradient():
    return (
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0b130b"/><stop offset="1" stop-color="#060a06"/>'
        "</linearGradient>"
    )


def svg(height, title, inner):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" '
        f'viewBox="0 0 1000 {height}" font-family="{FONT}">'
        f"<title>{esc(title)}</title><defs>{gradient()}</defs>{inner}</svg>"
    )


def card(height, title, body, note=""):
    note_text = f'<text x="965" y="29" text-anchor="end" font-size="14" fill="{FAINT}">{esc(note)}</text>' if note else ""
    return svg(height, title, (
        f'<rect width="1000" height="{height}" rx="18" fill="url(#bg)"/>'
        f'<rect x="1" y="1" width="998" height="{height - 2}" rx="17" fill="none" stroke="{GREEN}" stroke-opacity="0.35"/>'
        f'{dots()}<text x="500" y="29" text-anchor="middle" font-size="15" fill="{DIM}">{esc(title)}</text>{note_text}'
        f'<line x1="1" y1="47" x2="999" y2="47" stroke="{GREEN}" stroke-opacity="0.25"/>'
        f"{body}"
    ))


def prompt_line(y):
    return (
        f'<text x="{X0}" y="{y}" font-size="{SIZE}" textLength="{len(PROMPT) * CW:.1f}">'
        f'<tspan fill="{WHITE}">raunak@github</tspan><tspan fill="{SOFT}">:~</tspan>'
        f'<tspan fill="{GREEN}">$ </tspan></text>'
    )


def command(y, cmd):
    return text(X0 + len(PROMPT) * CW, y, cmd, WHITE)


def typed_command(y, cmd, start, clip_id):
    """A command that types itself out, one character at a time."""
    chars, x, duration = len(cmd), X0 + len(PROMPT) * CW, len(cmd) * PER_CHAR
    widths = ";".join(f"{step * CW:.1f}" for step in range(chars + 1))
    keys = ";".join("1" if step == chars else f"{step / chars:.5f}" for step in range(chars + 1))
    return (
        f'<clipPath id="{clip_id}"><rect x="{x:g}" y="{y - 22}" width="0" height="30">'
        f'<animate attributeName="width" calcMode="discrete" begin="{start:g}s" dur="{duration:g}s" '
        f'fill="freeze" values="{widths}" keyTimes="{keys}"/></rect></clipPath>'
        f'<text x="{x:g}" y="{y}" font-size="{SIZE}" fill="{WHITE}" clip-path="url(#{clip_id})" '
        f'textLength="{chars * CW:.1f}">{esc(cmd)}</text>'
    )


def appear(start, content):
    return (
        f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{start:g}s" dur="0.3s" '
        f'fill="freeze"/>{content}</g>'
    )


def stepped(attribute, events, start, end):
    """One discrete animation stepping through (time, value) pairs."""
    values = ";".join(f"{value:g}" for _, value in events)
    keys = ";".join(
        "1" if index == len(events) - 1 else f"{(moment - start) / (end - start):.5f}"
        for index, (moment, _) in enumerate(events)
    )
    return (
        f'<animate attributeName="{attribute}" calcMode="discrete" begin="{start:g}s" dur="{end - start:g}s" '
        f'fill="freeze" values="{values}" keyTimes="{keys}"/>'
    )


def about_block(ys):
    first, second, third = ys
    highlight = "in public"
    lead = ABOUT[1][: -len(highlight)]
    return (
        text(X0, first, ABOUT[0], TEXT)
        + f'<text x="{X0}" y="{second}" font-size="{SIZE}" textLength="{len(ABOUT[1]) * CW:.1f}">'
        f'<tspan fill="{TEXT}">{esc(lead)}</tspan><tspan fill="{GREEN}">{highlight}</tspan></text>'
        + text(X0, third, ABOUT[2], TEXT)
    )


def log_block(ys, rows):
    out = []
    for y, row in zip(ys, rows):
        out.append(text(X0, y, row["sha"], SOFT))
        out.append(text(X0 + 9 * CW, y, row["repo"], WHITE))
        out.append(text(X0 + 27 * CW, y, row["subject"], TEXT))
        out.append(text(944, y, row["ago"], FAINT, anchor="end", length=False))
    return "".join(out)


def build_session(still, rows):
    x_cmd = X0 + len(PROMPT) * CW
    y_about, y_log, y_idle = 102, 250, 398
    about_ys, log_ys = (136, 168, 200), (284, 316, 348)[: len(rows)]
    first_cmd, log_cmd = "cat about.txt", f"git log -{len(rows)} --oneline"

    prompts = prompt_line(y_about) + prompt_line(y_log) + prompt_line(y_idle)
    outputs = about_block(about_ys) + log_block(log_ys, rows)

    if still:
        body = (
            prompts + command(y_about, first_cmd) + command(y_log, log_cmd) + outputs
            + f'<rect x="{x_cmd:g}" y="{y_idle - 21}" width="{CW:g}" height="27" fill="{GREEN}"/>'
        )
    else:
        t1 = 0.6
        t_out1 = t1 + len(first_cmd) * PER_CHAR + 0.25
        t2 = t_out1 + 0.55
        t_out2 = t2 + len(log_cmd) * PER_CHAR + 0.25

        typed = prompts + typed_command(y_about, first_cmd, t1, "c1") + typed_command(y_log, log_cmd, t2, "c2")
        typed += appear(t_out1, about_block(about_ys))
        typed += "".join(
            appear(t_out2 + index * 0.12, log_block([y], [row]))
            for index, (y, row) in enumerate(zip(log_ys, rows))
        )
        cursor_x = [(t1 + step * PER_CHAR, x_cmd + step * CW) for step in range(len(first_cmd) + 1)]
        cursor_x += [(t_out1, x_cmd)]
        cursor_x += [(t2 + step * PER_CHAR, x_cmd + step * CW) for step in range(len(log_cmd) + 1)]
        cursor_x += [(t_out2, x_cmd)]
        cursor_y = [(t1, y_about - 21), (t_out1, y_log - 21), (t_out2, y_idle - 21)]
        typed += (
            f'<rect x="{x_cmd:g}" y="{y_about - 21}" width="{CW:g}" height="27" fill="{GREEN}">'
            f'{stepped("x", cursor_x, t1, t_out2)}{stepped("y", cursor_y, t1, t_out2)}'
            f'<animate attributeName="opacity" begin="{t_out2 + 0.6:g}s" dur="1s" calcMode="discrete" '
            f'values="1;0" keyTimes="0;0.5" repeatCount="indefinite"/></rect>'
        )
        resting = (
            prompts + command(y_about, first_cmd) + command(y_log, log_cmd) + outputs
            + f'<rect x="{x_cmd:g}" y="{y_idle - 21}" width="{CW:g}" height="27" fill="{GREEN}"/>'
        )
        body = (
            "<style>#resting{display:none}"
            "@media (prefers-reduced-motion:reduce){#resting{display:inline}#typed{display:none}}</style>"
            f'<g id="typed">{typed}</g><g id="resting">{resting}</g>'
        )

    today = dt.datetime.now(dt.timezone.utc)
    note = f"auto-updated {today.day} {today.strftime('%b %Y')}".lower()
    return card(448, "raunak@github:~", body, note)


def build_bar(title):
    shape = "M18 0.5H982A17.5 17.5 0 0 1 999.5 18V45.5H0.5V18A17.5 17.5 0 0 1 18 0.5Z"
    return svg(46, title, (
        f'<path d="{shape}" fill="url(#bg)" stroke="{GREEN}" stroke-opacity="0.35"/>'
        f'{dots()}<text x="500" y="30" text-anchor="middle" font-size="17" fill="{SOFT}">{esc(title)}</text>'
    ))


BARS = {
    "projects": "raunak@github:~/projects",
    "tools": "raunak@github:~/tools",
    "stats": "raunak@github:~/stats",
    "connect": "raunak@github:~/connect",
}


def write(path, content):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def main():
    args = sys.argv[1:]
    if args == ["bars"]:
        for name, title in BARS.items():
            write(os.path.join("assets", f"bar-{name}.svg"), build_bar(title))
        print(f"wrote {len(BARS)} bars")
    elif args[:1] == ["session"] and len(args) >= 2:
        svg_text = build_session("--still" in args, latest_commits())
        write(args[1], svg_text)
        print(f"wrote {args[1]} ({len(svg_text)} bytes)")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
