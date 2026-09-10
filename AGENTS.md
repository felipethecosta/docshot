# Working in this repository

A marketplace of small tools, each self-contained under `plugins/<name>/`. There
is no shared runtime and no build step: a plugin is files, and installing one
must never require touching another.

Read the tool's own `AGENTS.md` before working on it — `plugins/docshot/AGENTS.md`
for docshot. This file only covers the repository itself.

## Layout rules

- Everything a tool needs lives inside its plugin directory: code, skills, commands, examples, and its `AGENTS.md`.
- `.claude-plugin/marketplace.json` lists the plugins; `plugins/<name>/.claude-plugin/plugin.json` describes one. Both are plain JSON with no computed values — keep the versions in the two files in step.
- `codex/prompts/<name>.md` mirrors a skill for people on Codex. If you change the procedure in a skill, change the prompt in the same commit or delete it.
- `install.sh` installs into exactly three places: `~/.local/bin`, `~/.claude/skills`, `~/.codex/prompts`. Do not extend it to write anywhere else, and never make it install everything by default.

## What belongs in a skill, and what does not

A skill is a procedure someone follows: the order of the steps, what to check
before moving on, what a warning means. An `AGENTS.md` is the contract: the
vocabulary, the configuration reference, and the traps that cost a debugging
session. Neither is a place for settings, credentials, machine paths or hooks.

Write down what you had to learn the hard way. A model can read the source; it
cannot know that a click on an icon-only trigger silently does nothing.

## Public repository

No secrets, no corporate templates, no client screenshots, no customer names,
no internal hostnames — in the files or in the git history. Credentials in
examples are always `${VAR}` references.
