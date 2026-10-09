from mcp.server.fastmcp import FastMCP

from ht_mcp.catalog_client import CatalogClient, CatalogError
from ht_mcp.config import settings

mcp = FastMCP("HathiTrust Catalog", host=settings.mcp_host, port=settings.mcp_port)
catalog = CatalogClient()

# Source: https://www.hathitrust.org/the-collection/preservation/rights-database/
# and babel/mdp-lib/RightsGlobals.pm
RIGHTS_ATTRIBUTES = {
    "pd": "public domain",
    "ic": "in-copyright",
    "op": "out-of-print (implies in-copyright)",
    "orph": "copyright-orphaned (implies in-copyright)",
    "und": "undetermined copyright status",
    "umall": "available to UM affiliates and walk-in patrons (all campuses)",
    "ic-world": "in-copyright and permitted as world viewable by the copyright holder",
    "nobody": "available to nobody; blocked for all users",
    "pdus": "public domain only when viewed in the US",
    "cc-by-3.0": "Creative Commons Attribution license, 3.0 Unported",
    "cc-by-nd-3.0": "Creative Commons Attribution-NoDerivatives license, 3.0 Unported",
    "cc-by-nc-nd-3.0": "Creative Commons Attribution-NonCommercial-NoDerivatives license, 3.0 Unported",
    "cc-by-nc-3.0": "Creative Commons Attribution-NonCommercial license, 3.0 Unported",
    "cc-by-nc-sa-3.0": "Creative Commons Attribution-NonCommercial-ShareAlike license, 3.0 Unported",
    "cc-by-sa-3.0": "Creative Commons Attribution-ShareAlike license, 3.0 Unported",
    "orphcand": "orphan candidate - in 90-day holding period (implies in-copyright)",
    "cc-zero": "Creative Commons Zero license (implies pd)",
    "und-world": "undetermined copyright status and permitted as world viewable by the depositor",
    "icus": "in copyright in the US",
    "cc-by-4.0": "Creative Commons Attribution 4.0 International license",
    "cc-by-nd-4.0": "Creative Commons Attribution-NoDerivatives 4.0 International license",
    "cc-by-nc-nd-4.0": "Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International license",
    "cc-by-nc-4.0": "Creative Commons Attribution-NonCommercial 4.0 International license",
    "cc-by-nc-sa-4.0": "Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International license",
    "cc-by-sa-4.0": "Creative Commons Attribution-ShareAlike 4.0 International license",
    "pd-pvt": "public domain but access limited due to privacy concerns",
    "supp": "suppressed from view",
}


@mcp.tool()
def ping() -> dict:
    """Check that the MCP server is running."""
    return {"status": "ok"}


@mcp.tool()
async def health() -> dict:
    """Check connectivity to the HathiTrust catalog backend.

    Returns status 'ok' if the catalog is reachable, 'degraded' if not.
    Call this when you want to confirm the catalog is available before making lookups.
    """
    try:
        await catalog.lookup_single("htid", "probe")
        return {"status": "ok", "catalog": "reachable"}
    except CatalogError as e:
        return {"status": "degraded", "catalog": str(e)}
    except Exception as e:
        return {"status": "degraded", "catalog": f"unexpected error: {e}"}


@mcp.tool()
def describe_catalog() -> dict:
    """Describe the HathiTrust catalog: supported identifier fields, rights attribute
    codes, and URL patterns. Call this before using other tools if you are unsure what
    identifiers or rights codes mean.
    """
    return {
        "description": (
            "HathiTrust Digital Library catalog. Provides metadata and access "
            "information for digitized books and serials held by HathiTrust member libraries."
        ),
        "supported_identifier_fields": sorted(["htid", "oclc", "isbn", "lccn", "issn", "recordid"]),
        "rights_attributes": RIGHTS_ATTRIBUTES,
        "access_note": (
            "Item responses include 'rightsCode' (the attribute name above) and "
            "'usRightsString' ('Full view' or 'Limited (search-only)') which reflects "
            "access for an ordinary user. Some codes grant broader access to specific "
            "user types (e.g. SSD users, library IP addresses) depending on institutional "
            "holdings — that logic is handled by the HathiTrust page-turner, not this server."
        ),
        "item_url_pattern": "https://babel.hathitrust.org/cgi/pt?id={htid}",
        "record_url_pattern": "https://catalog.hathitrust.org/Record/{recordid}",
    }


@mcp.tool()
async def lookup_single(field: str, value: str) -> dict:
    """Look up a single HathiTrust catalog record by one identifier.

    Args:
        field: Identifier type — one of: htid, oclc, isbn, lccn, issn, recordid
        value: The identifier value, e.g. "9780316769174"

    Returns catalog record metadata and associated digitized items.
    """
    try:
        result = await catalog.lookup_single(field, value)
    except ValueError as e:
        return {"error": str(e)}
    except CatalogError as e:
        return {"error": str(e)}

    if not result.records and not result.items:
        return {"found": False, "records": {}, "items": []}

    return {
        "found": True,
        "records": {k: v.model_dump() for k, v in result.records.items()},
        "items": [item.model_dump() for item in result.items],
    }


@mcp.tool()
async def lookup_volumes(identifiers: list[str]) -> dict:
    """Look up multiple HathiTrust catalog records in a single call.

    Args:
        identifiers: List of 'field:value' strings, e.g. ["oclc:470409", "isbn:9780316769174"].
                     Supported fields: htid, oclc, isbn, lccn, issn, recordid.

    Returns results keyed by each input identifier.
    """
    try:
        batch = await catalog.lookup_volumes(identifiers)
    except ValueError as e:
        return {"error": str(e)}
    except CatalogError as e:
        return {"error": str(e)}

    return {
        key: {
            "found": bool(result.records or result.items),
            "records": {k: v.model_dump() for k, v in result.records.items()},
            "items": [item.model_dump() for item in result.items],
        }
        for key, result in batch.items()
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
