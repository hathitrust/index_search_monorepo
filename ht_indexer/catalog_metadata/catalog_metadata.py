import json

from indexer_config import IDENTICAL_CATALOG_METADATA, RENAMED_CATALOG_METADATA


class CatalogRecordMetadata:
    """This class is used to retrieve the metadata of a specific item in the Catalog"""

    def __init__(self, record: dict):
        self.metadata = self.get_metadata(record)

    def get_metadata(self, record: dict) -> dict:

        metadata = {}

        metadata.update(CatalogRecordMetadata.get_catalog_identical_fields(record))
        metadata.update(CatalogRecordMetadata.rename_catalog_fields(record))

        # Create bothPublishDate field
        if record.get("date") and record.get("enumPublishDate"):
            metadata.update({"bothPublishDate": record.get("enumPublishDate")})

        return metadata

    @staticmethod
    def get_catalog_identical_fields(metadata: dict) -> dict:
        entry = {}
        for field in IDENTICAL_CATALOG_METADATA:
            value = metadata.get(field)
            if value:
                entry[field] = value
        return entry

    @staticmethod
    def rename_catalog_fields(metadata: dict) -> dict:
        entry = {}
        for new_field in RENAMED_CATALOG_METADATA.keys():
            catalog_field = RENAMED_CATALOG_METADATA[new_field]
            entry[new_field] = metadata.get(catalog_field)
        return entry


class CatalogItemMetadata:
    """This class is used to retrieve the metadata of a specific item in the Catalog"""

    def __init__(self, record: dict, ht_id: str, record_metadata: CatalogRecordMetadata = None):

        self.ht_id = ht_id
        metadata = self.get_metadata(record)

        # Merge both dictionaries
        self.metadata = {**record_metadata.metadata, **metadata}

    @staticmethod
    def get_volume_enumcron(ht_id_display: str = None):
        # TODO REVIEW THIS METHOD
        enumcron = ht_id_display[0].split("|")[2]
        return enumcron

    def get_metadata(self, record: dict) -> dict:

        metadata = {}
        volume_enumcron = CatalogItemMetadata.get_volume_enumcron(record.get("ht_id_display"))

        metadata.update({"volume_enumcron": volume_enumcron})

        doc_json = [
            item
            for item in json.loads(record.get("ht_json"))
            if (_v := item.get("enum_pubdate") and self.ht_id == item.get("htid"))
        ]

        if len(doc_json) > 0:
            metadata.update(CatalogItemMetadata.get_data_ht_json_obj(doc_json[0]))

        if len(volume_enumcron) > 1:
            metadata["volume_enumcron"] = volume_enumcron
        metadata["htsource"] = CatalogItemMetadata.get_item_htsource(
            self.ht_id, record.get("htsource"), record.get("ht_id")
        )

        metadata["vol_id"] = self.ht_id
        return metadata

    @staticmethod
    def get_data_ht_json_obj(ht_json: dict = None) -> dict:
        catalog_json_data = {"enumPublishDate": ht_json.get("enum_pubdate")}
        return catalog_json_data

    @staticmethod
    def get_item_htsource(
            id: str = None, catalog_htsource: list = None, catalog_htid: list = None
    ) -> str:
        """
        In catalog it could be a list of sources, should obtain the source of an specific item
        :param id: Catalod ht_id field
        :param catalog_htsource: catalog item source
        :param catalog_htid: catalog item ht_id
        :return:
        """
        item_position = catalog_htid.index(id)
        try:
            htsource = catalog_htsource[item_position]
        except IndexError:
            htsource = catalog_htsource[0]
        return htsource
