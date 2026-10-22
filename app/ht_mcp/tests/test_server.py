import pytest
from ht_mcp import server
from ht_mcp.catalog_client import CatalogClient
from ht_mcp.server import mcp, ping
from mcp.server.fastmcp import FastMCP


def test_mcp_app_is_fastmcp():
    assert isinstance(mcp, FastMCP)


def test_ping_returns_ok():
    assert ping() == {"status": "ok"}


@pytest.mark.asyncio
async def test_lifespan_closes_catalog_client_on_shutdown(monkeypatch):
    # Use a throwaway client so the shared module-level one stays open for other tests.
    client = CatalogClient(base_url="http://catalog-test")
    monkeypatch.setattr(server, "catalog", client)

    async with server.lifespan(server.create_app()):
        assert not client._client.is_closed

    assert client._client.is_closed
