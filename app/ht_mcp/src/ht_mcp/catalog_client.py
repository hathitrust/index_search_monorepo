from collections.abc import Callable
from typing import Any

import httpx
from ht_utils.ht_logger import get_ht_logger

from ht_mcp.config import settings
from ht_mcp.models import BatchVolumeResult, VolumeResult

logger = get_ht_logger(__name__, settings.log_level)

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

    async def _get(self, url: str) -> httpx.Response:
        """GET url, turning timeouts and connection failures into CatalogError."""
        logger.debug("GET %s%s", self.base_url, url)
        try:
            return await self._client.get(url)
        except httpx.TimeoutException as e:
            logger.error("Catalog request timed out: %s%s", self.base_url, url)
            raise CatalogError(f"Catalog request timed out: {e!r}") from e
        except httpx.ConnectError as e:
            logger.error("Catalog unreachable: %s (%r)", self.base_url, e)
            raise CatalogError(f"Catalog unreachable: {e!r}") from e

    @staticmethod
    def _raise_for_error_status(response: httpx.Response) -> None:
        """Turn any remaining HTTP error (e.g. 403, 429) into CatalogError."""
        if response.is_error:
            logger.error("Catalog returned HTTP %s for %s", response.status_code, response.url)
            raise CatalogError(f"Catalog request failed (HTTP {response.status_code})")

    @staticmethod
    def _parse[T](response: httpx.Response, parse: Callable[[Any], T]) -> T:
        """Parse the JSON body, turning unreadable or unexpected replies into CatalogError.

        JSONDecodeError and pydantic's ValidationError are ValueErrors, which the server
        reports as rejected input, so they must not escape as-is.
        """
        try:
            return parse(response.json())
        except (ValueError, AttributeError) as e:
            logger.error("Catalog returned an unreadable response for %s: %r", response.url, e)
            raise CatalogError("Catalog returned an invalid response") from e

    async def lookup_single(self, field: str, value: str) -> VolumeResult:
        if field not in VALID_FIELDS:
            raise ValueError(f"Unknown field '{field}'. Valid fields: {sorted(VALID_FIELDS)}")

        url = f"/api/volumes/brief/{field}/{value}.json"
        response = await self._get(url)

        if response.status_code == 400:
            logger.warning("Catalog rejected %s:%s (HTTP 400)", field, value)
            raise CatalogError(f"Bad request for {field}:{value}")
        if response.status_code == 404 or response.status_code == 200 and not response.text.strip():
            return VolumeResult(records={}, items=[])
        if response.status_code >= 500:
            logger.error("Catalog returned HTTP %s for %s:%s", response.status_code, field, value)
            raise CatalogError(f"Catalog unavailable (HTTP {response.status_code})")

        self._raise_for_error_status(response)
        return self._parse(response, VolumeResult.model_validate)

    async def lookup_volumes(self, identifiers: list[str]) -> BatchVolumeResult:
        for ident in identifiers:
            _validate_identifier(ident)

        query = "|".join(identifiers)
        url = f"/api/volumes/brief/json/{query}"
        response = await self._get(url)

        if response.status_code == 400:
            logger.warning("Catalog rejected batch %s (HTTP 400)", identifiers)
            raise CatalogError(f"Bad request for identifiers: {identifiers}")
        if response.status_code >= 500:
            logger.error("Catalog returned HTTP %s for batch %s", response.status_code, identifiers)
            raise CatalogError(f"Catalog unavailable (HTTP {response.status_code})")

        self._raise_for_error_status(response)
        return self._parse(
            response,
            lambda data: {key: VolumeResult.model_validate(val) for key, val in data.items()},
        )

    async def close(self):
        await self._client.aclose()
