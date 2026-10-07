"""
Integration tests against a running catalog (CATALOG_URL).
Run with: uv run --package ht-mcp pytest app/ht_mcp/tests -m integration
These are skipped in the unit test suite (marked "not integration").
"""

import pytest
from ht_mcp.catalog_client import CatalogClient

HTID_1 = "mdp.35112103801421"
HTID_2 = "umn.31951002065930r"


@pytest.fixture
async def client():
    c = CatalogClient()
    yield c
    await c.close()


@pytest.mark.integration
async def test_lookup_single_returns_record(client):
    result = await client.lookup_single("htid", HTID_1)
    assert result.records, "expected at least one record"
    assert result.items, "expected at least one item"


@pytest.mark.integration
async def test_lookup_single_htid_present_in_items(client):
    result = await client.lookup_single("htid", HTID_1)
    htids = [item.htid for item in result.items]
    assert HTID_1 in htids


@pytest.mark.integration
async def test_lookup_single_rights_fields_populated(client):
    result = await client.lookup_single("htid", HTID_1)
    for item in result.items:
        assert item.rightsCode, f"empty rightsCode on {item.htid}"
        assert item.usRightsString in ("Full view", "Limited (search-only)"), (
            f"unexpected usRightsString: {item.usRightsString!r}"
        )


@pytest.mark.integration
async def test_lookup_single_nonexistent_returns_empty(client):
    result = await client.lookup_single("htid", "xxx.nonexistent00000000")
    assert result.records == {}
    assert result.items == []


@pytest.mark.integration
async def test_lookup_volumes_batch(client):
    result = await client.lookup_volumes([f"htid:{HTID_1}", f"htid:{HTID_2}"])
    assert f"htid:{HTID_1}" in result
    assert f"htid:{HTID_2}" in result


@pytest.mark.integration
async def test_lookup_volumes_first_item_has_data(client):
    result = await client.lookup_volumes([f"htid:{HTID_1}"])
    entry = result[f"htid:{HTID_1}"]
    assert entry.records
    assert entry.items


@pytest.mark.integration
async def test_lookup_volumes_second_record_independent(client):
    result = await client.lookup_volumes([f"htid:{HTID_1}", f"htid:{HTID_2}"])
    entry2 = result[f"htid:{HTID_2}"]
    assert entry2.records, "second record should have its own metadata"
    htids_2 = [item.htid for item in entry2.items]
    assert HTID_2 in htids_2
