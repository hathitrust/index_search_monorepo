import json

from indexer_config import IDENTICAL_CATALOG_METADATA, RENAMED_CATALOG_METADATA


class CatalogRecordMetadata:
    """This class is used to retrieve the metadata of a specific item in the Catalog"""

    def __init__(self, record: dict):
        self.record = record
        self.metadata = self.get_metadata()

    def get_metadata(self) -> dict:

        """Create a dictionary with the fulltext fields extracted from catalog metadata"""
        metadata = {}

        metadata.update(self.get_catalog_identical_fields())
        metadata.update(self.rename_catalog_fields())

        # Create bothPublishDate field
        if self.record.get("date") and self.record.get("enumPublishDate"):
            metadata.update({"bothPublishDate": self.record.get("enumPublishDate")})

        return metadata

    def get_catalog_identical_fields(self) -> dict:

        """Retrieve the fields that have identical names in the catalog and fulltext documents."""
        entry = {}
        for field in IDENTICAL_CATALOG_METADATA:
            value = self.record.get(field)
            if value:
                entry[field] = value
        return entry

    def rename_catalog_fields(self) -> dict:
        """Rename the fields from the catalog to the ones used in the fulltext documents."""
        entry = {}
        for new_field in RENAMED_CATALOG_METADATA.keys():
            catalog_field = RENAMED_CATALOG_METADATA[new_field]
            entry[new_field] = self.record.get(catalog_field)
        return entry


class CatalogItemMetadata:
    """This class is used to retrieve the metadata of a specific item in the Catalog"""

    def __init__(self, ht_id: str, record_metadata: CatalogRecordMetadata = None):

        self.record_metadata = record_metadata
        self.ht_id = ht_id
        metadata = self.get_metadata()

        # Merge both dictionaries
        self.metadata = {**self.record_metadata.metadata, **metadata}

    def get_volume_enumcron(self) -> list:
        try:
            return self.record_metadata.record.get("ht_id_display")[0].split("|")[2]
        except IndexError:
            return []

    def get_metadata(self) -> dict:

        metadata = {}

        volume_enumcron = self.get_volume_enumcron()

        doc_json = self.get_data_ht_json_obj()

        if len(doc_json) > 0:
            metadata["enumPublishDate"] = doc_json[0].get("ht_json")

        if len(volume_enumcron) > 1:
            metadata["volume_enumcron"] = volume_enumcron
        metadata["htsource"] = self.get_item_htsource()

        metadata["vol_id"] = self.ht_id
        return metadata

    def get_data_ht_json_obj(self) -> list:
        """Obtain the publication data of a specific item in the catalog."""
        doc_json = [
            item
            for item in json.loads(self.record_metadata.record.get("ht_json"))
            if (_v := item.get("enum_pubdate") and self.ht_id == item.get("htid"))
        ]

        return doc_json

    def get_item_htsource(self) -> str:
        """
        In catalog it could be a list of sources, should obtain the source of a specific item
        :param id: Catalod ht_id field
        :param catalog_htsource: catalog item source
        :param catalog_htid: catalog item ht_id
        :return:
        """
        item_position = self.record_metadata.record.get("ht_id").index(self.ht_id)
        try:
            htsource = self.record_metadata.record.get("htsource")[item_position]
        except IndexError:
            htsource = self.record_metadata.record.get("htsource")[0]
        return htsource
