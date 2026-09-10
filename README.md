# temis-tools

Tools I build at work and share with the team, packaged so you install only the
ones you want. It is a Claude Code marketplace, a set of Codex prompts, and a
plain `install.sh` — the same content reachable three ways.

| Plugin | What it does |
| --- | --- |
| [`docshot`](plugins/docshot) | Turn a running web application into an operation manual: screenshots driven by a config file, and `.docx` generated inside your own corporate template |

## Install — Claude Code

```
/plugin marketplace add felipethecosta/docshot
/plugin install docshot@temis-tools
```

`/plugin` then lists what is available and installs only what you pick. Each
plugin brings its own skills and commands; nothing else is touched.

## Install — Codex, or no plugin system at all

```bash
git clone https://github.com/felipethecosta/docshot.git
cd docshot
./install.sh            # menu: cli, skill, codex
./install.sh --list     # or install straight: ./install.sh cli codex
```

- `cli` symlinks the tool into `~/.local/bin`
- `skill` copies the Claude Code skill into `~/.claude/skills`
- `codex` copies the prompt into `~/.codex/prompts`, where it becomes `/write-manual`

Nothing is installed without you asking for it, and nothing is overwritten
outside those three paths.

## What is in here

```
.claude-plugin/marketplace.json   the marketplace Claude Code reads
plugins/<name>/                   one plugin per tool
  .claude-plugin/plugin.json        its manifest
  skills/ commands/                 what it teaches the assistant
  AGENTS.md                         the working contract for that tool
codex/prompts/                    the same procedures as Codex prompts
install.sh                        manual install, pick what you want
```

## Adding a tool to this repo

1. `plugins/<name>/` with a `.claude-plugin/plugin.json` (name, description, version, author).
2. `skills/<skill>/SKILL.md` for a procedure the assistant should follow, `commands/<cmd>.md` for a slash command, and an `AGENTS.md` with the contract — the traps, the vocabulary, the loop that works. Write down what cost you a debugging session; that is the part no model can guess.
3. Add an entry to `.claude-plugin/marketplace.json` and a line to the table above.
4. If it makes sense outside Claude Code, add a matching `codex/prompts/<name>.md` and a case in `install.sh`.

Keep secrets, corporate templates and client screenshots out of here — this
repository is public.
