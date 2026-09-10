---
name: write-manual
description: Turn a running web application into an operation manual (.docx) in the company's template, using docshot. Use when asked to write, update or regenerate a system manual, operating procedure, validation document or training guide from screens of a live app.
---

# Writing a manual from a running system

The order matters more than the writing. Capture first, describe second: a
section written from imagination names fields that do not exist and misses the
ones that do.

## 0. Before anything

Confirm three things, and say which one is missing instead of guessing:

- the app is running and reachable at some base URL;
- there are credentials for a **seeded demo or staging** environment (never production);
- there is a corporate `.docx` template, or the plain fallback is acceptable.

`docshot inspect` tells you what the template offers. Headings reported as
`none (direct formatting)` means the template has no heading styles — usable,
but say so.

## 1. Map the screens

Ask which modules the manual covers, then, for each route:

```bash
docshot probe /route
docshot probe /route --after '{"click":{"role":"button","name":"^New item$"}}'
```

`probe` prints every button, tab and field with the JSON step to paste, so the
steps are written against the real DOM. Never invent a button label: a guess
that matches nothing produces a screenshot of the wrong screen, silently.

Note what each screen actually contains — field names, required fields, the
states a record moves through. That is the raw material of the text.

## 2. Write the configuration

One shot per screen the manual will show. Name them `<module>-<order>-<what>`
so the file names sort in reading order.

Reach for the right step:

- a form or dialog → `click` on the button that opens it;
- an icon-only row menu → `menu` (focus + Enter; `click` is swallowed);
- a screen that is empty today → `repeatUntilGone` to page forward to real data, or capture the creation form instead;
- anything rendering personal data → add its selector to `mask`.

Credentials go in as `${VAR}`, never literally.

Then:

```bash
docshot check
```

Fix every error before opening a browser.

## 3. One screenshot, then the batch

```bash
docshot capture --only <one-shot>
```

Look at the PNG. Framing, theme, language and state are decided here — a batch
recaptured because the first one was never inspected costs far more.

```bash
docshot capture
```

Read the warnings. `the screen did not change after the interaction` means the
shot is showing the page behind the dialog: fix the step, do not ship it.

## 4. Write the Markdown

One file per module in `sourceDir`, front matter filled in, headings in the
document's own voice. Describe what the screenshot shows — the fields that are
required, what a status means, what the button does — not what you assume the
software does.

Repeated boilerplate goes in `source/_name.md` and is spliced with
`{{include: name}}`. Leave reviewer and approver blank: they belong to the
approval workflow.

## 5. Build and hand over

```bash
docshot build            # one .docx per module
docshot build --single   # one consolidated document
```

Report what was generated, and be explicit about any screen you could not
capture and why. A manual with a known gap is useful; one with an invented
section is not.
