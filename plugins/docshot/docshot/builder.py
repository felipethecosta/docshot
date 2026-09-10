"""Turn Markdown sources plus screenshots into .docx documents."""

import os
from typing import Dict, List, Optional

from . import doc, markdown, package, template
from .ooxml import Body


def sources(config: Dict) -> List[str]:
    """Every source slug, in filename order. `_name.md` files are includes."""
    source_dir = config["sourceDir"]
    if not os.path.isdir(source_dir):
        raise SystemExit("source directory not found: %s" % source_dir)
    return sorted(
        name[:-3]
        for name in os.listdir(source_dir)
        if name.endswith(".md") and not name.startswith("_")
    )


def _meta_for(config: Dict, front_matter: Dict) -> Dict:
    meta = dict(config.get("document") or {})
    meta.update(front_matter)
    return meta


EMU_PER_INCH = 914400


def _new_body(config: Dict, info: Dict) -> Body:
    # By default images span the template's usable text width; a project that
    # wants a narrower column sets maxImageWidthIn.
    width = config.get("maxImageWidthIn") or 0
    max_emu = int(width * EMU_PER_INCH) if width else info["max_image_emu"]
    return Body(info, lang=config.get("lang", "pt-BR"), max_image_emu=max_emu)


def build_one(config: Dict, slug: str, info: Optional[Dict] = None) -> str:
    info = info or template.probe(config["template"])
    source = os.path.join(config["sourceDir"], "%s.md" % slug)
    if not os.path.exists(source):
        raise SystemExit("source not found: %s" % source)

    missing = []  # type: List[str]
    body = _new_body(config, info)
    front_matter = markdown.parse(
        source,
        body,
        source_dir=config["sourceDir"],
        shots_dir=config["shotsDir"],
        missing=missing,
    )
    meta = _meta_for(config, front_matter)
    text = doc.labels(config.get("labels"))

    tail = _new_body(config, info)
    tail.adopt_ids(body)
    doc.control_tables(
        tail,
        meta,
        text,
        revision_history=config.get("revisionHistory", True),
        approval=config.get("approval", True),
    )
    body.xml.extend(tail.xml)

    output = os.path.join(config["outDir"], "%s.docx" % slug)
    package.write(
        output,
        config["template"],
        body,
        info["sect_pr"],
        cover_xml=doc.cover(meta, text) if config.get("cover", True) else "",
    )
    _report(output, missing)
    return output


def build_consolidated(config: Dict, slugs: List[str], info: Optional[Dict] = None) -> str:
    """One document holding every source as a chapter.

    Each source's headings drop one level so the chapter title can own `#`, and
    shared includes are emitted once, after the last chapter.
    """
    info = info or template.probe(config["template"])
    settings = config.get("consolidated") or {}
    rewrites = [tuple(pair) for pair in settings.get("rewrites", [])]
    trailing = settings.get("appendIncludes", [])

    missing = []  # type: List[str]
    body = _new_body(config, info)
    chapters = []

    for index, slug in enumerate(slugs):
        source = os.path.join(config["sourceDir"], "%s.md" % slug)
        front_matter = markdown.read_front_matter(source)
        title = front_matter.get("titulo") or front_matter.get("title") or slug
        chapters.append(title)

        if index:
            body.page_break()
        body.heading(1, title.upper())
        markdown.parse(
            source,
            body,
            source_dir=config["sourceDir"],
            shots_dir=config["shotsDir"],
            level_shift=1,
            skip_includes=True,
            rewrites=rewrites,
            missing=missing,
        )

    for name in trailing:
        partial = os.path.join(config["sourceDir"], "_%s.md" % name)
        if not os.path.exists(partial):
            print("    ! missing include: %s" % partial)
            continue
        body.page_break()
        markdown.parse(
            partial,
            body,
            source_dir=config["sourceDir"],
            shots_dir=config["shotsDir"],
            missing=missing,
        )

    meta = _meta_for(config, settings.get("document") or {})
    text = doc.labels(config.get("labels"))

    tail = _new_body(config, info)
    tail.adopt_ids(body)
    doc.control_tables(
        tail,
        meta,
        text,
        revision_history=config.get("revisionHistory", True),
        approval=config.get("approval", True),
    )
    body.xml.extend(tail.xml)

    output = os.path.join(config["outDir"], settings.get("output", "manual.docx"))
    package.write(
        output,
        config["template"],
        body,
        info["sect_pr"],
        cover_xml=doc.cover(meta, text) if config.get("cover", True) else "",
    )
    print("    chapters: " + " · ".join(chapters))
    _report(output, missing)
    return output


def _report(output: str, missing: List[str]) -> None:
    size = os.path.getsize(output) // 1024
    print("    -> %s (%d KB)" % (output, size))
    if missing:
        print("    ! %d screenshot(s) missing: %s" % (len(missing), ", ".join(sorted(set(missing)))))
