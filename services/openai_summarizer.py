"""Utilities for creating and updating document summaries via OpenAI."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable, Optional, Sequence

from flask import current_app

try:  # OpenAI SDK >= 1.0
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - handled gracefully at runtime
    OpenAI = None  # type: ignore

try:  # OpenAI SDK < 1.0
    import openai  # type: ignore
except ImportError:  # pragma: no cover
    openai = None  # type: ignore

SUMMARY_MODELS: Sequence[tuple[str, str]] = (
    ("gpt-3.5-turbo", "GPT-3.5 Turbo"),
    ("gpt-4o-mini", "GPT-4o Mini"),
    ("gpt-5", "GPT-5"),
)


class SummarizationError(RuntimeError):
    """Raised when we cannot produce a summary."""


@dataclass
class SummaryResult:
    text: str
    model: str


def _get_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SummarizationError("OPENAI_API_KEY is not configured.")
    return api_key


def _extract_text_from_pdf(blob: bytes) -> str:
    if not blob:
        return ""
    # Primary path: parse via pypdf
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(BytesIO(blob))
        pages: Iterable[str] = (page.extract_text() or "" for page in reader.pages)
        text = "\n".join(pages)
        if text.strip():
            return text
    except Exception:
        pass

    # Fallback 1: assume UTF-8 text masquerading as PDF (e.g., test fixtures)
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        # Fallback 2: best-effort decoding
        return blob.decode("latin-1", errors="ignore")


def _truncate_text(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


def _call_openai(text: str, model: str) -> str:
    system_prompt = (
        "You summarise PDF course materials for Vrije Universiteit Amsterdam. "
        "Return a clear, plain-language paragraph (<= 200 words) suitable for lecturers."
    )
    normalized_text = text.strip() or "(Empty document)"

    api_key = _get_api_key()

    if OpenAI is not None:  # SDK >= 1.0
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _truncate_text(normalized_text)},
            ],
        )

        summary = getattr(response, "output_text", None)
        if summary:
            return summary.strip()

        output = getattr(response, "output", None)
        if output:
            for item in output:
                contents = getattr(item, "content", [])
                for content in contents:
                    if getattr(content, "type", None) == "text":
                        value = getattr(getattr(content, "text", None), "value", None)
                        if value:
                            return value.strip()
        raise SummarizationError("OpenAI response did not contain text output.")

    if openai is not None:  # SDK < 1.0
        openai.api_key = api_key  # type: ignore[attr-defined]
        try:
            response = openai.ChatCompletion.create(  # type: ignore[attr-defined]
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": _truncate_text(normalized_text)},
                ],
                temperature=0.2,
                max_tokens=400,
            )
        except AttributeError as exc:  # pragma: no cover - defensive
            raise SummarizationError(
                "Installed 'openai' package is too old. Upgrade to >=0.28 or use the new SDK."
            ) from exc

        try:
            summary = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - defensive
            raise SummarizationError("OpenAI response did not contain text output.") from exc
        return (summary or "").strip()

    raise SummarizationError("The 'openai' package is not installed. Run 'pip install openai'.")


def summarise_document_content(content: bytes, model: str) -> SummaryResult:
    if model not in {choice for choice, _ in SUMMARY_MODELS}:
        raise SummarizationError(f"Unsupported model '{model}'.")

    text = _extract_text_from_pdf(content)
    if not text.strip():
        raise SummarizationError("Could not extract text from the document.")

    summary_text = _call_openai(text, model=model)
    return SummaryResult(text=summary_text, model=model)


def summarise_assignment_document(document, model: str) -> SummaryResult:
    if not document or not document.content:
        raise SummarizationError("Document payload is missing.")

    result = summarise_document_content(document.content, model=model)
    document.set_summary(result.text, model)
    return result
