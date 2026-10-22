import json
from pathlib import Path

import httpx
import pytest
import respx
from ht_mcp import server
from ht_mcp.catalog_client import VALID_FIELDS, CatalogClient
from ht_mcp.server import mcp, ping
from mcp.server.fastmcp import FastMCP

SINGLE_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "volumes_brief_single.json").read_text()
)
BATCH_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "volumes_brief_batch.json").read_text()
)
BASE_URL = "http://catalog-test"


@pytest.fixture
async def catalog(monkeypatch):
    """Point the server's module-level catalog at a test URL; closed again after the test."""
    client = CatalogClient(base_url=BASE_URL)
    monkeypatch.setattr(server, "catalog", client)
    yield client
    await client.close()


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


# --- health ---


@pytest.mark.asyncio
async def test_health_ok_when_catalog_reachable(catalog):
    with respx.mock(base_url=BASE_URL) as mock:
        # A 404 is a normal "not found" answer, so the catalog counts as reachable.
        mock.get("/api/volumes/brief/htid/probe.json").mock(return_value=httpx.Response(404))
        result = await server.health()

    assert result == {"status": "ok", "catalog": "reachable"}


@pytest.mark.asyncio
async def test_health_degraded_on_http_500(catalog):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/htid/probe.json").mock(return_value=httpx.Response(500))
        result = await server.health()

    assert result["status"] == "degraded"
    assert "HTTP 500" in result["catalog"]


@pytest.mark.asyncio
async def test_health_degraded_when_unreachable(catalog):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/htid/probe.json").mock(
            side_effect=httpx.ConnectError("refused")
        )
        result = await server.health()

    assert result["status"] == "degraded"
    assert "unreachable" in result["catalog"]


@pytest.mark.asyncio
async def test_health_degraded_on_unexpected_error(catalog):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/htid/probe.json").mock(
            return_value=httpx.Response(200, text="not json")
        )
        result = await server.health()

    assert result["status"] == "degraded"
    assert result["catalog"].startswith("unexpected error:")


# --- describe_catalog ---


def test_describe_catalog_lists_identifier_fields():
    result = server.describe_catalog()

    assert result["supported_identifier_fields"] == sorted(VALID_FIELDS)


def test_describe_catalog_includes_rights_codes_and_url_patterns():
    result = server.describe_catalog()

    assert result["rights_attributes"]["pd"] == "public domain"
    assert "{htid}" in result["item_url_pattern"]
    assert "{recordid}" in result["record_url_pattern"]


# --- lookup_single ---


@pytest.mark.asyncio
async def test_lookup_single_found(catalog):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/oclc/00000001.json").mock(
            return_value=httpx.Response(200, json=SINGLE_FIXTURE)
        )
        result = await server.lookup_single("oclc", "00000001")

    assert result["found"] is True
    assert result["records"]["000000001"]["titles"] == ["Example Title"]
    assert result["items"][0]["htid"] == "test.00000001"


@pytest.mark.asyncio
async def test_lookup_single_not_found(catalog):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/oclc/00000000.json").mock(return_value=httpx.Response(404))
        result = await server.lookup_single("oclc", "00000000")

    assert result == {"found": False, "records": {}, "items": []}


@pytest.mark.asyncio
async def test_lookup_single_invalid_field_returns_error(catalog):
    result = await server.lookup_single("badfield", "123")

    assert "Unknown field" in result["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response, message",
    [
        (httpx.Response(400, json={"message": "bad"}), "Bad request"),
        (httpx.Response(500), "HTTP 500"),
    ],
)
async def test_lookup_single_catalog_http_error_returns_error(catalog, response, message):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/oclc/00000001.json").mock(return_value=response)
        result = await server.lookup_single("oclc", "00000001")

    assert message in result["error"]


@pytest.mark.asyncio
async def test_lookup_single_network_error_returns_error(catalog):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/oclc/00000001.json").mock(
            side_effect=httpx.ConnectTimeout("slow")
        )
        result = await server.lookup_single("oclc", "00000001")

    assert "timed out" in result["error"]


# --- lookup_volumes ---


@pytest.mark.asyncio
async def test_lookup_volumes_marks_found_and_missing(catalog):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/json/oclc:00000001|oclc:00000002").mock(
            return_value=httpx.Response(200, json=BATCH_FIXTURE)
        )
        result = await server.lookup_volumes(["oclc:00000001", "oclc:00000002"])

    assert result["oclc:00000001"]["found"] is True
    assert result["oclc:00000001"]["items"][0]["htid"] == "test.00000001"
    assert result["oclc:00000002"] == {"found": False, "records": {}, "items": []}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "identifiers, message",
    [
        (["badfield:123"], "Unknown field"),
        (["no-colon-here"], "field:value"),
    ],
)
async def test_lookup_volumes_invalid_identifier_returns_error(catalog, identifiers, message):
    result = await server.lookup_volumes(identifiers)

    assert message in result["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response, message",
    [
        (httpx.Response(400, json={"message": "bad"}), "Bad request"),
        (httpx.Response(500), "HTTP 500"),
    ],
)
async def test_lookup_volumes_catalog_http_error_returns_error(catalog, response, message):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/json/oclc:00000001").mock(return_value=response)
        result = await server.lookup_volumes(["oclc:00000001"])

    assert message in result["error"]


@pytest.mark.asyncio
async def test_lookup_volumes_network_error_returns_error(catalog):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/json/oclc:00000001").mock(
            side_effect=httpx.ConnectError("refused")
        )
        result = await server.lookup_volumes(["oclc:00000001"])

    assert "unreachable" in result["error"]
