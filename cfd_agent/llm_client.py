"""Thin, swappable LLM layer. The LLM only extracts parameters from text via a single forced tool call.
It never writes solver files and never decides which pipeline steps run."""
from __future__ import annotations

import os
from typing import Protocol

SYSTEM_PROMPT = (
    "You extract parameters for a lid-driven cavity CFD simulation from a user's request. "
    "Call the tool exactly once. Rules: (1) Set supported=true ONLY if the request is about lid-driven "
    "cavity flow; otherwise supported=false with a short reason. (2) Fill a field ONLY if the user "
    "explicitly stated it; leave it null otherwise - never guess or invent values. (3) Copy numbers exactly "
    "as stated, even if they look unreasonable; validation happens elsewhere. (4) reynolds is the Reynolds "
    "number; grid_n is the number of cells per side of a square grid; lid_velocity is in m/s."
)

TOOL = {
    "name": "submit_cavity_request",
    "description": "Submit the parameters extracted from the user's cavity-flow request.",
    "input_schema": {
        "type": "object",
        "properties": {
            "supported": {"type": "boolean"},
            "reason": {"type": ["string", "null"]},
            "reynolds": {"type": ["number", "null"]},
            "grid_n": {"type": ["integer", "null"]},
            "lid_velocity": {"type": ["number", "null"]},
            "flow_throughs": {"type": ["number", "null"]},
        },
        "required": ["supported"],
    },
}


class LLMClient(Protocol):
    name: str

    def extract(self, request: str, feedback: str | None = None) -> dict: ...


class MockLLM:
    """Scripted LLM for tests. Each call pops the next response (dict) or raises it if it is an Exception."""
    name = "mock-llm"

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def extract(self, request: str, feedback: str | None = None) -> dict:
        self.calls.append((request, feedback))
        if not self.responses:
            raise RuntimeError("MockLLM has no more scripted responses")
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class AnthropicLLM:
    """Anthropic Messages API with a forced tool call. Needs ANTHROPIC_API_KEY in the environment.
    NOTE: written against the public SDK; not exercised against the live API in the original build environment."""

    def __init__(self, model: str | None = None, timeout_s: float = 30.0):
        import anthropic  # optional dependency

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set (read it from the environment; never hardcode it)")
        self.client = anthropic.Anthropic(timeout=timeout_s)
        self.model = model or os.environ.get("CFD_AGENT_MODEL", "claude-sonnet-5-5")
        self.name = f"anthropic:{self.model}"

    def extract(self, request: str, feedback: str | None = None) -> dict:
        content = request if not feedback else (
            f"{request}\n\nYour previous extraction was rejected by validation: {feedback}\n"
            "Re-extract, copying the user's stated values exactly.")
        msg = self.client.messages.create(
            model=self.model, max_tokens=300, system=SYSTEM_PROMPT, tools=[TOOL],
            tool_choice={"type": "tool", "name": TOOL["name"]},
            messages=[{"role": "user", "content": content}],
        )
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                return dict(block.input)
        raise RuntimeError("LLM returned no tool call")
