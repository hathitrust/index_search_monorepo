import os
from copy import deepcopy

import pytest

from catalog_metadata.catalog_metadata import CatalogItemMetadata, CatalogRecordMetadata

current = os.path.dirname(__file__)


# Update some fields of the catalog record to test some functions that retrieve specific fields
@pytest.fixture()
def update_catalog_record_metadata(get_record_data):
    new_record_data = deepcopy(get_record_data)
    new_record_data["htsource"] = ["University of Michigan", "Indiana University"]
    new_record_data["ht_id"].append("inu.30000108625017")
    return new_record_data


# Create a CatalogRecordMetadata object with the updated catalog record
@pytest.fixture()
def get_update_catalog_record_metadata(update_catalog_record_metadata):
    return CatalogRecordMetadata(update_catalog_record_metadata)


# Create a CatalogItemMetadata object with the updated catalog record and the ht_id of the item
@pytest.fixture()
def get_item_metadata_second_position(update_catalog_record_metadata: dict,
                                      get_update_catalog_record_metadata: CatalogRecordMetadata):
    """Fake data updating the input document to test the second position of the htsource field"""

    return CatalogItemMetadata("inu.30000108625017",
                               get_update_catalog_record_metadata)


@pytest.fixture()
def get_catalog_record_without_enum_pubdate(get_record_data):
    updating_record = deepcopy(get_record_data)
    updating_record[
        "ht_json"] = '[{"htid":"nyp.33433069877805","newly_open":null,"ingest":"20220501","rights":["pdus",null],"heldby":["nypl"],"collection_code":"nyp","enumcron":"v. 1","dig_source":"google"}]'
    updating_record["ht_id"] = ["nyp.33433069877805"]
    return updating_record


@pytest.fixture()
def get_catalog_record_metadata_without_enum_pubdate(get_catalog_record_without_enum_pubdate):
    return CatalogRecordMetadata(get_catalog_record_without_enum_pubdate)


@pytest.fixture()
def get_item_metadata_without_enum_pubdate(get_catalog_record_without_enum_pubdate: dict,
                                           get_catalog_record_metadata_without_enum_pubdate: CatalogRecordMetadata):
    """Fake data updating the input document to test the second position of the htsource field"""

    return CatalogItemMetadata("nyp.33433069877805",
                               get_catalog_record_metadata_without_enum_pubdate)


class TestCatalogMetadata:

    def test_catalog_record_metadata_class(self, get_catalog_record_metadata):
        assert 'ht_id' not in get_catalog_record_metadata.metadata.keys()
        assert 'htsource' in get_catalog_record_metadata.metadata.keys()
        assert 'vol_id' not in get_catalog_record_metadata.metadata.keys()

    def test_catalog_item_metadata_class(self, get_item_metadata):
        assert get_item_metadata.ht_id == "mdp.39015078560292"
        assert "mdp.39015078560292" == get_item_metadata.metadata.get('vol_id')
        assert "title" in get_item_metadata.metadata.keys()

    def test_get_item_htsource(self, get_item_metadata):
        htsource = get_item_metadata.get_item_htsource()
        assert htsource == "University of Michigan"

    def test_get_item_htsource_second_position(self, get_item_metadata_second_position):
        htsource = get_item_metadata_second_position.get_item_htsource()
        assert htsource == "Indiana University"

    def test_get_item_htsource_sharinghtsource(self, get_item_metadata):
        htsource = get_item_metadata.get_item_htsource()
        assert htsource == "University of Michigan"

    def test_get_volume_enumcron_empty(self):
        """
        Some documents do not have the field volume_enumcrom, that is because it is an empty string in the second
        position.
        See here https://github.com/hathitrust/hathitrust_catalog_indexer/blob/main/indexers/common_ht.rb#L50 how this
        field is generated.
        :return:
        """

        volume_enumcrom = ""
        ht_id_display = [
            "mdp.39015078560292|20220910||1860|1860-1869|||Rābinsan Krūso kā itihāsa. The adventures of Robinson "
            "Crusoe, translated [into Hindi] by Badrī Lāla, from a Bengali version ..."]
        assert volume_enumcrom == ht_id_display[0].split("|")[2]

    def test_missed_enum_publish_date(self, get_item_metadata_without_enum_pubdate):
        doc_json = get_item_metadata_without_enum_pubdate.get_data_ht_json_obj()
        assert len(doc_json) == 0

    def test_extract_enum_publish_date(self, get_item_metadata):
        doc_json = get_item_metadata.get_data_ht_json_obj()
        assert len(doc_json) == 1
