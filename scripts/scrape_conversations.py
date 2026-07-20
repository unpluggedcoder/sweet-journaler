#!/usr/bin/env python3
"""Scrape AI-tool conversation histories into a compact digest for work journals.

Reads local storage of: Claude Code, Qoder (IDE/CLI/IDEA/Work share ~/.qoder),
Cursor, GitHub Copilot (VS Code), Aone Copilot, Codex, Cline, OpenCode.
Sources that are absent on the machine are skipped silently (reported in stats).

Output: a markdown digest (default) or JSON, containing per-session user
prompts + the final assistant note, filtered to a local date or month.
The digest is INPUT for journal writing — it is not the journal itself.

Only stdlib is used. Never writes anything outside --out.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------- data model


@dataclass
class Session:
    tool: str
    project: str
    title: str
    start: dt.datetime | None
    end: dt.datetime | None
    user_msgs: list[str] = field(default_factory=list)
    final_assistant: str = ""
    msg_count: int = 0

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "project": self.project,
            "title": self.title,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "user_msgs": self.user_msgs,
            "final_assistant": self.final_assistant,
            "msg_count": self.msg_count,
        }


@dataclass
class Caps:
    msg_chars: int
    final_chars: int
    user_msgs: int
    sessions_per_tool: int


# ---------------------------------------------------------------- time utils


def parse_ts(value) -> dt.datetime | None:
    """Parse ISO string / epoch seconds / epoch ms into a local aware datetime."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            v = value.strip()
            if v.isdigit():
                return parse_ts(int(v))
            ts = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.astimezone()
            return ts.astimezone()
        if isinstance(value, (int, float)):
            if value > 1e12:  # epoch ms
                value = value / 1000.0
            return dt.datetime.fromtimestamp(value).astimezone()
    except (ValueError, OverflowError, OSError):
        return None
    return None


def overlaps(start: dt.datetime | None, end: dt.datetime | None,
             lo: dt.datetime, hi: dt.datetime) -> bool:
    """True if [start, end] intersects [lo, hi). Missing bounds fall back to the other."""
    s = start or end
    e = end or start
    if s is None or e is None:
        return False
    return s < hi and e >= lo


# ---------------------------------------------------------------- text utils

_SKIP_USER_PREFIXES = (
    "<command-", "<local-command", "<system-reminder", "Caveat: The messages below",
    "[Request interrupted", "<task-notification",
)


def clean_text(text: str, limit: int) -> str:
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def keep_user_text(text: str) -> bool:
    t = text.lstrip()
    return bool(t) and not any(t.startswith(p) for p in _SKIP_USER_PREFIXES)


def blocks_text(content) -> str:
    """Extract human text from a message content that may be str or block list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def project_from_path(cwd: str) -> str:
    return Path(cwd).name if cwd else "unknown"


# ------------------------------------------------------- source: CC-style jsonl


def scrape_cc_jsonl(root: Path, tool_label: str, lo, hi, caps: Caps) -> list[Session]:
    """Claude Code / Qoder transcripts: ~/.{claude,qoder}/projects/<slug>/<id>.jsonl.

    Qoder writes both IDE ("external") and CLI ("cli") sessions here; the
    entrypoint field refines the tool label.
    """
    sessions: list[Session] = []
    for jf in sorted(root.glob("*/*.jsonl")):
        try:
            if dt.datetime.fromtimestamp(jf.stat().st_mtime).astimezone() < lo:
                continue  # last write predates the window: nothing in range
            sess = _parse_cc_file(jf, tool_label, lo, hi, caps)
            if sess:
                sessions.append(sess)
        except (OSError, json.JSONDecodeError):
            continue
    return sessions


def _parse_cc_file(jf: Path, tool_label: str, lo, hi, caps: Caps) -> Session | None:
    user_msgs: list[str] = []
    final_assistant = ""
    first = last = None
    cwd = ""
    entrypoint = ""
    count = 0
    with jf.open() as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("isSidechain") or d.get("isMeta"):
                continue
            typ = d.get("type")
            if typ not in ("user", "assistant"):
                continue
            ts = parse_ts(d.get("timestamp"))
            if ts is None or not (lo <= ts < hi):
                continue
            cwd = d.get("cwd") or cwd
            entrypoint = d.get("entrypoint") or entrypoint
            first = first or ts
            last = ts
            text = blocks_text((d.get("message") or {}).get("content"))
            if typ == "user":
                if keep_user_text(text):
                    count += 1
                    if len(user_msgs) < caps.user_msgs:
                        user_msgs.append(clean_text(text, caps.msg_chars))
            else:
                count += 1
                if text.strip():
                    final_assistant = text
    if not user_msgs and not final_assistant:
        return None
    if "qoder" in tool_label.lower():
        tool_label = "Qoder CLI" if entrypoint == "cli" else "Qoder IDE"
    return Session(
        tool=tool_label,
        project=project_from_path(cwd),
        title=user_msgs[0][:80] if user_msgs else "(no user prompt in range)",
        start=first,
        end=last,
        user_msgs=user_msgs,
        final_assistant=clean_text(final_assistant, caps.final_chars),
        msg_count=count,
    )


# ------------------------------------------------------------- source: Cursor


def scrape_cursor(home: Path, lo, hi, caps: Caps) -> list[Session]:
    """Cursor chats: globalStorage/state.vscdb -> cursorDiskKV 'composerData:*'."""
    db = home / "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
    if not db.exists():
        return []
    sessions: list[Session] = []
    con = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    try:
        rows = con.execute(
            "SELECT value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
        ).fetchall()
    finally:
        con.close()
    for (raw,) in rows:
        try:
            d = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        start = parse_ts(d.get("createdAt"))
        end = parse_ts(d.get("lastUpdatedAt")) or start
        if not overlaps(start, end, lo, hi):
            continue
        user_msgs: list[str] = []
        final_assistant = ""
        count = 0
        for bubble in d.get("conversation") or []:
            text = bubble.get("text") or ""
            if not text.strip():
                continue
            count += 1
            if bubble.get("type") == 1:  # 1 = user, 2 = assistant
                if keep_user_text(text) and len(user_msgs) < caps.user_msgs:
                    user_msgs.append(clean_text(text, caps.msg_chars))
            else:
                final_assistant = text
        if not user_msgs and not final_assistant:
            continue
        sessions.append(Session(
            tool="Cursor",
            project=d.get("name") or "unknown",
            title=(d.get("name") or (user_msgs[0] if user_msgs else "untitled"))[:80],
            start=start,
            end=end,
            user_msgs=user_msgs,
            final_assistant=clean_text(final_assistant, caps.final_chars),
            msg_count=count,
        ))
    return sessions


# ----------------------------------------------- source: GitHub Copilot (VS Code)


def scrape_copilot(home: Path, lo, hi, caps: Caps) -> list[Session]:
    """Copilot Chat sessions: Code/User/workspaceStorage/*/chatSessions/*.{jsonl,json}."""
    ws = home / "Library/Application Support/Code/User/workspaceStorage"
    if not ws.exists():
        return []
    sessions: list[Session] = []
    for f in list(ws.glob("*/chatSessions/*.jsonl")) + list(ws.glob("*/chatSessions/*.json")):
        try:
            if dt.datetime.fromtimestamp(f.stat().st_mtime).astimezone() < lo:
                continue
            first_line = f.open().readline()
            d = json.loads(first_line)
            state = d.get("v") if isinstance(d.get("v"), dict) else d
            start = parse_ts(state.get("creationDate"))
            end = parse_ts(f.stat().st_mtime)
            if not overlaps(start, end, lo, hi):
                continue
            user_msgs: list[str] = []
            final_assistant = ""
            for req in state.get("requests") or []:
                msg = req.get("message")
                text = msg.get("text", "") if isinstance(msg, dict) else str(msg or "")
                if keep_user_text(text) and len(user_msgs) < caps.user_msgs:
                    user_msgs.append(clean_text(text, caps.msg_chars))
                for part in req.get("response") or []:
                    val = part.get("value") if isinstance(part, dict) else None
                    if isinstance(val, str) and val.strip():
                        final_assistant = val
            if not user_msgs:
                continue
            sessions.append(Session(
                tool="GitHub Copilot",
                project=state.get("responderUsername") or "unknown",
                title=user_msgs[0][:80],
                start=start,
                end=end,
                user_msgs=user_msgs,
                final_assistant=clean_text(final_assistant, caps.final_chars),
                msg_count=len(state.get("requests") or []),
            ))
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    return sessions


# ------------------------------------------------- source: GitHub Copilot CLI


def scrape_copilot_cli(home: Path, lo, hi, caps: Caps) -> list[Session]:
    """GitHub Copilot CLI (standalone `copilot`): ~/.copilot/session-store.db.

    sessions(id, cwd, summary, created_at, updated_at) + turns(session_id,
    turn_index, user_message, assistant_response, timestamp), ISO-Z timestamps.
    """
    db = home / ".copilot/session-store.db"
    if not db.exists():
        return []
    sessions: list[Session] = []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        srows = con.execute(
            "SELECT id, cwd, summary, created_at, updated_at FROM sessions"
        ).fetchall()
        for sid, cwd, summary, created, updated in srows:
            start, end = parse_ts(created), parse_ts(updated)
            if not overlaps(start, end, lo, hi):
                continue
            user_msgs: list[str] = []
            final_assistant = ""
            count = 0
            first = last = None
            for user_msg, resp, ts in con.execute(
                "SELECT user_message, assistant_response, timestamp FROM turns"
                " WHERE session_id = ? ORDER BY turn_index", (sid,),
            ):
                tts = parse_ts(ts)
                if tts is not None and not (lo <= tts < hi):
                    continue  # session spans days; keep only in-window turns
                count += 1
                first = first or tts
                last = tts or last
                if user_msg and keep_user_text(user_msg) and len(user_msgs) < caps.user_msgs:
                    user_msgs.append(clean_text(user_msg, caps.msg_chars))
                if resp and resp.strip():
                    final_assistant = resp
            if not user_msgs and not final_assistant:
                continue
            sessions.append(Session(
                tool="GitHub Copilot CLI",
                project=project_from_path(cwd or ""),
                title=(summary or (user_msgs[0] if user_msgs else "untitled"))[:80],
                start=first or start,
                end=last or end,
                user_msgs=user_msgs,
                final_assistant=clean_text(final_assistant, caps.final_chars),
                msg_count=count,
            ))
    except sqlite3.Error as exc:
        print(f"[scrape] copilot-cli: ERROR {exc}", file=sys.stderr)
    finally:
        con.close()
    return sessions


# --------------------------------------------------------- source: Aone Copilot


def scrape_aone(home: Path, lo, hi, caps: Caps) -> list[Session]:
    """Aone Copilot (JetBrains): ~/.aone_copilot/kv_storage entries <uuid>-{user,bot}."""
    base = home / ".aone_copilot/kv_storage"
    index = base / "index.json"
    if not index.exists():
        return []
    try:
        entries = json.loads(index.read_text()).get("entries") or {}
    except (json.JSONDecodeError, OSError):
        return []
    by_session: dict[str, list[dict]] = {}
    for key, meta in entries.items():
        if not (key.endswith("-user") or key.endswith("-bot")):
            continue
        blob_path = base / "data" / str(meta.get("fileName", ""))
        if not blob_path.exists():
            continue
        try:
            value = json.loads(blob_path.read_text()).get("value")
            msg = json.loads(value) if isinstance(value, str) else value
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(msg, dict):
            continue
        ts = parse_ts(msg.get("date"))
        if ts is None or not (lo <= ts < hi):
            continue
        sid = msg.get("storeSessionId") or msg.get("taskSessionId") or "aone"
        msg["_ts"] = ts
        by_session.setdefault(sid, []).append(msg)
    sessions: list[Session] = []
    for sid, msgs in by_session.items():
        msgs.sort(key=lambda m: m["_ts"])
        user_msgs = []
        final_assistant = ""
        for m in msgs:
            text = str(m.get("content") or "")
            text = re.sub(r"<tool_calls>.*?(</tool_calls>|$)", "", text, flags=re.S)
            if m.get("role") == "user":
                if keep_user_text(text) and len(user_msgs) < caps.user_msgs:
                    user_msgs.append(clean_text(text, caps.msg_chars))
            elif text.strip():
                final_assistant = text
        if not user_msgs and not final_assistant:
            continue
        sessions.append(Session(
            tool="Aone Copilot",
            project=sid[:20],
            title=user_msgs[0][:80] if user_msgs else "(assistant only)",
            start=msgs[0]["_ts"],
            end=msgs[-1]["_ts"],
            user_msgs=user_msgs,
            final_assistant=clean_text(final_assistant, caps.final_chars),
            msg_count=len(msgs),
        ))
    return sessions


# --------------------------------------------------------------- source: Codex


def scrape_codex(home: Path, lo, hi, caps: Caps) -> list[Session]:
    """Codex CLI: sessions/rollouts jsonl if present, else threads table in sqlite."""
    sessions: list[Session] = []
    for jf in (home / ".codex/sessions").glob("**/*.jsonl"):
        try:
            if dt.datetime.fromtimestamp(jf.stat().st_mtime).astimezone() < lo:
                continue
            sess = _parse_codex_rollout(jf, lo, hi, caps)
            if sess:
                sessions.append(sess)
        except OSError:
            continue
    db = home / ".codex/state_5.sqlite"
    if db.exists():
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            rows = con.execute(
                "SELECT title, first_user_message, preview, cwd, created_at, updated_at"
                " FROM threads"
            ).fetchall()
            con.close()
            for title, first_msg, preview, cwd, created, updated in rows:
                start, end = parse_ts(created), parse_ts(updated)
                if not overlaps(start, end, lo, hi):
                    continue
                user_msgs = [clean_text(first_msg, caps.msg_chars)] if first_msg else []
                sessions.append(Session(
                    tool="Codex",
                    project=project_from_path(cwd or ""),
                    title=(title or (user_msgs[0] if user_msgs else "untitled"))[:80],
                    start=start,
                    end=end,
                    user_msgs=user_msgs,
                    final_assistant=clean_text(preview or "", caps.final_chars),
                    msg_count=len(user_msgs),
                ))
        except sqlite3.Error:
            pass
    return sessions


def _parse_codex_rollout(jf: Path, lo, hi, caps: Caps) -> Session | None:
    user_msgs: list[str] = []
    final_assistant = ""
    first = last = None
    with jf.open() as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = parse_ts(d.get("timestamp"))
            payload = d.get("payload") or d
            role = payload.get("role") or payload.get("type")
            text = blocks_text(payload.get("content"))
            if ts and not (lo <= ts < hi):
                continue
            if role == "user" and keep_user_text(text):
                first = first or ts
                last = ts or last
                if len(user_msgs) < caps.user_msgs:
                    user_msgs.append(clean_text(text, caps.msg_chars))
            elif role in ("assistant", "agent_message") and text.strip():
                final_assistant = text
    if not user_msgs:
        return None
    return Session(
        tool="Codex", project=jf.parent.name, title=user_msgs[0][:80],
        start=first, end=last, user_msgs=user_msgs,
        final_assistant=clean_text(final_assistant, caps.final_chars),
        msg_count=len(user_msgs),
    )


# ---------------------------------------------------------------- source: Cline


def scrape_cline(home: Path, lo, hi, caps: Caps) -> list[Session]:
    """Cline: <IDE>/User/globalStorage/saoudrizwan.claude-dev/tasks/<ms>/."""
    sessions: list[Session] = []
    for ide in ("Code", "Cursor", "Qoder"):
        tasks = (home / "Library/Application Support" / ide /
                 "User/globalStorage/saoudrizwan.claude-dev/tasks")
        if not tasks.exists():
            continue
        for task_dir in tasks.iterdir():
            start = parse_ts(task_dir.name)
            hist = task_dir / "api_conversation_history.json"
            if start is None or not hist.exists():
                continue
            end = parse_ts(hist.stat().st_mtime)
            if not overlaps(start, end, lo, hi):
                continue
            try:
                msgs = json.loads(hist.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            user_msgs: list[str] = []
            final_assistant = ""
            for m in msgs if isinstance(msgs, list) else []:
                text = blocks_text(m.get("content"))
                text = re.sub(r"<environment_details>.*?</environment_details>", "", text, flags=re.S)
                text = re.sub(r"</?task>", "", text)
                if m.get("role") == "user":
                    if keep_user_text(text) and len(user_msgs) < caps.user_msgs:
                        user_msgs.append(clean_text(text, caps.msg_chars))
                elif text.strip():
                    final_assistant = text
            if not user_msgs:
                continue
            sessions.append(Session(
                tool="Cline", project=ide, title=user_msgs[0][:80],
                start=start, end=end, user_msgs=user_msgs,
                final_assistant=clean_text(final_assistant, caps.final_chars),
                msg_count=len(msgs),
            ))
    return sessions


# ------------------------------------------------------------- source: OpenCode


def scrape_opencode(home: Path, lo, hi, caps: Caps) -> list[Session]:
    """OpenCode: ~/.local/share/opencode/storage/session + message trees."""
    storage = home / ".local/share/opencode/storage"
    if not storage.exists():
        return []
    sessions: list[Session] = []
    for info in storage.glob("session/info/*.json"):
        try:
            d = json.loads(info.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        t = d.get("time") or {}
        start, end = parse_ts(t.get("created")), parse_ts(t.get("updated"))
        if not overlaps(start, end, lo, hi):
            continue
        sid = d.get("id") or info.stem
        user_msgs: list[str] = []
        final_assistant = ""
        for mf in sorted(storage.glob(f"session/message/{sid}/*.json")):
            try:
                m = json.loads(mf.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            parts = m.get("parts") or []
            text = "\n".join(p.get("text", "") for p in parts
                             if isinstance(p, dict) and p.get("type") == "text")
            text = text or blocks_text(m.get("content"))
            if m.get("role") == "user":
                if keep_user_text(text) and len(user_msgs) < caps.user_msgs:
                    user_msgs.append(clean_text(text, caps.msg_chars))
            elif text.strip():
                final_assistant = text
        if not user_msgs:
            continue
        sessions.append(Session(
            tool="OpenCode", project=d.get("title", "unknown")[:40],
            title=(d.get("title") or user_msgs[0])[:80],
            start=start, end=end, user_msgs=user_msgs,
            final_assistant=clean_text(final_assistant, caps.final_chars),
            msg_count=len(user_msgs),
        ))
    return sessions


# ------------------------------------------------------------------ rendering


def render_markdown(sessions: list[Session], label: str) -> str:
    lines = [f"# Conversation digest — {label}", ""]
    if not sessions:
        lines.append("_No AI conversations found in this period._")
        return "\n".join(lines)
    by_tool: dict[str, list[Session]] = {}
    for s in sessions:
        by_tool.setdefault(s.tool, []).append(s)
    for tool in sorted(by_tool):
        lines.append(f"## {tool}")
        for s in sorted(by_tool[tool], key=lambda x: (x.project, x.start or dt.datetime.min.astimezone())):
            span = ""
            if s.start:
                span = s.start.strftime("%m-%d %H:%M")
                if s.end and s.end != s.start:
                    span += "–" + s.end.strftime("%H:%M" if s.end.date() == s.start.date() else "%m-%d %H:%M")
            lines.append(f"### [{s.project}] {s.title}  ({span}, {s.msg_count} msgs)")
            for m in s.user_msgs:
                lines.append(f"- USER: {m}")
            if s.final_assistant:
                lines.append(f"- FINAL ASSISTANT NOTE: {s.final_assistant}")
            lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------------ main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--date", help="local day YYYY-MM-DD")
    grp.add_argument("--month", help="local month YYYY-MM")
    ap.add_argument("--home", default=str(Path.home()),
                    help="root under which tool storage is resolved (sandbox/testing)")
    ap.add_argument("--out", help="write digest to this file (default: stdout)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    ap.add_argument("--max-msg-chars", type=int, default=None)
    ap.add_argument("--max-final-chars", type=int, default=None)
    ap.add_argument("--max-user-msgs", type=int, default=None)
    ap.add_argument("--max-sessions-per-tool", type=int, default=200)
    args = ap.parse_args()

    if args.date:
        day = dt.date.fromisoformat(args.date)
        lo = dt.datetime.combine(day, dt.time.min).astimezone()
        hi = lo + dt.timedelta(days=1)
        label = f"{args.date} (daily)"
        caps = Caps(args.max_msg_chars or 400, args.max_final_chars or 700,
                    args.max_user_msgs or 30, args.max_sessions_per_tool)
    else:
        year, month = map(int, args.month.split("-"))
        lo = dt.datetime(year, month, 1).astimezone()
        hi = (dt.datetime(year + 1, 1, 1) if month == 12
              else dt.datetime(year, month + 1, 1)).astimezone()
        label = f"{args.month} (monthly)"
        caps = Caps(args.max_msg_chars or 200, args.max_final_chars or 300,
                    args.max_user_msgs or 12, args.max_sessions_per_tool)

    home = Path(args.home).expanduser()
    sources = [
        ("Claude Code", lambda: scrape_cc_jsonl(home / ".claude/projects", "Claude Code", lo, hi, caps)),
        ("Qoder", lambda: scrape_cc_jsonl(home / ".qoder/projects", "Qoder", lo, hi, caps)),
        ("Cursor", lambda: scrape_cursor(home, lo, hi, caps)),
        ("GitHub Copilot", lambda: scrape_copilot(home, lo, hi, caps)),
        ("GitHub Copilot CLI", lambda: scrape_copilot_cli(home, lo, hi, caps)),
        ("Aone Copilot", lambda: scrape_aone(home, lo, hi, caps)),
        ("Codex", lambda: scrape_codex(home, lo, hi, caps)),
        ("Cline", lambda: scrape_cline(home, lo, hi, caps)),
        ("OpenCode", lambda: scrape_opencode(home, lo, hi, caps)),
    ]
    sessions: list[Session] = []
    stats: list[str] = []
    for name, fn in sources:
        try:
            found = fn()[: caps.sessions_per_tool]
        except Exception as exc:  # a broken source must never kill the digest
            print(f"[scrape] {name}: ERROR {exc}", file=sys.stderr)
            continue
        stats.append(f"{name}={len(found)}")
        sessions.extend(found)
    print(f"[scrape] sessions per source: {', '.join(stats)}", file=sys.stderr)

    output = (json.dumps([s.to_dict() for s in sessions], ensure_ascii=False, indent=1)
              if args.json else render_markdown(sessions, label))
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"[scrape] digest written to {args.out}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
