"""Utilities to export assignment conversations to PDF."""
from __future__ import annotations

from io import BytesIO
from typing import Iterable, Optional

from fpdf import FPDF
from fpdf.enums import XPos, YPos
import unicodedata


def _sanitize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return normalized.encode("latin-1", "ignore").decode("latin-1")


class ConversationPDF:
    def __init__(self, title: str = "DiaLoque Conversation") -> None:
        self._pdf = FPDF()
        self._pdf.set_auto_page_break(auto=True, margin=15)
        self._pdf.add_page()
        self._pdf.set_title(title)
        self._pdf.set_font("Helvetica", "B", 16)
        self._pdf.cell(0, 10, _sanitize(title), ln=True)
        self._pdf.ln(4)

    def add_heading(self, text: str) -> None:
        self._pdf.set_font("Helvetica", "B", 13)
        self._pdf.cell(0, 9, _sanitize(text), ln=True)
        self._pdf.ln(1)

    def add_paragraph(self, text: str) -> None:
        self._pdf.set_font("Helvetica", "", 11)
        self._pdf.multi_cell(self._pdf.epw, 6, _sanitize(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self._pdf.ln(2)

    def add_conversation(self, messages: Iterable[dict]) -> None:
        for message in messages:
            role = message.get("role", "user")
            speaker = "DiaLoque" if role == "assistant" else "Student"
            content = message.get("content", "").strip()
            timestamp = message.get("timestamp")

            header = f"{speaker}"
            if timestamp:
                header += f" · {timestamp}"

            self._pdf.set_font("Helvetica", "B", 11)
            sanitized_header = _sanitize(header)
            if not sanitized_header.strip():
                sanitized_header = speaker
            self._pdf.multi_cell(self._pdf.epw, 6, sanitized_header, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self._pdf.set_font("Helvetica", "", 11)
            display_content = content if content else "(No content)"
            sanitized_content = _sanitize(display_content)
            if not sanitized_content.strip():
                sanitized_content = "(Content unavailable)"
            self._pdf.multi_cell(self._pdf.epw, 6, sanitized_content, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self._pdf.ln(2)

    def output(self) -> BytesIO:
        raw = self._pdf.output(dest="S")
        if isinstance(raw, str):
            pdf_bytes = raw.encode("latin1")
        else:
            pdf_bytes = bytes(raw)
        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)
        return buffer


def build_conversation_pdf(
    assignment_title: str,
    lecturer_summary: Optional[str],
    lecturer_model: Optional[str],
    student_summary: Optional[str],
    student_model: Optional[str],
    conversation: Iterable[dict],
) -> BytesIO:
    pdf = ConversationPDF(title=f"DiaLoque Session · {assignment_title}")

    pdf.add_heading("Lecturer Summary")
    if lecturer_summary:
        summary_text = lecturer_summary
        if lecturer_model:
            summary_text += f"\n\n(Model: {lecturer_model})"
        pdf.add_paragraph(summary_text)
    else:
        pdf.add_paragraph("No lecturer summary available.")

    pdf.add_heading("Student Summary")
    if student_summary:
        summary_text = student_summary
        if student_model:
            summary_text += f"\n\n(Model: {student_model})"
        pdf.add_paragraph(summary_text)
    else:
        pdf.add_paragraph("No student summary available.")

    pdf.add_heading("Conversation")
    pdf.add_conversation(conversation)

    return pdf.output()
