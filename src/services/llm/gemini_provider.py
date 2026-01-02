"""Google Gemini LLM provider using the new google-genai SDK."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from src.services.llm.base import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider for Google Gemini models (including free tier)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = 120.0,
    ):
        """
        Initialize the Gemini provider.

        Args:
            api_key: Google AI API key
            model: Model name (default: gemini-2.0-flash for free tier)
                   Options: gemini-2.0-flash, gemini-2.5-flash, gemini-2.5-pro
            timeout: Request timeout in seconds
        """
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError(
                "google-genai package is required for Gemini provider. "
                "Install it with: pip install google-genai"
            )

        # Ensure model name has the models/ prefix
        self._model_name = model if model.startswith("models/") else f"models/{model}"
        self._timeout = timeout
        self._types = types

        # Create the client with API key
        self._client = genai.Client(api_key=api_key)

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model_name

    def _convert_tools_to_gemini_format(
        self, tools: list[dict[str, Any]]
    ) -> list[Any]:
        """Convert Anthropic-style tool definitions to Gemini format."""
        gemini_tools = []

        for tool in tools:
            # Convert input_schema to Gemini's parameters format
            input_schema = tool.get("input_schema", {})

            # Build function declaration
            func_decl = self._types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=input_schema,
            )
            gemini_tools.append(func_decl)

        return gemini_tools

    def _convert_messages_to_gemini_format(
        self, messages: list[dict[str, Any]]
    ) -> list[Any]:
        """Convert messages to Gemini's content format."""
        gemini_contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Map roles
            gemini_role = "model" if role == "assistant" else "user"

            # Handle different content formats
            if isinstance(content, str):
                gemini_contents.append(
                    self._types.Content(
                        role=gemini_role,
                        parts=[self._types.Part.from_text(text=content)]
                    )
                )
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            parts.append(
                                self._types.Part.from_text(text=block.get("text", ""))
                            )
                        elif block.get("type") == "tool_use":
                            # Function call from assistant
                            parts.append(
                                self._types.Part.from_function_call(
                                    name=block.get("name", ""),
                                    args=block.get("input", {}),
                                )
                            )
                        elif block.get("type") == "tool_result":
                            # Function response
                            tool_content = block.get("content", "")
                            if isinstance(tool_content, str):
                                try:
                                    tool_content = json.loads(tool_content)
                                except json.JSONDecodeError:
                                    tool_content = {"result": tool_content}

                            parts.append(
                                self._types.Part.from_function_response(
                                    name=block.get("tool_name", "tool"),
                                    response=tool_content,
                                )
                            )

                if parts:
                    gemini_contents.append(
                        self._types.Content(role=gemini_role, parts=parts)
                    )

        return gemini_contents

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Send a chat request to Gemini."""
        try:
            # Build generation config
            generation_config = self._types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                system_instruction=system_prompt if system_prompt else None,
            )

            # Add tools if provided
            if tools:
                gemini_tools = self._convert_tools_to_gemini_format(tools)
                generation_config.tools = [self._types.Tool(function_declarations=gemini_tools)]

            # Convert messages to Gemini format
            gemini_contents = self._convert_messages_to_gemini_format(messages)

            # Make the API call using the async client method
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=gemini_contents,
                config=generation_config,
            )

            # Parse response
            content = None
            tool_calls = []

            # Check if response has candidates
            if response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.text:
                            content = part.text
                        elif part.function_call:
                            fc = part.function_call
                            # Convert args to dict
                            args = dict(fc.args) if fc.args else {}

                            tool_calls.append(
                                ToolCall(
                                    id=str(uuid.uuid4()),
                                    name=fc.name,
                                    arguments=args,
                                )
                            )

            # Determine stop reason
            stop_reason = "stop"
            if tool_calls:
                stop_reason = "tool_use"
            elif response.candidates:
                finish_reason = response.candidates[0].finish_reason
                if finish_reason:
                    # Map Gemini finish reasons to our standard
                    reason_map = {
                        "STOP": "stop",
                        "MAX_TOKENS": "length",
                        "SAFETY": "safety",
                        "RECITATION": "recitation",
                        "OTHER": "other",
                    }
                    stop_reason = reason_map.get(str(finish_reason), "stop")

            # Get usage info
            usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = {
                    "input_tokens": response.usage_metadata.prompt_token_count or 0,
                    "output_tokens": response.usage_metadata.candidates_token_count or 0,
                }

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                stop_reason=stop_reason,
                usage=usage,
                raw_response=response,
            )

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    def format_tool_result(
        self,
        tool_call_id: str,  # noqa: ARG002
        tool_name: str,
        result: Any,
    ) -> dict[str, Any]:
        """Format a tool result for Gemini."""
        result_str = json.dumps(result, default=str) if not isinstance(result, str) else result

        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "content": result_str,
                }
            ],
        }

    def format_assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        """Format Gemini's response as a message."""
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

    async def health_check(self) -> bool:
        """Check if Gemini API is available."""
        try:
            response = await self.chat(
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=10,
            )
            return response.content is not None
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return False
