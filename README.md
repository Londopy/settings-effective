<div align="center">

# 🧭 settings-effective

**The Claude Code settings actually in effect — every key, and which file decided it. Plus the reasons the one you set isn't. Runs from Claude Code, Codex, Cursor or any Agent Skills host.**

[![CI](https://github.com/Londopy/settings-effective/actions/workflows/ci.yml/badge.svg)](https://github.com/Londopy/settings-effective/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)](skills/settings-effective/scripts/effective.py)
[![Agent Skills](https://img.shields.io/badge/Agent_Skills-spec-111)](https://agentskills.io)
[![Runs from](https://img.shields.io/badge/runs_from-Claude_Code_%7C_Codex_%7C_Cursor_%7C_Gemini_CLI_%7C_Copilot_%7C_OpenCode-D97757)](#install)
[![Platform](https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey)](#install)

<img src="docs/demo.png" alt="settings-effective output: the six layers, each effective key with its source, and the findings that explain a setting that is not applying" width="900">

<sub>Part of the rollcall family — tools that make what your coding agent does silently legible: [skill-rollcall](https://github.com/Londopy/skill-rollcall) · [mcp-rollcall](https://github.com/Londopy/mcp-rollcall) · **settings-effective** · [git-attribution](https://github.com/Londopy/git-attribution) · all four: [agent-skills](https://github.com/Londopy/agent-skills)</sub>

</div>

---

You put `"model": "opus"` in `~/.claude/settings.json` and Claude keeps using Sonnet. You clicked "Yes, don't ask again" and it asks again. You added a hook and nothing fires. Claude Code merges six settings sources — managed policy, `--settings`, `.claude/settings.local.json`, `.claude/settings.json`, `~/.claude/settings.json` and a few keys from `~/.claude.json` — and shows the result to nobody. `/status` tells you which files loaded. Nothing tells you which file *won*, or that the key you set is in a file that isn't allowed to set it.

`settings-effective` prints the merged result with the deciding file next to every key, and lists the silent reasons a setting isn't applying. It runs as a skill (`/settings-effective`, or just say "why isn't my setting working") and as a plain CLI.

## What it does

| Mode | Question it answers |
|---|---|
| default | Which files loaded (and which were **skipped** for bad JSON), is this folder **trusted**, and for every effective key: its value and **which layer set it**. Permission rules and hooks itemized per source. |
| findings | Why isn't it applying? Key in a file whose **scope can't set it**; value **shadowed** by a higher layer; `allow` rule **outranked** by `ask`/`deny`; **typo'd** key with a did-you-mean; project rules **waiting on trust**; `disableAllHooks`; bypass mode disabled by policy; a **restart-only** key edited mid-session. |
| `--key permissions` | One subtree, every list itemized with sources. Also `hooks`, `env`, or any key. |
| `--explain KEY` | What the key does, its topic, and which files may set it — from the docs' index, 231 keys. |
| `--settings FILE\|JSON` | What `claude --settings …` would change. |
| `--problems-only`, `--strict` | Findings only; non-zero exit on any ignored key or skipped file, for CI on a committed `.claude/settings.json`. |

Read-only, always.

## Install

One layout — `skills/settings-effective/SKILL.md` + `scripts/effective.py` — is the [Agent Skills](https://agentskills.io) standard, so the same folder works in every host. The subject is always Claude Code's settings; a machine that runs several agents still has one Claude Code configuration to debug, and this reads it from whichever agent you're in.

**`skills` CLI** — any of 79 agents (global; `--copy` because symlinks need Developer Mode on Windows):

```bash
npx skills add Londopy/settings-effective -g --copy                  # picks the agents it finds
npx skills add Londopy/settings-effective -g --copy -a codex -a cursor
npx skills add Londopy/settings-effective -g --copy --all            # every agent, no prompts
```

**Claude Code plugin** (in an interactive `claude` session):

```
/plugin marketplace add Londopy/settings-effective
/plugin install settings-effective@settings-effective
```

**By hand** — copy the folder into the host's skills directory:

```bash
git clone https://github.com/Londopy/settings-effective
cp -r settings-effective/skills/settings-effective ~/.claude/skills/          # Claude Code
cp -r settings-effective/skills/settings-effective ~/.agents/skills/          # Codex, Cline, Zed, Warp (universal)
cp -r settings-effective/skills/settings-effective ~/.cursor/skills/          # Cursor
cp -r settings-effective/skills/settings-effective ~/.gemini/skills/          # Gemini CLI
cp -r settings-effective/skills/settings-effective ~/.copilot/skills/         # GitHub Copilot
cp -r settings-effective/skills/settings-effective ~/.config/opencode/skills/ # OpenCode
```

## Usage

### From your agent

Say what you'd naturally say — "why is my model setting ignored?", "why does it still ask me about `npm test`?", "which hooks are actually running?", "where do I put `autoMode`?" — or type `/settings-effective`. Claude runs it from the project you're in, answers the question about your key first, then the findings that touch it. After Claude edits a settings file itself, it reruns with `--key` to confirm the edit landed where it applies.

### As a CLI

Stdlib-only Python, nothing in it depends on any particular agent (the header's `host` line says which one you ran it from):

```bash
python ~/.claude/skills/settings-effective/scripts/effective.py
python ~/.claude/skills/settings-effective/scripts/effective.py --key permissions
python ~/.claude/skills/settings-effective/scripts/effective.py --explain modelPicker
```

| Flag | Effect |
|---|---|
| `--project DIR` | Project to resolve (default: cwd; walks up to the nearest `.claude/` or the git root) |
| `--settings FILE\|JSON` | Add a `--settings` layer, as the `claude` CLI would |
| `--key K` | Only `K` and its subkeys, every list itemized |
| `--explain K` | Describe a key from the index |
| `--problems-only` | Findings, no table |
| `--full` | Itemize every list, don't truncate values |
| `--strict` | Exit 1 on any error-level finding |
| `--json` | Machine-readable |

## How it merges

The same way the [docs](https://code.claude.com/docs/en/settings#settings-precedence) say the harness does:

- **Precedence**, highest first: managed → `--settings` → local → project → user. Managed is `managed-settings.json` plus `managed-settings.d/*.json` in alphabetical order, from `/Library/Application Support/ClaudeCode`, `/etc/claude-code` or `C:\Program Files\ClaudeCode`.
- **Scalars** override. **Lists** union across layers (`permissions.allow`, `hooks.PreToolUse`, `sandbox.network.allowedDomains`…), each entry remembering its source. **Objects** merge per leaf, so `attribution.commit` from one file and `attribution.pr` from another both apply. `fallbackModel` and `modelPicker` are taken whole from the highest layer; `statusLine` and `agent` are one value, not a bag of keys.
- **Scope**: each key's index entry says which files may set it. `modelPicker` and `autoMode` are *User or managed*; `requiredMinimumVersion` is *Managed*; `copyOnSelect` is *Global config* (`~/.claude.json` only). A key in a file outside its scope is reported IGNORED and left out of the merge — because that's what the harness does.
- **Security exceptions**: `disableClaudeAiConnectors: true`, `isolatePeerMachines: true`, `enableArtifact: false`, a lower `maxEffortLevel`, a stricter `crossSessionInbound` from a project file, `remoteControlAtStartup: false` from a project file, and `useAutoModeDuringPlan` / `syncClaudeAiSkills` / `syncClaudeAiPlugins: false` from user or local — all honored over a looser managed value, and reported as a note so you know it's by design.
- **Trust**: `~/.claude.json` records whether you accepted the trust dialog for this folder. Until you have, project `permissions.allow`, `env` and `extraKnownMarketplaces` don't apply; `deny` and `ask` do. The legacy per-project `allowedTools` list in the same file is shown too.

## What it catches

| Finding | Severity | Example |
|---|---|---|
| Key in a file whose scope can't set it | IGNORED | `autoMode` in `.claude/settings.json` — only user or managed may set it |
| File isn't valid JSON | IGNORED | a trailing comma in `settings.local.json`; the whole file is skipped |
| `allow` outranked by `ask` / `deny` | warn | `"Bash(npm test)"` allowed in user, asked in project — you'll be prompted |
| Unknown key | warn | `permisions` → *did you mean `permissions`?*; top-level `disableBypassPermissionsMode` → *`permissions.disableBypassPermissionsMode`* |
| Project rule / env before trust | warn | `permissions.allow` in a folder you haven't trusted |
| Rule not `Tool` / `Tool(spec)` shaped | warn | `"npm test"` |
| `disableAllHooks` with hooks defined | warn | none of them run |
| Shadowed value | note | user `opus`, project `sonnet` → both shown |
| Security exception applied | note | project `disableClaudeAiConnectors: true` over managed `false` |
| Restart-only key | note | `model`, `effortLevel`, `modelSettings` — use `/model`, `/effort` |
| `env` var also in the shell | note | which applies is decided per variable |

## The index

`--explain` and the scope checks come from an embedded copy of the [settings reference](https://code.claude.com/docs/en/settings-reference) index — 231 keys with scope, topic and a one-line description, dated in the report header. `python docs/update_index.py` regenerates it from the live docs and prints which keys were added or removed; CI regenerates from a saved snapshot to make sure the parser still matches the page layout.

## Related, not overlapping

`/status` lists which files loaded. `/permissions` and `/hooks` show and edit their slice. `/config` writes user-level keys. `claude doctor` reports dropped files. None of them show a merged key with its source or tell you a key is somewhere it can't apply. [`skill-rollcall`](https://github.com/Londopy/skill-rollcall) does the same job for skills.

## What it cannot do

- **It reads Claude Code's settings only.** Codex's `config.toml` layers, Cursor's settings and Gemini's `settings.json` are different merges; under those hosts the header says so. Their MCP servers and skills are covered by [mcp-rollcall](https://github.com/Londopy/mcp-rollcall) and [skill-rollcall](https://github.com/Londopy/skill-rollcall).

- **It reads files, not the running harness.** Managed policy delivered by MDM or the claude.ai console rather than a file isn't visible here; `/status` is the authority for that.
- **Merge rules come from the docs, not the source.** A key with bespoke merging the docs don't describe is shown per leaf. `modelSettings` is resolved per model by the harness.
- **The index is a snapshot.** A key newer than its date shows as unknown until `update_index.py` is rerun.
