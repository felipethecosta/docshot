"""The Markdown dialect the manual sources are written in.

Deliberately small — headings, bullets, tables, images, code blocks, page
breaks and includes. Anything richer belongs in the template, not here.
"""

import os
import re
from typing import Dict, List, Optional, Tuple

from .ooxml import Body

INCLUDE = re.compile(r"^\{\{include:\s*(.+?)\s*\}\}$")
IMAGE = re.compile(r"^!\[(.*?)\]\((.*?)\)$")
SUB_BULLET = re.compile(r"^ {2,}[-*] ")


def read_front_matter(path: str) -> Dict[str, str]:
    """The `key: value` block delimited by `---` at the top of a source."""
    meta = {}
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    if not lines or lines[0].strip() != "---":
        return meta
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def parse(
    path: str,
    body: Body,
    source_dir: str,
    shots_dir: str,
    level_shift: int = 0,
    skip_includes: bool = False,
    rewrites: Optional[List[Tuple[str, str]]] = None,
    missing: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Translate one source file into OOXML paragraphs appended to `body`."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    meta = {}
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            if ":" in lines[i]:
                key, value = lines[i].split(":", 1)
                meta[key.strip()] = value.strip()
            i += 1
        i += 1

    pending_table = []  # type: List[List[str]]

    def flush_table():
        if not pending_table:
            return
        header, rows = pending_table[0], pending_table[1:]
        rows = [r for r in rows if not all(set(c.strip()) <= set("-:") for c in r)]
        body.table(header, rows)
        del pending_table[:]

    while i < len(lines):
        line = lines[i]
        for old, new in rewrites or ():
            line = line.replace(old, new)
        stripped = line.strip()

        include = INCLUDE.match(stripped)
        if include:
            flush_table()
            if not skip_includes:
                partial = os.path.join(source_dir, "_%s.md" % include.group(1))
                if os.path.exists(partial):
                    with open(partial, encoding="utf-8") as fh:
                        lines[i + 1 : i + 1] = fh.read().split("\n")
                else:
                    print("    ! missing include: %s" % partial)
            i += 1
            continue

        if stripped.startswith("```"):
            flush_table()
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            body.code_block(block)
            i += 1
            continue

        if stripped.startswith("|"):
            pending_table.append([c.strip() for c in stripped.strip("|").split("|")])
            i += 1
            continue
        flush_table()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            body.page_break()
        elif stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            body.heading(level + level_shift, stripped[level:].strip())
        elif stripped.startswith("!["):
            match = IMAGE.match(stripped)
            if match:
                caption, filename = match.group(1), match.group(2)
                shot = filename if os.path.isabs(filename) else os.path.join(shots_dir, filename)
                if not body.image(shot, caption) and missing is not None:
                    missing.append(filename)
        elif SUB_BULLET.match(line):
            body.bullet(SUB_BULLET.sub("", line), level=1)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            body.bullet(stripped[2:], level=0)
        else:
            body.paragraph(stripped)

        i += 1

    flush_table()
    return meta
