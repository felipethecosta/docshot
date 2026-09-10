"""Inspect a .docx template and report what the generator can reuse from it.

Nothing here is specific to one corporate template: heading styles, the bullet
list, the table style, the section properties (which carry the header and
footer references) and the usable page width are all read from the file that
was handed in.
"""

import re
import zipfile
from typing import Dict, List, Optional
from xml.etree import ElementTree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

TWIP_PER_EMU = 635
HEADING_NAME = re.compile(r"^(?:heading|t[íi]tulo|encabezado|berschrift)\s*([1-9])$")
TABLE_CELL_NAMES = {"table contents", "tabela conteúdo", "tabela conteudo", "table content"}

# A4 minus 2cm margins, the fallback when the template has no section properties.
DEFAULT_MAX_IMAGE_EMU = 5943600


def _read(package: zipfile.ZipFile, name: str) -> Optional[str]:
    try:
        return package.read(name).decode("utf-8")
    except KeyError:
        return None


def _bullet_num_ids(numbering_xml: Optional[str]) -> List[str]:
    """numIds whose first level is a bullet, in document order."""
    if not numbering_xml:
        return []
    root = ElementTree.fromstring(numbering_xml)

    bullet_abstract = set()
    for abstract in root.findall(W + "abstractNum"):
        for level in abstract.findall(W + "lvl"):
            if level.get(W + "ilvl") != "0":
                continue
            fmt = level.find(W + "numFmt")
            if fmt is not None and fmt.get(W + "val") == "bullet":
                bullet_abstract.add(abstract.get(W + "abstractNumId"))

    ids = []
    for num in root.findall(W + "num"):
        ref = num.find(W + "abstractNumId")
        if ref is not None and ref.get(W + "val") in bullet_abstract:
            ids.append(num.get(W + "numId"))
    return ids


def _styles(styles_xml: Optional[str], bullet_nums: List[str]) -> Dict:
    found = {
        "heading": {},
        "bullet_style": None,
        "bullet_num_id": bullet_nums[0] if bullet_nums else None,
        "table_cell_style": None,
    }
    if not styles_xml:
        return found

    root = ElementTree.fromstring(styles_xml)
    for style in root.findall(W + "style"):
        if style.get(W + "type") != "paragraph":
            continue
        style_id = style.get(W + "styleId") or ""
        name_el = style.find(W + "name")
        name = (name_el.get(W + "val") if name_el is not None else "") or ""
        key = name.strip().lower()

        match = HEADING_NAME.match(key) or HEADING_NAME.match(style_id.strip().lower())
        if match:
            found["heading"].setdefault(int(match.group(1)), style_id)
            continue

        if key in TABLE_CELL_NAMES and not found["table_cell_style"]:
            found["table_cell_style"] = style_id
            continue

        # A paragraph style already wired to a bullet list is the one the
        # template's own authors use for bullets — prefer it over a bare numId.
        num_id = style.find("./%spPr/%snumPr/%snumId" % (W, W, W))
        if num_id is not None and num_id.get(W + "val") in bullet_nums:
            if not found["bullet_style"]:
                found["bullet_style"] = style_id
                found["bullet_num_id"] = num_id.get(W + "val")

    return found


def _section_properties(document_xml: str) -> Optional[str]:
    """The body-level <w:sectPr>, which carries header/footer relationships."""
    match = re.search(r"<w:sectPr[ >].*?</w:sectPr>", document_xml, re.S)
    if match:
        return match.group(0)
    match = re.search(r"<w:sectPr[^>]*/>", document_xml)
    return match.group(0) if match else None


def _usable_width_emu(sect_pr: Optional[str]) -> int:
    if not sect_pr:
        return DEFAULT_MAX_IMAGE_EMU
    size = re.search(r'<w:pgSz[^>]*w:w="(\d+)"', sect_pr)
    margins = re.search(r"<w:pgMar[^>]*>", sect_pr)
    if not size or not margins:
        return DEFAULT_MAX_IMAGE_EMU
    left = re.search(r'w:left="(\d+)"', margins.group(0))
    right = re.search(r'w:right="(\d+)"', margins.group(0))
    twips = int(size.group(1)) - int(left.group(1) if left else 0) - int(
        right.group(1) if right else 0
    )
    return max(twips, 1000) * TWIP_PER_EMU


def probe(template_path: str) -> Dict:
    """Everything the generator needs to write a body the template accepts."""
    with zipfile.ZipFile(template_path) as package:
        document_xml = _read(package, "word/document.xml")
        if document_xml is None:
            raise ValueError("not a Word document: %s" % template_path)
        styles_xml = _read(package, "word/styles.xml")
        numbering_xml = _read(package, "word/numbering.xml")
        rels_xml = _read(package, "word/_rels/document.xml.rels") or ""

    info = _styles(styles_xml, _bullet_num_ids(numbering_xml))
    info["sect_pr"] = _section_properties(document_xml)
    info["max_image_emu"] = _usable_width_emu(info["sect_pr"])
    info["rel_ids"] = set(re.findall(r'Id="([^"]+)"', rels_xml))
    return info


def describe(info: Dict) -> str:
    headings = ", ".join(
        "%d=%s" % (level, info["heading"][level]) for level in sorted(info["heading"])
    )
    return "\n".join(
        [
            "headings:   %s" % (headings or "none (direct formatting)"),
            "bullets:    %s"
            % (
                "%s (numId %s)" % (info["bullet_style"] or "no style", info["bullet_num_id"])
                if info["bullet_num_id"]
                else "none (literal bullet character)"
            ),
            "table cell: %s" % (info["table_cell_style"] or "none (direct formatting)"),
            "sectPr:     %s" % ("reused from template" if info["sect_pr"] else "generator default"),
            "text width: %.2f in" % (info["max_image_emu"] / 914400.0),
        ]
    )
