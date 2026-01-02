"""Configuration management for the RCA system."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://rca:rca@localhost:5432/rca_db",
        description="PostgreSQL connection URL",
    )

    # Observability backends
    loki_url: str = Field(
        default="http://localhost:3100",
        description="Loki server URL",
    )
    cortex_url: str = Field(
        default="http://localhost:9009",
        description="Cortex server URL",
    )

    # LLM Provider Configuration
    llm_provider: str = Field(
        default="anthropic",
        description="LLM provider to use: 'anthropic', 'ollama', or 'gemini'",
    )

    # Anthropic Configuration
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude",
    )
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Anthropic model to use",
    )

    # Ollama Configuration
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL",
    )
    ollama_model: str = Field(
        default="llama3.1:8b",
        description="Ollama model to use",
    )
    ollama_timeout_seconds: int = Field(
        default=300,
        description="Ollama request timeout (local models are slower)",
    )

    # Gemini Configuration
    gemini_api_key: str = Field(
        default="",
        description="Google AI API key for Gemini (free tier available)",
    )
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model to use (gemini-2.0-flash is free tier)",
    )
    gemini_timeout_seconds: int = Field(
        default=120,
        description="Gemini API request timeout",
    )

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")

    # RCA Configuration
    correlation_window_seconds: int = Field(
        default=300,
        description="Time window (in seconds) for correlating related alerts",
    )
    rca_max_iterations: int = Field(
        default=10,
        description="Maximum iterations for the RCA agent loop",
    )
    log_level: str = Field(default="INFO", description="Logging level")

    # Optimization settings
    semantic_correlation_enabled: bool = Field(
        default=True,
        description="Enable LLM-based semantic correlation (disable to reduce API calls)",
    )
    correlation_score_threshold: int = Field(
        default=8,
        description="Skip semantic analysis if label-based score is above this threshold",
    )

    # RCA Expert Context - Configurable domain expertise for the RCA agent
    rca_expert_context: str = Field(
        default="",
        description="Custom expert context/knowledge to inject into RCA agent. Leave empty for generic SRE.",
    )
    rca_expert_context_file: str = Field(
        default="",
        description="Path to file containing expert context (overrides rca_expert_context if set).",
    )

    # Timeouts
    loki_timeout_seconds: int = Field(default=30, description="Loki query timeout")
    cortex_timeout_seconds: int = Field(default=30, description="Cortex query timeout")
    claude_timeout_seconds: int = Field(default=120, description="Claude API timeout")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
