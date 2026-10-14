# ruff: noqa: N815  (field names mirror the Catalog API's camelCase JSON keys)
from pydantic import BaseModel


class CatalogRecord(BaseModel):
    recordURL: str
    titles: list[str] = []
    isbns: list[str] = []
    issns: list[str] = []
    oclcs: list[str] = []
    lccns: list[str] = []
    publishDates: list[str] = []


class CatalogItem(BaseModel):
    htid: str
    itemURL: str
    rightsCode: str
    usRightsString: str
    orig: str
    fromRecord: str
    enumcron: str | bool = False
    lastUpdate: str = ""


class VolumeResult(BaseModel):
    records: dict[str, CatalogRecord]
    items: list[CatalogItem]


# Batch response: keyed by the original "field:value" identifier string
BatchVolumeResult = dict[str, VolumeResult]
