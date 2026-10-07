import json
from pathlib import Path

import pytest
import respx
from ht_mcp.catalog_client import CatalogClient, CatalogError
from httpx import Response

SINGLE_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "volumes_brief_single.json").read_text()
)
BATCH_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "volumes_brief_batch.json").read_text()
)
BASE_URL = "http://catalog-test"


@pytest.fixture
def client():
    return CatalogClient(base_url=BASE_URL)


# --- lookup_single ---


@pytest.mark.asyncio
async def test_lookup_single_happy_path(client):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/oclc/00000001.json").mock(
            return_value=Response(200, json=SINGLE_FIXTURE)
        )
        result = await client.lookup_single("oclc", "00000001")

    assert "000000001" in result.records
    assert result.records["000000001"].titles == ["Example Title"]
    assert result.items[0].htid == "test.00000001"
    assert result.items[0].rightsCode == "ic"


@pytest.mark.asyncio
async def test_lookup_single_empty_result(client):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/oclc/00000000.json").mock(
            return_value=Response(200, json={"records": {}, "items": []})
        )
        result = await client.lookup_single("oclc", "00000000")

    assert result.records == {}
    assert result.items == []


@pytest.mark.asyncio
async def test_lookup_single_http_400(client):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/oclc/bad.json").mock(
            return_value=Response(400, json={"message": "missing or empty query"})
        )
        with pytest.raises(CatalogError):
            await client.lookup_single("oclc", "bad")


@pytest.mark.asyncio
async def test_lookup_single_http_500(client):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/oclc/00000001.json").mock(return_value=Response(500))
        with pytest.raises(CatalogError):
            await client.lookup_single("oclc", "00000001")


@pytest.mark.asyncio
async def test_lookup_single_invalid_field(client):
    with pytest.raises(ValueError, match="Unknown field"):
        await client.lookup_single("badfield", "123")


# --- lookup_volumes ---


@pytest.mark.asyncio
async def test_lookup_volumes_joins_identifiers(client):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/api/volumes/brief/json/oclc:00000001|oclc:00000002").mock(
            return_value=Response(200, json=BATCH_FIXTURE)
        )
        result = await client.lookup_volumes(["oclc:00000001", "oclc:00000002"])

    assert route.called
    assert "oclc:00000001" in result
    assert "oclc:00000002" in result


@pytest.mark.asyncio
async def test_lookup_volumes_empty_entry(client):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/volumes/brief/json/oclc:00000001|oclc:00000002").mock(
            return_value=Response(200, json=BATCH_FIXTURE)
        )
        result = await client.lookup_volumes(["oclc:00000001", "oclc:00000002"])

    assert result["oclc:00000002"].records == {}
    assert result["oclc:00000002"].items == []


@pytest.mark.asyncio
async def test_lookup_volumes_invalid_field_raises_before_http(client):
    with respx.mock(base_url=BASE_URL):
        with pytest.raises(ValueError, match="Unknown field"):
            await client.lookup_volumes(["badfield:123"])


@pytest.mark.asyncio
async def test_lookup_volumes_malformed_identifier_raises(client):
    with pytest.raises(ValueError, match="field:value"):
        await client.lookup_volumes(["no-colon-here"])
