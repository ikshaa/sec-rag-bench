"""
Multi-provider LLM gateway with automatic fallback.

Primary: Anthropic Claude Haiku 4.5
Fallback: OpenAI gpt-4o-mini

Automatic fallback on retryable errors (rate limit, server error, timeout,
overload). Returns which provider actually served the request so callers
can log and measure the provider mix in observability dashboards.
"""

import os
from dataclasses import dataclass
from typing import Literal

import anthropic
import openai
from dotenv import load_dotenv

load_dotenv()

PRIMARY_MODEL = "claude-haiku-4-5"
FALLBACK_MODEL = "gpt-4o-mini"
MAX_TOKENS = 1024


# ---------------------------------------------------------------------------
# Lazy clients
# ---------------------------------------------------------------------------

_anthropic_client = None
_openai_client = None


def _anthropic() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _openai() -> openai.OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.OpenAI()
    return _openai_client


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

@dataclass
class GatewayResponse:
    text: str
    provider: Literal["anthropic", "openai"]
    model: str
    fallback_used: bool
    primary_error: str | None = None


# ---------------------------------------------------------------------------
# Provider-specific calls
# ---------------------------------------------------------------------------

def _call_anthropic(prompt: str) -> str:
    client = _anthropic()
    response = client.messages.create(
        model=PRIMARY_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _call_openai(prompt: str) -> str:
    client = _openai()
    response = client.chat.completions.create(
        model=FALLBACK_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Fallback logic
# ---------------------------------------------------------------------------

def _is_retryable_error(e: Exception) -> bool:
    """
    Should we fall back to the other provider on this error?
    True for rate limits, overloaded, timeouts, and 5xx server errors.
    False for auth failures, bad prompts, etc. (user error, won't recover).
    """
    error_str = str(e).lower()
    retryable_markers = [
        "rate_limit", "ratelimit", "429",
        "overloaded", "529",
        "timeout",
        "500", "502", "503", "504",
        "server_error", "internal_server",
    ]
    return any(marker in error_str for marker in retryable_markers)


def generate(prompt: str) -> GatewayResponse:
    """
    Call the primary LLM. On retryable errors, fall back to the secondary.
    If both fail or the error is non-retryable, raises the original exception.
    """
    try:
        text = _call_anthropic(prompt)
        return GatewayResponse(
            text=text,
            provider="anthropic",
            model=PRIMARY_MODEL,
            fallback_used=False,
        )
    except Exception as primary_error:
        if not _is_retryable_error(primary_error):
            # Non-retryable: auth failure, bad request, etc.
            raise

        # Try the fallback
        try:
            text = _call_openai(prompt)
            return GatewayResponse(
                text=text,
                provider="openai",
                model=FALLBACK_MODEL,
                fallback_used=True,
                primary_error=f"{type(primary_error).__name__}: {primary_error}",
            )
        except Exception:
            # Both providers failed. Raise the primary error so caller knows
            # the main service is the problem.
            raise primary_error