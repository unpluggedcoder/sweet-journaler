# Conversation source storage map (macOS)

Where each AI tool stores chat history, as verified on this machine (2026-07).
`scripts/scrape_conversations.py` implements all of these; this doc is for
debugging when a source returns 0 sessions unexpectedly, or for extending the
scraper when a tool changes its format.

All paths are relative to `$HOME` (overridable with `--home` for sandbox tests).

## Claude Code CLI — verified ✅

- Path: `.claude/projects/<path-slug>/<session-uuid>.jsonl`
- One JSON object per line. Relevant: `type` (`user`/`assistant`), `message.content`
  (string or block list; only `type: "text"` blocks are human text), `timestamp`
  (ISO 8601 Z), `cwd`, `isSidechain` (skip true — subagent chatter), `isMeta`.
- User lines whose text starts with `<command-`, `<local-command`,
  `<system-reminder`, or "Caveat:" are harness noise, not the user.

## Qoder IDE + Qoder CLI (also IDEA/Work surfaces) — verified ✅

- Path: `.qoder/projects/<path-slug>/<session-uuid>.jsonl`
- Same schema as Claude Code, plus `entrypoint`: `cli` → Qoder CLI,
  `external` → Qoder IDE. Extra line types (`token-stats`, `ai-title`,
  `file-history-snapshot`, `last-prompt`) are skipped.
- The IDE's `state.vscdb` (`aicoding-chat-*` keys) holds only UI view state —
  the transcript itself is always in `~/.qoder/projects/`.

## Cursor — verified ✅

- Path: `Library/Application Support/Cursor/User/globalStorage/state.vscdb`
- SQLite, table `cursorDiskKV`, keys `composerData:<uuid>` → JSON with
  `conversation[]` (bubble `type` 1=user / 2=assistant, `text`), `createdAt` /
  `lastUpdatedAt` (epoch ms), `name`.
- Bubbles carry no per-message timestamp → a session is included when its
  [createdAt, lastUpdatedAt] span overlaps the requested window.
- Open read-only (`mode=ro&immutable=1`) — Cursor may hold the db open.

## GitHub Copilot CLI (standalone `copilot`) — verified ✅

- Path: `.copilot/session-store.db` (SQLite)
- `sessions(id, cwd, summary, created_at, updated_at)` +
  `turns(session_id, turn_index, user_message, assistant_response, timestamp)`;
  timestamps are ISO-8601 Z strings. A session can span days — the scraper
  filters at turn level.
- Richer per-session data also exists under `.copilot/session-state/<id>/`
  (events.jsonl, session.db) but the turns table is sufficient.

## GitHub Copilot (VS Code) — verified ✅ (format), little data on this machine

- Path: `Library/Application Support/Code/User/workspaceStorage/*/chatSessions/*.jsonl`
  (first line: `{"kind":0,"v":{creationDate, requests[], ...}}`); older builds
  used plain `*.json` with the same state object at top level.
- `requests[].message.text` = user prompt; `requests[].response[].value` = reply.

## Aone Copilot (JetBrains plugin) — verified ✅

- Path: `.aone_copilot/kv_storage/index.json` + `data/<hash>.json`
- `index.json` → `entries`: keys like `<uuid>-user` / `<uuid>-bot` map to
  `{fileName}`. Each data blob has `value` = JSON-encoded message:
  `content`, `role` (`user`/`assistant`), `date`, `storeSessionId`.
- Bot content may embed `<tool_calls>…` XML — stripped by the scraper.
- Entries expire (`expireTime`) — old months may be gone; scrape promptly.

## Codex CLI — installed, empty on this machine (2026-07)

- New builds: `threads` table in `.codex/state_5.sqlite` (`title`,
  `first_user_message`, `preview`, `cwd`, epoch-second timestamps).
- Older builds: `.codex/sessions/**/*.jsonl` rollout files (also parsed).

## Cline — not installed here; supported via known path

- Path: `Library/Application Support/{Code,Cursor,Qoder}/User/globalStorage/`
  `saoudrizwan.claude-dev/tasks/<epoch-ms>/api_conversation_history.json`
- Standard `{role, content:[{type:"text",text}]}` list; `<task>` and
  `<environment_details>` wrappers stripped.

## OpenCode — not installed here; supported via known path

- Path: `.local/share/opencode/storage/session/info/<id>.json` (+
  `session/message/<id>/*.json` with `parts[]` text).

## Absence handling

Every source returns `[]` when its path is missing — a machine with only two
tools installed just yields fewer sections. Per-source session counts are
always printed to stderr (`[scrape] sessions per source: …`) so you can see at
a glance which sources contributed.
