"""OpenAI-powered conversation utilities for student submissions."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence, Tuple

try:  # newer SDK (>=1.0)
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

try:  # legacy SDK (<1.0)
    import openai  # type: ignore
except ImportError:  # pragma: no cover
    openai = None  # type: ignore

from services.openai_summarizer import SUMMARY_MODELS


CHAT_MODELS: Sequence[tuple[str, str]] = SUMMARY_MODELS


class ConversationError(RuntimeError):
    """Raised when we cannot produce a chat response."""


@dataclass
class ChatResult:
    text: str
    model: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


def _get_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ConversationError("OPENAI_API_KEY is not configured.")
    return api_key


def _normalize_timestamp(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build_context_messages(
    submission,
    user_message: str,
    include_lecturer_summary: bool,
    include_student_summary: bool,
    max_history: Optional[int] = None,
) -> List[dict]:
    """Construct the chat payload with system context, prompts, and history."""
    messages: List[dict] = []

    base_instructions = (
        "You are DiaLoque, an academic teaching assistant helping VU students analyse AI mobility "
        "assignments. Maintain a supportive tone, encourage reflection, and reference the provided "
        "context. Cite insights from lecturer guidance or the student's own analysis when relevant."
    )
    messages.append({"role": "system", "content": base_instructions})

    assignment = submission.assignment

    if include_lecturer_summary:
        lecturer_doc = next((doc for doc in assignment.documents if doc.slot == 1), None)
        if lecturer_doc and lecturer_doc.summary:
            content = (
                "Lecturer summary for this assignment:\n" + lecturer_doc.summary.strip()
            )
            messages.append({"role": "system", "content": content})

    if include_student_summary and submission.summary:
        messages.append(
            {
                "role": "system",
                "content": "Student's submitted summary:\n" + submission.summary.strip(),
            }
        )

    # Conversation history
    history_source = sorted(
        submission.messages,
        key=lambda m: (_normalize_timestamp(m.created_at), m.id or 0),
    )
    if max_history is not None and len(history_source) > max_history:
        history_source = history_source[-max_history:]
    history: Iterable = history_source
    for msg in history:
        if msg.role == "student":
            role = "user"
            content = msg.content
            messages.append({"role": role, "content": content})
        elif msg.role == "assistant":
            messages.append({"role": "assistant", "content": msg.content})
        elif msg.role == "lecturer":
            context = msg.get_context() or {}
            title = context.get("prompt_title")
            example = context.get("example_response")
            prompt_content = msg.content.strip()
            if title:
                header = f"Lecturer prompt ({title}):\n{prompt_content}"
            else:
                header = f"Lecturer prompt:\n{prompt_content}"
            if example:
                header = (
                    f"{header}\n\nExample assistant reply previously shared by the lecturer:\n"
                    f"{example.strip()}"
                )
            messages.append({"role": "system", "content": header})
        else:
            continue

    messages.append({"role": "user", "content": user_message.strip()})
    return messages


def _call_openai(messages: List[dict], model: str) -> ChatResult:
    api_key = _get_api_key()

    if OpenAI is not None:  # new SDK path
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            input=messages,
        )
        text = getattr(response, "output_text", None)
        if not text:
            output = getattr(response, "output", None)
            if output:
                for item in output:
                    for content in getattr(item, "content", []):
                        if getattr(content, "type", None) == "text":
                            value = getattr(getattr(content, "text", None), "value", None)
                            if value:
                                text = value
                                break
                    if text:
                        break
        if not text:
            raise ConversationError("OpenAI response did not contain text output.")

        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "input_tokens", None) if usage else None
        completion_tokens = getattr(usage, "output_tokens", None) if usage else None
        total_tokens = getattr(usage, "total_tokens", None) if usage else None

        return ChatResult(
            text=text.strip(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    if openai is not None:  # legacy SDK path
        openai.api_key = api_key  # type: ignore[attr-defined]
        try:
            response = openai.ChatCompletion.create(  # type: ignore[attr-defined]
                model=model,
                messages=messages,
                temperature=0.4,
                max_tokens=600,
            )
        except AttributeError as exc:  # pragma: no cover
            raise ConversationError(
                "Installed 'openai' package is outdated. Upgrade to >=0.28 or install the new SDK."
            ) from exc

        try:
            text = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ConversationError("OpenAI response did not contain text output.") from exc

        usage = response.get("usage", {})
        return ChatResult(
            text=(text or "").strip(),
            model=model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    raise ConversationError("The 'openai' package is not installed. Run 'pip install openai'.")


def generate_chat_response(
    submission,
    user_message: str,
    model: str,
    include_lecturer_summary: bool = True,
    include_student_summary: bool = True,
) -> ChatResult:
    if model not in {choice for choice, _ in CHAT_MODELS}:
        raise ConversationError(f"Unsupported model '{model}'.")
    if not user_message or not user_message.strip():
        raise ConversationError("Message cannot be empty.")

    messages = _build_context_messages(
        submission=submission,
        user_message=user_message,
        include_lecturer_summary=include_lecturer_summary,
        include_student_summary=include_student_summary,
    )
    return _call_openai(messages, model=model)
