"""Emerald Exchange entry point."""

from emerald_exchange.mcp_server import mcp_server

if __name__ == "__main__":
    server = mcp_server()
    server.run(transport="stdio")
