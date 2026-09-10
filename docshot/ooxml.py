"""OOXML paragraph builders.

The document body is assembled as a list of XML fragments plus the media files
they reference. Every style id used here is resolved from the template at
runtime (see `template.py`) — nothing about a particular corporate template is
baked in.
"""

import html
import os
import re
import struct
from typing import Dict, List, Optional, Tuple

EMU_PER_PX = 9525


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def image_size(path: str) -> Tuple[int, int]:
    """Pixel size of a PNG or JPEG, read from the header alone."""
    with open(path, "rb") as fh:
        head = fh.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            width, height = struct.unpack(">II", head[16:24])
            return width, height
        if head[:2] == b"\xff\xd8":
            fh.seek(2)
            while True:
                marker = fh.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    break
                size = struct.unpack(">H", fh.read(2))[0]
                if marker[1] in (0xC0, 0xC1, 0xC2, 0xC3):
                    fh.read(1)
                    height, width = struct.unpack(">HH", fh.read(4))
                    return width, height
                fh.seek(size - 2, os.SEEK_CUR)
    raise ValueError("unsupported image (PNG and JPEG only): %s" % path)


class Body:
    """Accumulates OOXML paragraphs plus the media files they reference."""

    def __init__(self, styles: Dict, lang: str = "pt-BR", max_image_emu: int = 5943600):
        self.styles = styles
        self.lang = lang
        self.max_image_emu = max_image_emu
        self.xml = []  # type: List[str]
        self.images = []  # type: List[Tuple[str, str]]
        self._pid = 0x30000000
        self._drawing_id = 1000

    # -- ids --------------------------------------------------------------

    def next_paragraph_id(self) -> str:
        self._pid += 1
        return "%08X" % self._pid

    def adopt_ids(self, other: "Body") -> None:
        """Continue another body's id sequence, so ids stay unique in one file."""
        self._pid = other._pid
        self._drawing_id = other._drawing_id
        self.images = other.images

    # -- shared bits ------------------------------------------------------

    def _lang(self) -> str:
        return '<w:lang w:val="%s"/>' % self.lang

    def _spacing(self, line: str = "288") -> str:
        return '<w:spacing w:after="0" w:line="%s" w:lineRule="auto"/>' % line

    # -- block builders ---------------------------------------------------

    def heading(self, level: int, text: str) -> None:
        level = max(1, min(level, 9))
        style = self.styles["heading"].get(level)
        pid = self.next_paragraph_id()
        if style:
            ppr = (
                '<w:pPr><w:pStyle w:val="%s"/>'
                '<w:spacing w:before="0" w:after="0"/></w:pPr>' % style
            )
            rpr = ""
        else:
            # No heading style in the template: fall back to direct formatting
            # so the document still reads as a hierarchy.
            size = max(28 - (level - 1) * 4, 20)
            ppr = (
                '<w:pPr><w:spacing w:before="240" w:after="120"/>'
                '<w:outlineLvl w:val="%d"/></w:pPr>' % (level - 1)
            )
            rpr = '<w:rPr><w:b/><w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr>' % (size, size)
        self.xml.append(
            '<w:p w14:paraId="{pid}" w14:textId="{pid}">{ppr}'
            '<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'.format(
                pid=pid, ppr=ppr, rpr=rpr, text=esc(text)
            )
        )

    def paragraph(self, text: str = "") -> None:
        pid = self.next_paragraph_id()
        runs = self._runs(text) if text else ""
        self.xml.append(
            '<w:p w14:paraId="{pid}" w14:textId="{pid}">'
            "<w:pPr>{spacing}<w:rPr><w:szCs w:val=\"22\"/>{lang}</w:rPr></w:pPr>"
            "{runs}</w:p>".format(
                pid=pid, spacing=self._spacing(), lang=self._lang(), runs=runs
            )
        )

    def bullet(self, text: str, level: int = 0) -> None:
        pid = self.next_paragraph_id()
        style = self.styles.get("bullet_style")
        num_id = self.styles.get("bullet_num_id")
        parts = ["<w:pPr>"]
        if style:
            parts.append('<w:pStyle w:val="%s"/>' % style)
        if num_id:
            parts.append(
                '<w:numPr><w:ilvl w:val="%d"/><w:numId w:val="%s"/></w:numPr>'
                % (level, num_id)
            )
        else:
            # Without a bullet list in the template, indent and prefix by hand.
            parts.append('<w:ind w:left="%d"/>' % (360 + level * 360))
        parts.append('<w:spacing w:before="0" w:after="0"/></w:pPr>')
        content = text if num_id else ("• " + text)
        self.xml.append(
            '<w:p w14:paraId="{pid}" w14:textId="{pid}">{ppr}{runs}</w:p>'.format(
                pid=pid, ppr="".join(parts), runs=self._runs(content)
            )
        )

    def code_block(self, lines: List[str]) -> None:
        for line in lines:
            pid = self.next_paragraph_id()
            self.xml.append(
                '<w:p w14:paraId="{pid}" w14:textId="{pid}">'
                '<w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
                '<w:ind w:left="284"/></w:pPr>'
                '<w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>'
                '<w:sz w:val="18"/><w:szCs w:val="18"/>{lang}</w:rPr>'
                '<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'.format(
                    pid=pid, lang=self._lang(), text=esc(line) or " "
                )
            )

    def page_break(self) -> None:
        pid = self.next_paragraph_id()
        self.xml.append(
            '<w:p w14:paraId="{pid}" w14:textId="{pid}">'
            '<w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
            '<w:jc w:val="left"/></w:pPr>'
            '<w:r><w:br w:type="page"/></w:r></w:p>'.format(pid=pid)
        )

    def caption(self, text: str) -> None:
        pid = self.next_paragraph_id()
        rpr = '<w:rPr><w:i/><w:sz w:val="18"/><w:szCs w:val="18"/>%s</w:rPr>' % self._lang()
        self.xml.append(
            '<w:p w14:paraId="{pid}" w14:textId="{pid}">'
            '<w:pPr>{spacing}<w:jc w:val="center"/>{rpr}</w:pPr>'
            '<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'.format(
                pid=pid, spacing=self._spacing(), rpr=rpr, text=esc(text)
            )
        )

    def image(self, path: str, caption: str = "") -> bool:
        if not os.path.exists(path):
            print("    ! missing image, section rendered without it: %s" % path)
            return False

        width_px, height_px = image_size(path)
        cx = width_px * EMU_PER_PX
        cy = height_px * EMU_PER_PX
        if cx > self.max_image_emu:
            cy = int(cy * self.max_image_emu / cx)
            cx = self.max_image_emu

        rel_id = "rIdDocshotImg%d" % (len(self.images) + 1)
        self.images.append((rel_id, path))
        self._drawing_id += 1
        did = self._drawing_id
        pid = self.next_paragraph_id()

        self.xml.append(
            '<w:p w14:paraId="{pid}" w14:textId="{pid}">'
            '<w:pPr>{spacing}<w:jc w:val="center"/></w:pPr>'
            "<w:r><w:rPr><w:noProof/></w:rPr><w:drawing>"
            '<wp:inline distT="0" distB="0" distL="0" distR="0">'
            '<wp:extent cx="{cx}" cy="{cy}"/>'
            '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
            '<wp:docPr id="{did}" name="Image {did}" descr="{alt}"/>'
            "<wp:cNvGraphicFramePr>"
            '<a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>'
            "</wp:cNvGraphicFramePr>"
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:nvPicPr><pic:cNvPr id="{did}" name="Image {did}"/>'
            "<pic:cNvPicPr/></pic:nvPicPr>"
            '<pic:blipFill><a:blip r:embed="{rel}"/>'
            "<a:stretch><a:fillRect/></a:stretch></pic:blipFill>"
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
            '<a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            "</pic:pic></a:graphicData></a:graphic></wp:inline>"
            "</w:drawing></w:r></w:p>".format(
                pid=pid,
                spacing=self._spacing(),
                cx=cx,
                cy=cy,
                did=did,
                alt=esc(caption),
                rel=rel_id,
            )
        )
        if caption:
            self.caption(caption)
        return True

    def table(self, header: List[str], rows: List[List[str]]) -> None:
        cols = max(len(header), 1)
        width = int(5000 / cols)
        grid = "".join('<w:gridCol w:w="%d"/>' % int(9628 / cols) for _ in range(cols))
        cell_style = self.styles.get("table_cell_style")

        def header_cell(text: str) -> str:
            pid = self.next_paragraph_id()
            rpr = '<w:rPr><w:b/><w:szCs w:val="20"/>%s</w:rPr>' % self._lang()
            return (
                '<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="pct"/>'
                '<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/></w:tcPr>'
                '<w:p w14:paraId="{pid}" w14:textId="{pid}">'
                '<w:pPr>{spacing}<w:jc w:val="left"/>{rpr}</w:pPr>'
                '<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p></w:tc>'
            ).format(
                w=width,
                fill=self.styles.get("table_header_fill", "BFBFBF"),
                pid=pid,
                spacing=self._spacing(),
                rpr=rpr,
                text=esc(text),
            )

        def body_cell(text: str) -> str:
            pid = self.next_paragraph_id()
            ppr = (
                '<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % cell_style
                if cell_style
                else "<w:pPr>%s</w:pPr>" % self._spacing("240")
            )
            return (
                '<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="pct"/></w:tcPr>'
                '<w:p w14:paraId="{pid}" w14:textId="{pid}">{ppr}{runs}</w:p></w:tc>'
            ).format(w=width, pid=pid, ppr=ppr, runs=self._runs(text, table=True))

        xml = [
            '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>'
            '<w:top w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
            '<w:left w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
            '<w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
            '<w:right w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
            '<w:insideH w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
            '<w:insideV w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
            "</w:tblBorders><w:tblCellMar>"
            '<w:left w:w="70" w:type="dxa"/><w:right w:w="70" w:type="dxa"/>'
            "</w:tblCellMar>"
            '<w:tblLook w:val="0080" w:firstRow="0" w:lastRow="0" w:firstColumn="1"'
            ' w:lastColumn="0" w:noHBand="0" w:noVBand="0"/></w:tblPr>'
            "<w:tblGrid>%s</w:tblGrid>" % grid,
            "<w:tr><w:trPr><w:tblHeader/></w:trPr>"
            + "".join(header_cell(h) for h in header)
            + "</w:tr>",
        ]
        for row in rows:
            padded = (row + [""] * cols)[:cols]
            xml.append("<w:tr>" + "".join(body_cell(c) for c in padded) + "</w:tr>")
        xml.append("</w:tbl>")
        self.xml.append("".join(xml))

    # -- inline formatting ------------------------------------------------

    def _runs(self, text: str, table: bool = False) -> str:
        """Split on **bold**, *italic* and `code`, emitting one run per fragment."""
        lang = self._lang()
        rpr_normal = "" if table else '<w:rPr><w:szCs w:val="22"/>%s</w:rPr>' % lang
        rpr_bold = (
            "<w:rPr><w:b/></w:rPr>"
            if table
            else '<w:rPr><w:b/><w:szCs w:val="22"/>%s</w:rPr>' % lang
        )
        rpr_italic = (
            "<w:rPr><w:i/></w:rPr>"
            if table
            else '<w:rPr><w:i/><w:szCs w:val="22"/>%s</w:rPr>' % lang
        )
        rpr_code = (
            '<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>'
            '<w:sz w:val="18"/><w:szCs w:val="18"/>%s</w:rPr>' % lang
        )

        runs = []
        for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text):
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                content, rpr = part[2:-2], rpr_bold
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                content, rpr = part[1:-1], rpr_italic
            elif part.startswith("`") and part.endswith("`"):
                content, rpr = part[1:-1], rpr_code
            else:
                content, rpr = part, rpr_normal
            runs.append(
                '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, esc(content))
            )
        return "".join(runs)
