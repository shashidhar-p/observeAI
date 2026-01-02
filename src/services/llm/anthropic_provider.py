"""Anthropic Claude LLM provider."""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from src.services.llm.base import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """LLM provider for Anthropic Claude models."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        timeout: float = 120.0,
    ):
        """
        Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model name (default: claude-sonnet-4-20250514)
            timeout: Request timeout in seconds
        """
        self._model = model
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=timeout,
        )

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Send a chat request to Claude."""
        try:
            # Build request kwargs
            kwargs: dict[str, Any] = {
                "model": self._model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            if tools:
                kwargs["tools"] = tools

            # Make the API call
            response = await self._client.messages.create(**kwargs)

            # Parse response
            content = None
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    content = block.text
                elif block.type == "tool_use":
                    tool_calls.append(
                        ToolCall(
                            id=block.id,
                            name=block.name,
                            arguments=block.input if isinstance(block.input, dict) else {},
                        )
                    )

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                stop_reason=response.stop_reason,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                raw_response=response,
            )

        except anthropic.RateLimitError as e:
            logger.warning(f"Rate limit hit: {e}")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def format_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,  # noqa: ARG002
        result: Any,
    ) -> dict[str, Any]:
        """Format a tool result for Claude."""
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": json.dumps(result, default=str) if not isinstance(result, str) else result,
                }
            ],
        }

    def format_assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        """Format Claude's response as a message."""
        content = []

        if response.content:
            content.append({"type": "text", "text": response.content})

        for tool_call in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tool_call.id,
                "name": tool_call.name,
                "input": tool_call.arguments,
            })

        return {"role": "assistant", "content": content}
