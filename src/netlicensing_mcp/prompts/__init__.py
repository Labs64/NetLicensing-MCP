"""Prompt templates for the NetLicensing MCP server."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import TypeVar

F = TypeVar("F", bound=Callable[..., object])


def clean_doc(fn: F) -> F:
    """Dedent *fn*'s docstring, which FastMCP sends as the prompt description.

    FastMCP uses ``fn.__doc__`` as is. On Python 3.12 that keeps the source
    indentation, and Markdown clients render lines indented by four or more
    spaces as code blocks (3.13+ strips it at compile time). Apply it below
    ``@mcp.prompt(...)``.
    """
    if fn.__doc__:
        fn.__doc__ = inspect.cleandoc(fn.__doc__)
    return fn
