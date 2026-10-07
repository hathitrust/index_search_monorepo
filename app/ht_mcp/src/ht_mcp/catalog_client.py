import httpx

from ht_mcp.config import settings
from ht_mcp.models import BatchVolumeResult, VolumeResult

VALID_FIELDS = {"htid", "oclc", "isbn", "lccn", "issn", "recordid"}


def _validate_identifier(identifier: str) -> None:
    """Raise ValueError if identifier is not in 'field:value' form with a known field."""
    parts = identifier.split(":", 1)
    if len(parts) != 2 or not parts[1].strip():
        raise ValueError(f"Identifier '{identifier}' must be in 'field:value' form")
    field = parts[0].strip()
    if field not in VALID_FIELDS:
        raise ValueError(f"Unknown field '{field}'. Valid fields: {sorted(VALID_FIELDS)}")


class CatalogError(Exception):
    pass


class CatalogClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.catalog_url
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=settings.http_timeout_seconds,
        )

    async def lookup_single(self, field: str, value: str) -> VolumeResult:
        if field not in VALID_FIELDS:
            raise ValueError(f"Unknown field '{field}'. Valid fields: {sorted(VALID_FIELDS)}")

        url = f"/api/volumes/brief/{field}/{value}.json"
        response = await self._client.get(url)

        if response.status_code == 400:
            raise CatalogError(f"Bad request for {field}:{value}")
        if response.status_code == 404 or response.status_code == 200 and not response.text.strip():
            return VolumeResult(records={}, items=[])
        if response.status_code >= 500:
            raise CatalogError(f"Catalog unavailable (HTTP {response.status_code})")

        response.raise_for_status()
        return VolumeResult.model_validate(response.json())

    async def lookup_volumes(self, identifiers: list[str]) -> BatchVolumeResult:
        for ident in identifiers:
            _validate_identifier(ident)

        query = "|".join(identifiers)
        url = f"/api/volumes/brief/json/{query}"
        response = await self._client.get(url)

        if response.status_code == 400:
            raise CatalogError(f"Bad request for identifiers: {identifiers}")
        if response.status_code >= 500:
            raise CatalogError(f"Catalog unavailable (HTTP {response.status_code})")

        response.raise_for_status()
        return {key: VolumeResult.model_validate(val) for key, val in response.json().items()}

    async def close(self):
        await self._client.aclose()
