"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: Any = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0

    @property
    def is_complete(self) -> bool:
        """Check if the LLM has finished (no more tool calls)."""
        return self.stop_reason in ("end_turn", "stop", "length") and not self.has_tool_calls


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the model being used."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """
        Send a chat request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            LLMResponse with content and/or tool calls
        """
        pass

    @abstractmethod
    def format_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: Any,
    ) -> dict[str, Any]:
        """
        Format a tool result for the next message.

        Args:
            tool_call_id: The ID of the tool call
            tool_name: Name of the tool
            result: The tool's result

        Returns:
            Formatted message dict for the conversation
        """
        pass

    @abstractmethod
    def format_assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        """
        Format the assistant's response as a message for conversation history.

        Args:
            response: The LLM response

        Returns:
            Formatted message dict
        """
        pass

    async def health_check(self) -> bool:
        """Check if the provider is available."""
        try:
            response = await self.chat(
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=10,
            )
            return response.content is not None
        except Exception:
            return False
