"""netlicensing-mcp — official Labs64 NetLicensing MCP server."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("netlicensing-mcp")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "unknown"
