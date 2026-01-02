"""Ollama LLM provider for local models."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import httpx

from src.services.llm.base import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """LLM provider for Ollama local models."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: float = 300.0,
    ):
        """
        Initialize the Ollama provider.

        Args:
            base_url: Ollama server URL
            model: Model name (default: llama3.1:8b)
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "ollama"

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
        """Send a chat request to Ollama."""
        try:
            # Convert messages to Ollama format
            ollama_messages = []

            if system_prompt:
                ollama_messages.append({
                    "role": "system",
                    "content": system_prompt,
                })

            for msg in messages:
                ollama_messages.append(self._convert_message(msg))

            # Build request payload
            payload: dict[str, Any] = {
                "model": self._model,
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            # Add tools if provided (Ollama supports tool calling)
            if tools:
                payload["tools"] = self._convert_tools(tools)

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            # Parse response
            message = data.get("message", {})
            content = message.get("content")
            tool_calls = []

            # Parse tool calls from Ollama response
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    tool_calls.append(
                        ToolCall(
                            id=tc.get("id", str(uuid.uuid4())),
                            name=tc["function"]["name"],
                            arguments=tc["function"].get("arguments", {}),
                        )
                    )

            # Determine stop reason
            stop_reason = "stop"
            if tool_calls:
                stop_reason = "tool_use"
            elif data.get("done_reason") == "length":
                stop_reason = "length"

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                stop_reason=stop_reason,
                usage={
                    "input_tokens": data.get("prompt_eval_count", 0),
                    "output_tokens": data.get("eval_count", 0),
                },
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Ollama request error: {e}")
            raise
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    def _convert_message(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Convert a message to Ollama format."""
        role = msg["role"]
        content = msg.get("content", "")

        # Handle Anthropic-style content blocks
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        # Format tool results
                        tool_content = block.get("content", "")
                        text_parts.append(f"Tool result: {tool_content}")
                    elif block.get("type") == "tool_use":
                        # Skip tool_use blocks in conversion (handled separately)
                        pass
            content = "\n".join(text_parts)

        return {"role": role, "content": content}

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert Anthropic-style tools to Ollama format."""
        ollama_tools = []
        for tool in tools:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
        return ollama_tools

    def format_tool_result(
        self,
        tool_call_id: str,  # noqa: ARG002
        tool_name: str,  # noqa: ARG002
        result: Any,
    ) -> dict[str, Any]:
        """Format a tool result for Ollama."""
        result_str = json.dumps(result, default=str) if not isinstance(result, str) else result
        return {
            "role": "tool",
            "content": result_str,
        }

    def format_assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        """Format Ollama's response as a message."""
        message: dict[str, Any] = {"role": "assistant"}

        if response.content:
            message["content"] = response.content

        if response.tool_calls:
            message["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    },
                }
                for tc in response.tool_calls
            ]

        return message

    async def health_check(self) -> bool:
        """Check if Ollama server is running and model is available."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Check if server is running
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                data = response.json()

                # Check if model is available
                available_models = [m["name"] for m in data.get("models", [])]
                model_base = self._model.split(":")[0]

                for available in available_models:
                    if available.startswith(model_base):
                        return True

                logger.warning(
                    f"Model {self._model} not found. Available: {available_models}"
                )
                return False

        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
