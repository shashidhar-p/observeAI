"""Fixture loader utility for loading JSON test data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).parent


def load_fixture(name: str) -> dict[str, Any]:
    """
    Load a JSON fixture by name.

    Args:
        name: Fixture name without .json extension

    Returns:
        Parsed JSON data as dictionary

    Raises:
        FileNotFoundError: If fixture file doesn't exist
        json.JSONDecodeError: If fixture contains invalid JSON
    """
    fixture_path = FIXTURES_DIR / f"{name}.json"
    with open(fixture_path) as f:
        return json.load(f)


def load_fixture_raw(name: str) -> str:
    """
    Load a fixture file as raw string.

    Args:
        name: Fixture name without .json extension

    Returns:
        Raw file contents as string
    """
    fixture_path = FIXTURES_DIR / f"{name}.json"
    with open(fixture_path) as f:
        return f.read()


def list_fixtures() -> list[str]:
    """
    List all available fixture names.

    Returns:
        List of fixture names (without .json extension)
    """
    return [f.stem for f in FIXTURES_DIR.glob("*.json")]


def fixture_exists(name: str) -> bool:
    """
    Check if a fixture exists.

    Args:
        name: Fixture name without .json extension

    Returns:
        True if fixture file exists
    """
    return (FIXTURES_DIR / f"{name}.json").exists()
