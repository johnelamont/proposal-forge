"""F7: build the portfolio manifest from confirmed records and render it.

Two pure functions. `build_manifest` decides exactly what text appears (the
Rule 5 boundary lives here: client names only where permitted, no money
fields, no provenance, counts-only results). `render_pdf` turns a manifest
into bytes deterministically, so the hash the operator approved in the
preview is the hash of the document they download.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections import Counter
from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.portfolio import (
    Manifest,
    ManifestEntry,
    Results,
    Selection,
    TechCount,
)
from app.models.proposal import Profile

FOOTER = "Prepared from the consultant's own records with Proposal Forge"
LOST_BID = {"hired_other", "job_closed"}  # "not worth bidding" is left out


class PortfolioError(Exception):
    """A selection that cannot become a document (the route maps it to 422)."""


# --- manifest --------------------------------------------------------------------


def _month_label(ym: str | None) -> str | None:
    if not ym:
        return None
    try:
        y, m = ym.split("-")
        return date(int(y), int(m), 1).strftime("%b %Y")
    except ValueError:
        return ym


def _period(entry: dict[str, Any]) -> str | None:
    start, end = _month_label(entry.get("started")), _month_label(entry.get("ended"))
    if start and end:
        return start if start == end else f"{start} – {end}"
    return end or start


def _client_line(entry: dict[str, Any]) -> str | None:
    """Named only with permission; anonymised to the vertical otherwise; and
    nothing at all when the entry has no client (own products, open source)."""
    name = (entry.get("client_name") or "").strip()
    if not name:
        return None
    if entry.get("may_name_client"):
        return f"for {name}"
    vertical = (entry.get("vertical") or "").strip()
    return f"for a {vertical} client" if vertical else "for a client"


def _in_range(entry: dict[str, Any], from_: str | None, to: str | None) -> bool:
    anchor = entry.get("ended") or entry.get("started")
    if not (from_ or to):
        return True
    if not anchor:
        return False
    return (not from_ or anchor >= from_) and (not to or anchor <= to)


def _sort_key(entry: dict[str, Any]) -> tuple[int, str]:
    anchor = entry.get("ended") or entry.get("started") or ""
    return (
        0 if anchor else 1,
        "" if not anchor else "".join(chr(0x10FFFF - ord(c)) for c in anchor),
    )


def build_manifest(
    profile: Profile,
    entries: list[dict[str, Any]],
    index_rows: list[dict[str, Any]],
    selection: Selection,
    today: date,
) -> tuple[Manifest, list[str]]:
    """Exactly what the PDF will say, plus warnings for the operator about
    what was left out and why."""
    warnings: list[str] = []
    by_id = {e["id"]: e for e in entries}
    chosen = [by_id[i] for i in selection.entry_ids if i in by_id]
    missing = len(selection.entry_ids) - len(chosen)
    if missing:
        plural = "y" if missing == 1 else "ies"
        warnings.append(
            f"{missing} selected entr{plural} no longer exist and were skipped."
        )

    in_range = [e for e in chosen if _in_range(e, selection.from_, selection.to)]
    dropped = len(chosen) - len(in_range)
    if dropped:
        plural = "y" if dropped == 1 else "ies"
        warnings.append(
            f"{dropped} entr{plural} fall outside the date range "
            "(or have no dates) and were left out."
        )
    if not in_range:
        raise PortfolioError("Nothing to export: no selected entries match.")
    in_range.sort(key=_sort_key)

    unnamed = sum(
        1
        for e in in_range
        if (e.get("client_name") or "").strip() and not e.get("may_name_client")
    )
    if unnamed:
        noun, verb, be = (
            ("entry", "records", "is") if unnamed == 1 else ("entries", "record", "are")
        )
        warnings.append(
            f"{unnamed} {noun} {verb} a client name but {be} not "
            'marked "OK to name"; the client is not shown.'
        )

    manifest_entries = [
        ManifestEntry(
            id=e["id"],
            name=e["name"],
            period=_period(e),
            role=(e.get("role") or None),
            vertical=(e.get("vertical") or None),
            client_line=_client_line(e),
            summary=(e.get("summary") or "").strip(),
            tech_stack=list(e.get("tech_stack") or []),
            outcomes=[o for o in (e.get("outcomes") or []) if str(o).strip()],
        )
        for e in in_range
    ]

    tech: list[TechCount] = []
    if selection.include_tech:
        counts = Counter(
            t.strip()
            for e in in_range
            for t in (e.get("tech_stack") or [])
            if t.strip()
        )
        tech = [
            TechCount(name=n, count=c)
            for n, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        ]

    results: Results | None = None
    if selection.include_results:
        live = [r for r in index_rows if not r.get("archived")]
        won = [r for r in live if r.get("outcome") == "won"]
        lost = [
            r
            for r in live
            if r.get("outcome") == "lost" and r.get("lost_reason") in LOST_BID
        ]
        withdrawn = [r for r in live if r.get("outcome") == "withdrawn"]
        if won or lost or withdrawn:
            results = Results(
                won=len(won),
                lost=len(lost),
                withdrawn=len(withdrawn),
                industries_won=sorted(
                    {r["industry"] for r in won if r.get("industry")}
                ),
            )

    name = profile.signature_name.strip()
    return (
        Manifest(
            title=(selection.title or f"{name} — Selected work").strip(),
            operator=name,
            positioning=profile.positioning.strip(),
            generated_on=today.isoformat(),
            entries=manifest_entries,
            tech=tech,
            results=results,
            footer=FOOTER,
        ),
        warnings,
    )


def manifest_hash(manifest: Manifest) -> str:
    canonical = json.dumps(
        manifest.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- renderer ---------------------------------------------------------------------


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _numbered_canvas(footer: str, pages_out: list[int]):
    """Canvas that writes 'footer · page n of N' on every page. Two-pass via
    saved page states, the standard ReportLab recipe."""

    class NumberedCanvas(pdfcanvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states: list[dict] = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_page_states)
            pages_out.append(total)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.grey)
                self.drawCentredString(
                    A4[0] / 2, 12 * mm, f"{footer} · page {self._pageNumber} of {total}"
                )
                super().showPage()
            super().save()

    return NumberedCanvas


def render_pdf(manifest: Manifest) -> tuple[bytes, int]:
    """Deterministic: ReportLab's invariant mode fixes dates and IDs, so the
    same manifest always yields the same bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=manifest.title,
        author=manifest.operator,
        subject="Selected work",
        creator="Proposal Forge",
        invariant=1,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1", parent=styles["Title"], alignment=TA_LEFT, fontSize=20, spaceAfter=4
    )
    meta = ParagraphStyle(
        "meta", parent=styles["Normal"], textColor=colors.grey, fontSize=9
    )
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14)
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4
    )
    h3 = ParagraphStyle(
        "h3", parent=styles["Heading3"], fontSize=11, spaceBefore=6, spaceAfter=1
    )
    small = ParagraphStyle(
        "small", parent=body, fontSize=9, textColor=colors.HexColor("#444444")
    )

    flow: list = [
        Paragraph(_esc(manifest.title), h1),
        Paragraph(f"{_esc(manifest.operator)} · {_esc(manifest.generated_on)}", meta),
        Spacer(1, 6),
    ]
    if manifest.positioning:
        flow += [Paragraph(_esc(manifest.positioning), body), Spacer(1, 4)]

    flow.append(Paragraph("Selected work", h2))
    for e in manifest.entries:
        block: list = [Paragraph(_esc(e.name), h3)]
        line = " · ".join(filter(None, [e.period, e.role, e.client_line]))
        if line:
            block.append(Paragraph(_esc(line), small))
        if e.summary:
            block.append(Paragraph(_esc(e.summary), body))
        if e.tech_stack:
            block.append(
                Paragraph("<b>Stack:</b> " + _esc(", ".join(e.tech_stack)), small)
            )
        for o in e.outcomes:
            block.append(Paragraph("• " + _esc(o), small))
        block.append(Spacer(1, 6))
        flow.append(KeepTogether(block))

    if manifest.tech:
        flow.append(Paragraph("Tech stack", h2))
        rows = [[_esc(t.name), str(t.count)] for t in manifest.tech]
        table = Table(
            [["Technology", "Projects"]] + rows,
            colWidths=[110 * mm, 30 * mm],
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                    ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        flow.append(table)

    if manifest.results:
        r = manifest.results
        flow.append(Paragraph("Upwork results", h2))
        parts = [f"{r.won} proposal{'s' if r.won != 1 else ''} won"]
        if r.lost:
            parts.append(f"{r.lost} not selected")
        if r.withdrawn:
            parts.append(f"{r.withdrawn} withdrawn")
        flow.append(Paragraph(_esc(", ".join(parts)) + ".", body))
        if r.industries_won:
            flow.append(
                Paragraph("Won in: " + _esc(", ".join(r.industries_won)), small)
            )

    pages: list[int] = []
    doc.build(flow, canvasmaker=_numbered_canvas(manifest.footer, pages))
    return buf.getvalue(), (pages[0] if pages else 1)


def pdf_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
