# Example: demo app

A project laid out the way a real one is, with the binaries left out: the
corporate `.docx` template and the captured screenshots belong to whoever runs
the pipeline, not to this repository.

```bash
cp .env.example .env          # fill in the credentials
docshot capture               # writes shots/*.png
docshot build --single        # writes build/Manual.docx
```

Without `template/base.docx`, `docshot build` falls back to a plain template so
the pipeline still runs end to end.

The `shots` list shows the interactions worth copying: a form opened from a
button, a tab switch, an icon-only row menu that only opens from the keyboard,
and paging forward until a screen has something worth photographing.
