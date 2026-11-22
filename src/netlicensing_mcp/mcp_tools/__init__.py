"""MCP tool wrappers, one module per NetLicensing entity.

Each module registers its tools on the shared FastMCP instance from
``netlicensing_mcp.app`` when imported. ``netlicensing_mcp.server`` imports
them in a fixed order, which is the order tools are listed to clients.
"""
