# Working on a docshot project

This file is for the coding agent (Claude Code, Codex, Cursor, …) helping someone
turn a running application into an operation manual. Read it before writing a
line of configuration or Markdown — most of what follows is not guessable from
the code, and every item here comes from a document that went to review wrong.

## What this tool does

Two halves, one configuration file (`docshot.config.json`):

- `docshot capture` drives a browser through the app and writes one PNG per screen into `shotsDir`.
- `docshot build` turns each Markdown file in `sourceDir` into a `.docx` **inside the project's own corporate template**, embedding those PNGs.

The generator never invents styling. It reads the heading styles, the bullet
list, the table style and the section properties out of the `.docx` template it
was given, and replaces only the document body. That is why the header, the
footer, the document code and the validity fields survive.

## The loop that works

1. **`docshot inspect`** — confirm the template gives you headings and a bullet list. If it reports `none (direct formatting)`, the template is unusual; say so instead of fighting it.
2. **`docshot probe <route>`** — ask the screen what it offers. It logs in, opens the route and prints every button, tab and field with the exact JSON step to paste. Use it before writing any step; do not guess a button's label. `--after '<step json>'` probes what appears *after* an interaction (inside a dialog, for example).
3. **Write the shots** in `docshot.config.json`.
4. **`docshot check`** — static validation, no browser. Catches unknown keys, invalid regexes, a `waitForUrl` that matches the login page itself, duplicate shot names, images a manual references that no shot produces, and shots nobody uses.
5. **`docshot capture --only <one-shot>`** — take **one** screenshot and look at it. Framing, theme and state are decided here.
6. **`docshot capture`** — the whole batch. Read the warnings at the end; they are not decoration.
7. **Write the Markdown** describing what the screenshots actually show.
8. **`docshot build`** (or `--single` for one consolidated document).

Capture **before** writing. A section written from imagination describes fields
that do not exist and misses the ones that do.

## Traps that cost a review cycle

- **`waitForUrl` that matches everything.** `"/(?!login)"` also matches the `//` in `http://`, so the run declares login complete while still sitting on the login page, and every screenshot is of an error screen. Anchor it: `"localhost:3000/(?!login)"`. `docshot check` flags this.
- **A click that misses photographs the screen behind it.** Nobody notices until review. The capture compares the screen before and after an interaction and warns `the screen did not change after the interaction` — treat that warning as a failure.
- **Icon-only menu triggers swallow `click()`.** On Radix/Headless UI, the event lands on the SVG inside the button and the menu stays closed, with no error. Use the `menu` step (focus + Enter). `probe` already emits `menu` for anything with `aria-haspopup`.
- **A screen whose list is empty is not worth a screenshot.** Use `repeatUntilGone` to page forward to a day or filter that has data, or capture the creation form instead.
- **Personal data.** Put every selector that can render a name, a document number or contact details in `mask`. Capture against a seeded demo environment, never production.
- **Login throttling.** Apps rate-limit login; repeated capture runs hit it and the run fails with `login did not leave …/login`. Wait, do not "fix" the credentials.
- **Images are scaled to the template's text width.** If a document must keep an existing layout, set `maxImageWidthIn`.

## The Markdown dialect

Small on purpose — anything richer belongs in the template.

```
# ## ###        headings (they become the template's heading styles)
- item          bullet;  "  - item" is a sub-bullet
| a | b |       table, with the usual separator row
**bold** *italic* `code`
```fenced```    code block
![caption](shot.png)   image from shotsDir, with a caption below it
---             page break, alone on a line
{{include: x}}  splices source/_x.md
```

Front matter (`titulo`, `subtitulo`, `versao`, `data`, `elaborador`,
`cargo_elaborador`, `departamento`) fills the cover and the approval tables and
overrides `document` in the config. Files starting with `_` are includes, not
manuals of their own.

Reviewer, approver and homologator are left blank **by design** — they are
filled in during the approval workflow. Do not invent names.

## Configuration reference

Top level: `template`, `sourceDir`, `shotsDir`, `outDir`, `lang`,
`maxImageWidthIn`, `cover`, `revisionHistory`, `approval`, `document`,
`labels`, `consolidated`, `capture`.

`capture`: `baseUrl`, `viewport`, `deviceScaleFactor`, `colorScheme`, `locale`,
`timezone`, `settleMs`, `timeoutMs`, `mask`, `maskColor`, `stopOnError`,
`auth`, `shots`.

A shot: `name` (becomes the file name), `goto`, `steps`, `settleMs`,
`finalSettleMs`, `fullPage`, `skipScreenshot`, `closeWith`.

Steps: `goto`, `click`, `menu`, `fill`, `press`, `hover`, `scrollTo`, `wait`,
`waitForText`, `repeatUntilGone`, `screenshot`, `evaluate`.

A target is `{selector}`, `{role, name}`, `{text}` or `{label}`; `name` is a
case-insensitive regex, `nth` picks among matches.

## House rules

- **Credentials never go in the file.** Use `${VAR}`; the value comes from the shell or from a `.env` beside the config, which is gitignored. `docshot check` rejects a literal.
- **Do not commit the corporate template or the client's screenshots** to a public repository.
- Keep `shots/` in version control next to the sources — that is what makes a document reproducible months later.
- The generator is standard-library Python and the runner is plain Node plus Playwright. Do not add dependencies to either.
