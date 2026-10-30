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
        """GET url, turning timeouts and other transport failures into CatalogError.

        The messages are deliberately generic: the details (host, exception text) go to
        the log, not to the MCP client.
        """
        logger.debug("GET %s%s", self.base_url, url)
        try:
            return await self._client.get(url)
        except httpx.TimeoutException as e:
            logger.exception("Catalog request timed out: %s%s", self.base_url, url)
            raise CatalogError("Catalog request timed out") from e
        except httpx.ConnectError as e:
            logger.exception("Catalog unreachable: %s", self.base_url)
            raise CatalogError("Catalog unreachable") from e
        except httpx.TransportError as e:
            # Anything else at the transport level, e.g. a connection dropped mid-response.
            logger.exception("Catalog connection failed: %s%s", self.base_url, url)
            raise CatalogError("Catalog connection failed") from e

    @staticmethod
    def _raise_for_error_status(response: httpx.Response, subject: str) -> None:
        """Turn any HTTP error status (400, 403, 429, 5xx, ...) into CatalogError.

        `subject` names what was looked up, for the log only.
        """
        if response.status_code == 400:
            logger.warning("Catalog rejected %s (HTTP 400)", subject)
            raise CatalogError("Bad request to catalog (HTTP 400)")
        if response.is_error:
            logger.error("Catalog returned HTTP %s for %s", response.status_code, subject)
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
            logger.exception("Catalog returned an unreadable response for %s", response.url)
            raise CatalogError("Catalog returned an invalid response") from e

    async def lookup_single(self, field: str, value: str) -> VolumeResult:
        if field not in VALID_FIELDS:
            raise ValueError(f"Unknown field '{field}'. Valid fields: {sorted(VALID_FIELDS)}")

        url = f"/api/volumes/brief/{field}/{value}.json"
        response = await self._get(url)

        if response.status_code == 404 or response.status_code == 200 and not response.text.strip():
            return VolumeResult(records={}, items=[])

        self._raise_for_error_status(response, f"{field}:{value}")
        return self._parse(response, VolumeResult.model_validate)

    async def lookup_volumes(self, identifiers: list[str]) -> BatchVolumeResult:
        for ident in identifiers:
            _validate_identifier(ident)

        query = "|".join(identifiers)
        url = f"/api/volumes/brief/json/{query}"
        response = await self._get(url)

        self._raise_for_error_status(response, f"batch {identifiers}")
        return self._parse(
            response,
            lambda data: {key: VolumeResult.model_validate(val) for key, val in data.items()},
        )

    async def close(self):
        await self._client.aclose()
