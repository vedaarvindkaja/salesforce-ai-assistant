"""
Claude API client with streaming, tool-use agentic loop, and cost tracking.

Owns the multi-turn conversation mechanics:
  1. Send messages to Claude
  2. Stream text to caller as it arrives
  3. Detect tool_use blocks in the response
  4. Dispatch tool calls to registered handlers
  5. Feed results back to Claude
  6. Repeat until stop_reason == "end_turn" or max_iterations reached

Tool handlers are registered externally (tool_definitions.py injects them).
This keeps the client generic — it knows nothing about Salesforce.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Awaitable
from dataclasses import dataclass, field
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing (claude-sonnet-4-6, per million tokens, as of 2025-05)
# Update here if you switch models or Anthropic changes rates.
# ---------------------------------------------------------------------------
MODEL_ID = "claude-sonnet-4-6"

_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input_per_mtok": 3.00,
        "output_per_mtok": 15.00,
    },
    "claude-opus-4-7": {
        "input_per_mtok": 15.00,
        "output_per_mtok": 75.00,
    },
}


def _cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _PRICING.get(model, _PRICING[MODEL_ID])
    return (
        input_tokens / 1_000_000 * rates["input_per_mtok"]
        + output_tokens / 1_000_000 * rates["output_per_mtok"]
    )


# ---------------------------------------------------------------------------
# Usage tracking — in-memory, session-scoped
# ---------------------------------------------------------------------------
@dataclass
class TurnUsage:
    """Token usage and cost for a single Claude turn."""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class SessionUsage:
    """Cumulative usage across all turns in a session."""
    turns: list[TurnUsage] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(t.input_tokens for t in self.turns)

    @property
    def total_output_tokens(self) -> int:
        return sum(t.output_tokens for t in self.turns)

    @property
    def total_cost_usd(self) -> float:
        return sum(t.cost_usd for t in self.turns)

    def record(self, usage: anthropic.types.Usage, model: str) -> TurnUsage:
        turn = TurnUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=_cost_usd(model, usage.input_tokens, usage.output_tokens),
        )
        self.turns.append(turn)
        return turn

    def summary(self) -> str:
        return (
            f"Session: {len(self.turns)} turn(s) | "
            f"{self.total_input_tokens:,} in + {self.total_output_tokens:,} out tokens | "
            f"${self.total_cost_usd:.4f}"
        )


# ---------------------------------------------------------------------------
# Tool handler type
# ---------------------------------------------------------------------------
# A tool handler is an async callable that receives the tool input dict
# and returns a string result to feed back to Claude.
ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


# ---------------------------------------------------------------------------
# Claude client
# ---------------------------------------------------------------------------
class ClaudeClient:
    """
    Async Claude client with streaming, agentic tool loop, and cost tracking.

    Usage:
        client = ClaudeClient()
        client.register_tool("find_dependencies", my_handler)

        async for chunk in client.ask("What depends on AccountService?", tools=[...]):
            print(chunk, end="", flush=True)

        print(client.session.summary())
    """

    def __init__(
        self,
        model: str = MODEL_ID,
        max_tokens: int = 4096,
        max_iterations: int = 10,
        system_prompt: str | None = None,
    ) -> None:
        self._anthropic = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
        self.model = model
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.session = SessionUsage()
        self._tool_handlers: dict[str, ToolHandler] = {}

    def register_tool(self, name: str, handler: ToolHandler) -> None:
        """Register an async handler for a named tool."""
        self._tool_handlers[name] = handler

    async def ask(
        self,
        user_message: str,
        tools: list[dict[str, Any]] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """
        Send a user message and yield streamed text chunks.

        Runs the full agentic loop:
          - streams Claude's text response
          - if Claude calls tools, dispatches them and continues
          - yields text from every Claude turn
          - stops when Claude says end_turn or max_iterations hit
        """
        messages: list[dict[str, Any]] = list(conversation_history or [])
        messages.append({"role": "user", "content": user_message})
        active_tools = tools or []

        for iteration in range(self.max_iterations):
            logger.debug("Agentic loop iteration %d", iteration + 1)

            text_chunks: list[str] = []
            tool_uses: list[anthropic.types.ToolUseBlock] = []
            final_message: anthropic.types.Message | None = None

            # Stream this turn
            async with self._anthropic.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=messages,
                tools=active_tools,
            ) as stream:
                async for text in stream.text_stream:
                    text_chunks.append(text)
                    yield text

                final_message = await stream.get_final_message()

            # Record usage
            if final_message:
                turn_usage = self.session.record(final_message.usage, self.model)
                logger.debug(
                    "Turn %d: %d in / %d out tokens | $%.4f",
                    iteration + 1,
                    turn_usage.input_tokens,
                    turn_usage.output_tokens,
                    turn_usage.cost_usd,
                )

            if final_message is None:
                break

            # Collect tool use blocks
            for block in final_message.content:
                if block.type == "tool_use":
                    tool_uses.append(block)

            stop_reason = final_message.stop_reason

            if stop_reason == "end_turn" or not tool_uses:
                break

            # Append Claude's turn (including tool_use blocks) to history
            messages.append({"role": "assistant", "content": final_message.content})

            # Dispatch tool calls and collect results
            tool_results = await self._dispatch_tools(tool_uses)
            messages.append({"role": "user", "content": tool_results})

        else:
            logger.warning("Reached max_iterations (%d) — stopping loop", self.max_iterations)

    async def _dispatch_tools(
        self, tool_uses: list[anthropic.types.ToolUseBlock]
    ) -> list[dict[str, Any]]:
        """Run all tool calls concurrently and return tool_result blocks."""
        async def _call_one(tool_use: anthropic.types.ToolUseBlock) -> dict[str, Any]:
            handler = self._tool_handlers.get(tool_use.name)
            if handler is None:
                result = f"Error: no handler registered for tool '{tool_use.name}'"
                logger.error(result)
            else:
                try:
                    result = await handler(tool_use.input)
                except Exception as exc:
                    result = f"Error executing tool '{tool_use.name}': {exc}"
                    logger.exception("Tool handler failed: %s", tool_use.name)

            return {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            }

        return list(await asyncio.gather(*(_call_one(t) for t in tool_uses)))


# ---------------------------------------------------------------------------
# Default system prompt
# ---------------------------------------------------------------------------
_DEFAULT_SYSTEM_PROMPT = """You are an AI assistant embedded in a Salesforce developer intelligence platform.
You have access to tools that can query a metadata graph built from a real Salesforce org.
The graph contains Apex classes, triggers, objects, and flows with their dependencies.

When answering questions:
- Use tools to look up real metadata rather than guessing
- Be specific: name the actual classes, objects, and flows involved
- When showing dependencies, explain WHY the relationship exists (SOQL query, method call, Flow action, etc.)
- Keep answers concise and developer-focused

Available graph node types: APEX_CLASS, APEX_TRIGGER, OBJECT, FLOW
Available edge types: REFERENCES (name reference), CALLS (method call), USES_OBJECT (SOQL/DML)
"""
