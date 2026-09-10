"""Write the .docx by cloning the template package and swapping the body.

Styles, header, footer, numbering, theme and document variables all stay
exactly as the template had them — only `word/document.xml`, its relationships
and the embedded media change.
"""

import os
import zipfile
from typing import Dict, List, Optional, Tuple

from .ooxml import Body

CONTENT_TYPE_BY_EXTENSION = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
}

FALLBACK_SECT_PR = (
    '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"'
    ' w:header="708" w:footer="708" w:gutter="0"/>'
    '<w:cols w:space="708"/><w:docGrid w:linePitch="360"/></w:sectPr>'
)


def _media_names(images: List[Tuple[str, str]]) -> Dict[str, str]:
    """One media file name per source path, de-duplicated across folders."""
    names = {}
    used = set()
    for _, path in images:
        if path in names:
            continue
        base = os.path.basename(path)
        candidate = base
        stem, ext = os.path.splitext(base)
        counter = 2
        while candidate in used:
            candidate = "%s-%d%s" % (stem, counter, ext)
            counter += 1
        used.add(candidate)
        names[path] = candidate
    return names


def _ensure_content_types(content_types: str, media: Dict[str, str]) -> str:
    for name in media.values():
        extension = os.path.splitext(name)[1].lstrip(".").lower()
        content_type = CONTENT_TYPE_BY_EXTENSION.get(extension)
        if not content_type or 'Extension="%s"' % extension in content_types:
            continue
        content_types = content_types.replace(
            "</Types>",
            '<Default Extension="%s" ContentType="%s"/></Types>' % (extension, content_type),
        )
    return content_types


def write(
    output: str,
    template: str,
    body: Body,
    sect_pr: Optional[str],
    cover_xml: str = "",
) -> str:
    with zipfile.ZipFile(template) as tpl:
        document_xml = tpl.read("word/document.xml").decode("utf-8")
        rels = tpl.read("word/_rels/document.xml.rels").decode("utf-8")
        content_types = tpl.read("[Content_Types].xml").decode("utf-8")
        names = tpl.namelist()

    prolog = document_xml[: document_xml.index("<w:body>") + len("<w:body>")]
    document = (
        prolog
        + cover_xml
        + "".join(body.xml)
        + (sect_pr or FALLBACK_SECT_PR)
        + "</w:body></w:document>"
    )

    media = _media_names(body.images)
    image_rels = "".join(
        '<Relationship Id="%s" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        'Target="media/%s"/>' % (rel_id, media[path])
        for rel_id, path in body.images
    )
    rels = rels.replace("</Relationships>", image_rels + "</Relationships>")
    content_types = _ensure_content_types(content_types, media)

    directory = os.path.dirname(os.path.abspath(output))
    if directory:
        os.makedirs(directory, exist_ok=True)

    with zipfile.ZipFile(template) as tpl, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED
    ) as out:
        for name in names:
            if name == "word/document.xml":
                out.writestr(name, document)
            elif name == "word/_rels/document.xml.rels":
                out.writestr(name, rels)
            elif name == "[Content_Types].xml":
                out.writestr(name, content_types)
            else:
                out.writestr(name, tpl.read(name))
        for path, media_name in media.items():
            out.write(path, "word/media/%s" % media_name)

    return output
