from ht_mcp.server import mcp, ping
from mcp.server.fastmcp import FastMCP


def test_mcp_app_is_fastmcp():
    assert isinstance(mcp, FastMCP)


def test_ping_returns_ok():
    assert ping() == {"status": "ok"}
