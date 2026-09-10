"""docshot build/inspect/init — the .docx half of the tool."""

import argparse
import os
import sys

from . import builder, config as config_module, lint, plain_template, template

STARTER_CONFIG = """{
  "template": "template/base.docx",
  "sourceDir": "source",
  "shotsDir": "shots",
  "outDir": "build",
  "document": {
    "titulo": "%s",
    "subtitulo": "Manual de Operação",
    "versao": "1.0.0",
    "data": "",
    "elaborador": "",
    "cargo_elaborador": "",
    "departamento": ""
  },
  "consolidated": {
    "output": "manual.docx",
    "appendIncludes": []
  },
  "capture": {
    "baseUrl": "http://localhost:3000",
    "outDir": "shots",
    "viewport": { "width": 1440, "height": 900 },
    "shots": [{ "name": "home", "goto": "/" }]
  }
}
"""

STARTER_SOURCE = """---
titulo: %s
subtitulo: Manual de Operação
versao: 1.0.0
data: 
elaborador: 
---

# OBJETIVO

Descreva aqui o que este manual cobre.

# OPERAÇÃO

![Tela inicial do sistema](home.png)

- Um passo da operação
  - Um detalhe do passo
"""


def _resolve_template(config: dict, override: str) -> str:
    path = os.path.expanduser(override) if override else config["template"]
    if path and os.path.exists(path):
        return path

    fallback = os.path.join(config["root"], ".docshot", "plain.docx")
    if path:
        print("template not found (%s) — falling back to the plain one" % path)
    plain_template.write(fallback)
    return fallback


def _load(args) -> dict:
    config = config_module.load(args.config or config_module.find())
    if getattr(args, "out", None):
        config["outDir"] = os.path.join(config["root"], args.out)
    config["template"] = _resolve_template(config, getattr(args, "template", ""))
    return config


def cmd_build(args) -> int:
    config = _load(args)
    info = template.probe(config["template"])
    slugs = args.slugs or builder.sources(config)

    if args.single:
        print("single document")
        builder.build_consolidated(config, slugs, info)
        return 0

    for slug in slugs:
        print(slug)
        builder.build_one(config, slug, info)
    return 0


def cmd_inspect(args) -> int:
    config = _load(args)
    print(config["template"])
    print(template.describe(template.probe(config["template"])))
    return 0


def cmd_check(args) -> int:
    path = args.config or config_module.find()
    config = config_module.load(path)
    print(path)
    return lint.report(lint.check(config))


def cmd_init(args) -> int:
    root = os.path.abspath(args.directory)
    name = args.name or os.path.basename(root)
    for folder in ("source", "shots", "template", "build"):
        os.makedirs(os.path.join(root, folder), exist_ok=True)

    config_path = os.path.join(root, config_module.CONFIG_NAME)
    if os.path.exists(config_path):
        print("%s already exists, left untouched" % config_path)
    else:
        with open(config_path, "w", encoding="utf-8") as fh:
            fh.write(STARTER_CONFIG % name)
        print("wrote %s" % config_path)

    source_path = os.path.join(root, "source", "01-manual.md")
    if not os.path.exists(source_path):
        with open(source_path, "w", encoding="utf-8") as fh:
            fh.write(STARTER_SOURCE % name)
        print("wrote %s" % source_path)

    print("drop your corporate .docx at template/base.docx, then: docshot build")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="docshot", description=__doc__)
    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build", help="build .docx from the Markdown sources")
    build.add_argument("slugs", nargs="*", help="source names (default: all)")
    build.add_argument("--single", action="store_true", help="one document, one chapter per source")
    build.add_argument("--config", help="path to docshot.config.json")
    build.add_argument("--template", help="override the .docx template")
    build.add_argument("--out", help="override the output directory")
    build.set_defaults(func=cmd_build)

    inspect = sub.add_parser("inspect", help="report what the template offers the generator")
    inspect.add_argument("--config", help="path to docshot.config.json")
    inspect.add_argument("--template", help="override the .docx template")
    inspect.set_defaults(func=cmd_inspect)

    check = sub.add_parser("check", help="validate the configuration and the sources")
    check.add_argument("--config", help="path to docshot.config.json")
    check.set_defaults(func=cmd_check)

    init = sub.add_parser("init", help="scaffold a project in this directory")
    init.add_argument("directory", nargs="?", default=".")
    init.add_argument("--name", help="document title used in the starter files")
    init.set_defaults(func=cmd_init)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
