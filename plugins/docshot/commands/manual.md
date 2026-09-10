---
description: Turn a running web application into an operation manual (.docx) using docshot — probe the screens, capture, write, build.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

## Where docshot is

- On PATH: !`command -v docshot || echo "not on PATH"`
- In this plugin: `${CLAUDE_PLUGIN_ROOT}/bin/docshot`
- Project config: !`ls docshot.config.json 2>/dev/null || echo "no docshot.config.json here — run: docshot init"`

## What the user asked for

$ARGUMENTS

## How to proceed

Follow the `write-manual` skill that ships with this plugin. In short:

1. `docshot inspect` — what the .docx template offers.
2. `docshot probe <route>` — what each screen offers, as steps to paste. Never guess a button label.
3. Write the shots into `docshot.config.json`.
4. `docshot check` — fix every error before opening a browser.
5. `docshot capture --only <one>` — look at that screenshot before running the batch.
6. `docshot capture` — read the warnings; "the screen did not change" is a failure, not a note.
7. Write the Markdown describing what the screenshots actually show.
8. `docshot build` (or `--single`).

If `docshot` is not on PATH, call it as `${CLAUDE_PLUGIN_ROOT}/bin/docshot`.
