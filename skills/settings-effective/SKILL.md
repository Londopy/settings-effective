---
name: settings-effective
description: Show the merged Claude Code settings actually in effect and which file decided each key - managed policy, --settings, .claude/settings.local.json, .claude/settings.json, ~/.claude/settings.json and ~/.claude.json - and name the reasons a setting is not applying. Runs from any agent; it inspects Claude Code's files. Use this whenever the user says a Claude Code setting isn't working or isn't taking effect, asks why they are still being prompted for a tool they allowed, asks which settings file wins or where a value is coming from, asks what a settings key does or where it goes, wants their settings files checked for typos or keys in the wrong file, asks whether a project is trusted, or wants to see all their hooks, permission rules or env in one place. Also use it after you edit any settings.json yourself, to confirm the key landed where it applies.
license: MIT
compatibility: Requires Python 3.10+. Read-only. Inspects Claude Code settings; runs from any Agent Skills host.
metadata:
  author: Londopy
  version: "1.1.0"
---

# settings-effective

Claude Code merges up to six settings sources at startup and again on every file change,
and shows the result to nobody: `/status` lists which files loaded, `/permissions` and
`/hooks` each show one slice, and nothing prints a key with the file that decided it.
The failure modes are all silent - a key in a file whose scope does not allow it, a
project value overriding the user value you just edited, an `allow` rule losing to an
`ask` rule from another file, a typo'd key, a file with a stray comma that the harness
skipped whole. This skill prints the merged result with provenance and lists those
reasons.

The script is `scripts/effective.py` next to this file - run it from wherever this skill
was installed (`~/.claude/skills/settings-effective/`, `~/.agents/skills/settings-effective/`,
`~/.cursor/skills/...`, or a project's `.agents/skills/`). Stdlib-only Python 3.10+ and
read-only, always. It carries the docs' settings index (231 keys with the scope each may
be set from); the date is printed in the header and `docs/update_index.py` refreshes it.

## Which host

The subject is always Claude Code's settings: that is the merge with six layers and
scope rules worth making legible. You can run it from Codex, Cursor or Gemini CLI - a
machine with several agents still has one Claude Code configuration to debug - and the
header's `host` line then says which agent you are and that its own config
(`~/.codex/config.toml`, Cursor's settings, `~/.gemini/settings.json`) is a different
merge this tool does not read. For those hosts' MCP servers use `mcp-rollcall`; for
their skills, `skill-rollcall`. If the user asks about a Codex or Cursor *setting*, say
so plainly rather than running this.

## Pick the mode from what the user asked

| The user says | Run |
|---|---|
| "my setting isn't working", "why is X still on" | default, then look at **findings** |
| "why am I still being asked", "I clicked don't ask again" | `--key permissions` |
| "what hooks are running", "where is this hook from" | `--key hooks` |
| "which env vars is Claude getting" | `--key env` |
| "what does X do", "where do I put X" | `--explain X` |
| "check my settings files" / before committing `.claude/settings.json` | `--problems-only`, or `--strict` in CI |
| "what would `--settings foo.json` change" | `--settings foo.json` |

`--project DIR` when they mean another project (it walks up to the nearest `.claude/`
like the harness does). `--full` itemizes every list; `--json` for processing.

## Steps

1. Run it from the project directory the user means. The header lists each layer as
   `loaded`, `absent` or `SKIPPED`; a `SKIPPED` line names the JSON error, and that
   file contributed nothing - lead with that if it is the file they just edited.
   `trust` says whether `~/.claude.json` records the folder as trusted; until it is,
   project `permissions.allow`, `env` and `extraKnownMarketplaces` do not apply.

2. Answer the question first. If they asked about one key, find its row: the value in
   effect and the layer that set it. Then the findings for that key, in this order:
   - **IGNORED** - the key is in a file whose scope does not allow it. The message
     names the files that do. This is the most common "I set it and nothing happened".
   - **warn** - a typo'd key (with a did-you-mean), an `allow` rule that a `deny` or
     `ask` elsewhere outranks, a project rule waiting on trust, `disableAllHooks`
     making the hooks list moot, bypass mode requested but disabled by policy.
   - **note** - a value shadowed by a higher layer (both values are shown), a
     security key where a *stricter* lower value is honored over managed (that one is
     working as designed; say so), an `env` var also exported in the shell, a key the
     harness reads only at startup (`model`, `effortLevel`, `modelSettings`) which an
     edit does not change mid-session - `/model` and `/effort` do.

3. When the fix is "move the key to another file", say which file and whether it
   needs a restart. Keys in `permissions`, `hooks` and `env` hot-reload; the
   restart-only ones are listed above. A managed value cannot be overridden from any
   file the user owns; tell them which managed source it is and stop there.

4. If you edited a settings file yourself this session, rerun with `--key <the key>`
   and quote the row back. That is the confirmation; do not assume the edit applied.

## Related, not overlapping

`/status` says which files loaded; `/permissions` and `/hooks` show and edit their own
slices; `/config` writes user-level keys; `claude doctor` reports files the harness
dropped. None of them show a merged key with its source, or tell you a key is in a
file that cannot set it. `skill-rollcall` does the same job for skills.

## What this cannot do

It reads files; it does not ask the running harness what it loaded, so a managed
source delivered by MDM or the claude.ai console rather than a file is not seen, and
`/status` is the authority there. It does not resolve any other agent's settings -
Codex's `config.toml` layers, Cursor's or Gemini's - only Claude Code's. Its merge rules come from the docs, not the harness
source, so a key with bespoke merging the docs do not describe may be shown per-leaf
when the harness treats it whole. `modelSettings` is resolved per model by the harness
and shown per leaf here. And the index is a snapshot: a key newer than its date shows
as "not a known settings key" until `docs/update_index.py` is rerun.
