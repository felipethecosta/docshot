"""Cover page and the closing control tables (revision history, approval).

Every label is configurable, so the same generator serves a manual in any
language or a template with different governance sections.
"""

from typing import Dict, List

from .ooxml import Body, esc

DEFAULT_LABELS = {
    "subtitle": "Manual de Operação",
    "version_prefix": "Versão",
    "revision_history": "HISTÓRICO DE REVISÕES",
    "revision_columns": ["Versão", "Mês/Ano", "Responsável", "Alteração"],
    "first_release": "Emissão inicial.",
    "approval": "APROVAÇÃO",
    "approval_columns": ["Papel", "Nome", "Cargo", "Departamento", "Data"],
    "approval_roles": ["Elaborador", "Revisor", "Aprovador", "Homologador"],
    "effective_from": "Vigente em:",
}


def labels(overrides: Dict) -> Dict:
    merged = dict(DEFAULT_LABELS)
    merged.update(overrides or {})
    return merged


def cover(meta: Dict, text: Dict, blank_lines_before: int = 11) -> str:
    """Title block on its own page, centred, above a rule."""
    blank = (
        '<w:p><w:pPr><w:spacing w:after="0" w:line="288" w:lineRule="auto"/>'
        '<w:jc w:val="left"/></w:pPr></w:p>'
    )
    centered = (
        '<w:p><w:pPr><w:spacing w:after="0" w:line="288" w:lineRule="auto"/>'
        '<w:jc w:val="center"/><w:rPr><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:pPr>'
        '<w:r><w:rPr><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>'
        '<w:t xml:space="preserve">{}</w:t></w:r></w:p>'
    )
    ruled = (
        "<w:p><w:pPr><w:pBdr>"
        '<w:bottom w:val="single" w:sz="12" w:space="1" w:color="auto"/></w:pBdr>'
        '<w:spacing w:after="0" w:line="288" w:lineRule="auto"/>'
        '<w:jc w:val="center"/></w:pPr>'
        '<w:r><w:t xml:space="preserve">{}</w:t></w:r></w:p>'
    )
    page_break = (
        '<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
        '<w:jc w:val="left"/></w:pPr><w:r><w:br w:type="page"/></w:r></w:p>'
    )

    subtitle = meta.get("subtitulo") or meta.get("subtitle") or text["subtitle"]
    version = meta.get("versao") or meta.get("version") or ""
    return (
        blank * blank_lines_before
        + centered.format(esc(meta.get("titulo") or meta.get("title") or ""))
        + centered.format(esc(subtitle))
        + ruled.format(esc("%s %s" % (text["version_prefix"], version)) if version else "")
        + ruled.format("")
        + blank * 8
        + page_break
    )


def control_tables(
    body: Body,
    meta: Dict,
    text: Dict,
    revision_history: bool = True,
    approval: bool = True,
) -> None:
    author = meta.get("elaborador") or meta.get("author") or ""
    department = meta.get("departamento") or meta.get("department") or ""

    if revision_history:
        body.heading(1, text["revision_history"])
        body.table(
            text["revision_columns"],
            [["01", meta.get("data") or meta.get("date") or "", author, text["first_release"]]],
        )
        body.paragraph()

    if approval:
        body.heading(1, text["approval"])
        roles = text["approval_roles"]  # type: List[str]
        rows = []
        for index, role in enumerate(roles):
            if index == 0:
                rows.append(
                    [
                        role,
                        author,
                        meta.get("cargo_elaborador") or meta.get("author_role") or "",
                        department,
                        "",
                    ]
                )
            else:
                # Reviewer, approver and homologator are filled in by hand
                # during the approval workflow — the generator leaves them blank.
                rows.append([role, "", "", department if index < len(roles) - 1 else "", ""])
        body.table(text["approval_columns"], rows)
        body.paragraph()
        body.table([text["effective_from"], ""], [])
