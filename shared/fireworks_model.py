"""Explicit Muse Spark Open transport; same runtime, tool and budget boundaries.

No automatic fallback from Meta. Provider reasoning stays in private replay data,
never ModelTurn.text; encrypted Meta state cannot be translated across providers.
"""

import re
from types import SimpleNamespace

from openai import APIStatusError, OpenAI

from contracts.models import ModelTurn
from shared.model_client import ModelCallFailed

MODEL = "accounts/fireworks/models/muse-spark-open"
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


def _identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid tool identifier")
    return value


def _text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise ValueError("Text-only model context required")
    parts = []
    for part in content:
        if (
            not isinstance(part, dict)
            or part.get("type") not in {"input_text", "output_text"}
            or not isinstance(part.get("text"), str)
        ):
            raise ValueError("Unsupported model content")
        parts.append(part["text"])
    return "".join(parts)


def chat_messages(history):
    """Translate the canonical, task-scoped transcript without orphaned tool results."""
    messages, assistant = [], None
    pending, seen = set(), set()

    def flush():
        nonlocal assistant
        if assistant is not None:
            messages.append(assistant)
            assistant = None

    for item in history:
        kind = item.get("type")
        if kind == "reasoning":
            raise ValueError("Meta reasoning state cannot be replayed through Fireworks")
        if kind == "function_call":
            identifier = _identifier(item.get("call_id"))
            name = _identifier(item.get("name"))
            arguments = item.get("arguments")
            if identifier in seen or not isinstance(arguments, str):
                raise ValueError("Invalid or duplicate tool call")
            if assistant is None:
                if pending:
                    raise ValueError("Previous tool results are incomplete")
                assistant = {"role": "assistant", "content": None}
            assistant.setdefault("tool_calls", []).append(
                {
                    "id": identifier,
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }
            )
            pending.add(identifier)
            seen.add(identifier)
        elif kind == "function_call_output":
            flush()
            identifier = _identifier(item.get("call_id"))
            if identifier not in pending or not isinstance(item.get("output"), str):
                raise ValueError("Orphaned or duplicate tool result")
            messages.append({"role": "tool", "tool_call_id": identifier, "content": item["output"]})
            pending.remove(identifier)
        elif kind in {None, "message"}:
            flush()
            if pending:
                raise ValueError("Tool results must precede the next message")
            role = item.get("role")
            if role not in {"system", "developer", "user", "assistant"}:
                raise ValueError("Unsupported message role")
            message = {"role": role, "content": _text(item.get("content"))}
            reasoning = item.get("fireworks_reasoning_content")
            if reasoning is not None:
                if (
                    role != "assistant"
                    or item.get("provider") != "fireworks"
                    or not isinstance(reasoning, str)
                ):
                    raise ValueError("Invalid provider replay context")
                message["reasoning_content"] = reasoning
            if role == "assistant":
                assistant = message
            else:
                messages.append(message)
        else:
            raise ValueError("Unsupported replay item")
    flush()
    if pending or not messages:
        raise ValueError("Incomplete model context")
    return messages


def chat_tools(tools):
    result, names = [], set()
    for tool in tools:
        name = _identifier(tool.get("name"))
        if (
            tool.get("type") != "function"
            or name in names
            or not isinstance(tool.get("parameters"), dict)
        ):
            raise ValueError("Unsupported or duplicate model tool")
        names.add(name)
        result.append(
            {
                "type": "function",
                "function": {
                    key: tool[key]
                    for key in ("name", "description", "parameters", "strict")
                    if key in tool
                },
            }
        )
    return result


class FireworksModelClient:
    def __init__(self, settings):
        if not settings.fireworks_api_key:
            raise RuntimeError("AGENT_FIREWORKS_API_KEY is not configured")
        if settings.meta_reasoning_effort not in {None, "low", "medium", "high"}:
            raise ValueError("Unsupported Fireworks reasoning effort")
        self.max_output_tokens = settings.meta_max_output_tokens
        self._reasoning_effort = settings.meta_reasoning_effort
        self._client = OpenAI(
            api_key=settings.fireworks_api_key.get_secret_value(),
            base_url="https://api.fireworks.ai/inference/v1",
            timeout=30,
            max_retries=0,
        )

    def turn(self, history, tools):
        messages, definitions = chat_messages(history), chat_tools(tools)
        options = {"reasoning_effort": self._reasoning_effort} if self._reasoning_effort else {}
        try:
            response = self._client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=definitions or None,
                max_tokens=self.max_output_tokens,
                n=1,
                # Reject overflow rather than silently shrinking the output budget.
                extra_body={"context_length_exceeded_behavior": "error"},
                **options,
            )
        except APIStatusError as exc:
            raise ModelCallFailed(
                status="http_error", http_status=exc.status_code, code=exc.code
            ) from None
        usage = response.usage
        known = usage is not None and all(
            type(getattr(usage, key, None)) is int and getattr(usage, key) >= 0
            for key in ("prompt_tokens", "completion_tokens")
        )
        safe_usage = (
            SimpleNamespace(input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens)
            if known
            else None
        )
        if len(response.choices) != 1:
            raise ModelCallFailed(status="failed", usage=safe_usage)
        choice = response.choices[0]
        if choice.finish_reason not in {"stop", "tool_calls"}:
            raise ModelCallFailed(
                status="incomplete" if choice.finish_reason == "length" else "failed",
                usage=safe_usage,
                incomplete_reason="max_output_tokens" if choice.finish_reason == "length" else None,
            )
        message = choice.message
        text, calls = message.content or "", message.tool_calls or []
        if (
            message.refusal
            or (choice.finish_reason == "tool_calls") != bool(calls)
            or not (text.strip() or calls)
            or "<think>" in text.lower()
            or "</think>" in text.lower()
        ):
            raise ModelCallFailed(status="failed", usage=safe_usage)
        output = [
            {
                "type": "message",
                "role": "assistant",
                "provider": "fireworks",
                "content": [{"type": "output_text", "text": text}] if text else [],
            }
        ]
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning is not None:
            if not isinstance(reasoning, str):
                raise ModelCallFailed(status="failed", usage=safe_usage)
            output[0]["fireworks_reasoning_content"] = reasoning
        names, identifiers = {tool["name"] for tool in tools}, set()
        for call in calls:
            if (
                call.type != "function"
                or call.function.name not in names
                or call.id in identifiers
                or not isinstance(call.function.arguments, str)
            ):
                raise ModelCallFailed(status="failed", usage=safe_usage)
            _identifier(call.id)
            _identifier(call.function.name)
            identifiers.add(call.id)
            output.append(
                {
                    "type": "function_call",
                    "call_id": call.id,
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                }
            )
        return ModelTurn(
            output=output,
            text=text,
            input_tokens=usage.prompt_tokens if known else 0,
            output_tokens=usage.completion_tokens if known else 0,
            usage_known=known,
        )
