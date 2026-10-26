"""
AI の呼び出しを1か所にまとめる。

Render の環境変数 AI_PROVIDER で切り替える。
    openai（既定）: OpenAI（OPENAI_API_KEY）
    claude        : Claude（ANTHROPIC_API_KEY）

モデルは OPENAI_MODEL / CLAUDE_MODEL で変えられる。
どちらも「JSONスキーマどおりの答え」を返すように頼む。
"""

import json
import os
from dataclasses import dataclass


DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"

DEFAULT_CLAUDE_MODEL = "claude-haiku-5-5"


@dataclass
class AIResult:
    data: dict
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


def provider():

    value = os.environ.get(
        "AI_PROVIDER",
        "openai",
    ).strip().lower()

    return (
        "claude"
        if value in {"claude", "anthropic"}
        else "openai"
    )


def model_name():

    if provider() == "claude":

        return os.environ.get(
            "CLAUDE_MODEL",
            DEFAULT_CLAUDE_MODEL,
        )

    return os.environ.get(
        "OPENAI_MODEL",
        DEFAULT_OPENAI_MODEL,
    )


def generate_json(
    instructions,
    input_text,
    schema,
    name,
    max_tokens,
):
    """
    instructions と input_text を渡し、schema に沿った dict を返す。
    途中で切れた・断られた場合は RuntimeError。
    """

    if provider() == "claude":
        return _claude_json(
            instructions,
            input_text,
            schema,
            max_tokens,
        )

    return _openai_json(
        instructions,
        input_text,
        schema,
        name,
        max_tokens,
    )


def _openai_json(
    instructions,
    input_text,
    schema,
    name,
    max_tokens,
):

    from config.services.openai_client import (
        get_openai_client,
    )

    model = model_name()

    response = get_openai_client().responses.create(
        model=model,

        reasoning={
            "effort": "none",
        },

        instructions=instructions,

        input=input_text,

        text={
            "format": {
                "type": "json_schema",
                "name": name,
                "strict": True,
                "schema": schema,
            }
        },

        max_output_tokens=max_tokens,

        store=False,
    )

    if response.status == "incomplete":

        reason = getattr(
            response.incomplete_details,
            "reason",
            "unknown",
        )

        raise RuntimeError(
            f"OpenAI response incomplete: {reason}"
        )

    usage = response.usage

    return AIResult(
        data=json.loads(
            response.output_text
        ),
        model=model,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
    )


def _claude_client():

    import anthropic

    if not os.environ.get(
        "ANTHROPIC_API_KEY"
    ):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured."
        )

    return anthropic.Anthropic()


def _claude_json(
    instructions,
    input_text,
    schema,
    max_tokens,
):

    model = model_name()

    # 翻訳・分類は考え込む必要がないので、思考なし・effort low で安く速く。
    response = _claude_client().messages.create(
        model=model,

        max_tokens=max_tokens,

        system=instructions,

        messages=[
            {
                "role": "user",
                "content": input_text,
            }
        ],

        thinking={
            "type": "disabled",
        },

        output_config={
            "effort": "low",
            "format": {
                "type": "json_schema",
                "schema": schema,
            },
        },
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(
            "Claude declined the request."
        )

    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            "Claude response incomplete: max_tokens"
        )

    text = next(
        (
            block.text
            for block in response.content
            if block.type == "text"
        ),
        "",
    )

    return AIResult(
        data=json.loads(text),
        model=model,
        input_tokens=response.usage.input_tokens or 0,
        output_tokens=response.usage.output_tokens or 0,
    )
