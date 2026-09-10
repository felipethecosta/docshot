Turn a running web application into an operation manual (.docx) with docshot.

Capture first, describe second — a section written from imagination names fields
that do not exist and misses the ones that do.

1. `docshot inspect` — confirm the .docx template offers heading styles and a bullet list.
2. `docshot probe <route>` — the screen prints every button, tab and field with the
   JSON step that addresses it. Use `--after '<step json>'` to look inside a dialog.
   Never invent a button label: a guess that matches nothing silently photographs
   the wrong screen.
3. Write one shot per screen into `docshot.config.json`. Use `menu` (focus + Enter)
   for icon-only triggers, `repeatUntilGone` to page past an empty state, and `mask`
   for anything rendering personal data. Credentials go in as `${VAR}`.
4. `docshot check` — fix every error before a browser opens.
5. `docshot capture --only <one-shot>` and look at the PNG. Then `docshot capture`
   for the batch, and read the warnings: "the screen did not change after the
   interaction" means the shot is showing the page behind the dialog.
6. Write the Markdown in `sourceDir` describing what the screenshots show.
7. `docshot build` for one file per module, or `docshot build --single`.

Capture against a seeded demo environment, never production. Leave reviewer and
approver blank — they belong to the approval workflow.

Full contract: AGENTS.md in the docshot repository.
