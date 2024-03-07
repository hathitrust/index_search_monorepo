import inspect
import json
import os

import pytest

from catalog_metadata.catalog_metadata import CatalogItemMetadata, CatalogRecordMetadata

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))


@pytest.fixture()
def get_record_data():
    with open(os.path.join(current, "data/catalog.json"), "r", ) as file:
        data = json.load(file)

    return data


@pytest.fixture()
def get_catalog_record_metadata(get_record_data):
    return CatalogRecordMetadata(get_record_data)


@pytest.fixture()
def get_item_metadata(get_record_data: dict, get_catalog_record_metadata: CatalogRecordMetadata):
    return CatalogItemMetadata(get_record_data, "mdp.39015078560292", get_catalog_record_metadata)


class TestCatalogMetadata:

    def test_catalog_record_metadata_class(self, get_catalog_record_metadata):

        assert 'ht_id' not in get_catalog_record_metadata.metadata.keys()
        assert 'htsource' in get_catalog_record_metadata.metadata.keys()
        assert 'vol_id' not in get_catalog_record_metadata.metadata.keys()

    def test_catalog_item_metadata_class(self, get_item_metadata):

        assert get_item_metadata.ht_id == "mdp.39015078560292"
        assert "mdp.39015078560292" == get_item_metadata.metadata.get('vol_id')
        assert "title" in get_item_metadata.metadata.keys()

    def test_get_item_htsource(self):
        htsource = CatalogItemMetadata.get_item_htsource(
            "mdp.39015061418433",  # it is in solr core 7
            ["University of Michigan", "Indiana University"],
            ["mdp.39015061418433", "inu.30000108625017"],
        )
        assert htsource == "University of Michigan"

        htsource = CatalogItemMetadata.get_item_htsource(
            "inu.30000108625017",  # it is in solr core 7
            ["University of Michigan", "Indiana University"],
            ["mdp.39015061418433", "inu.30000108625017"],
        )
        assert htsource == "Indiana University"

    def test_get_item_htsource_sharinghtsource(self):
        htsource = CatalogItemMetadata.get_item_htsource(
            "inu.30000108625017",  # it is in solr core 7
            ["University of Michigan"],
            ["mdp.39015061418433", "inu.30000108625017"],
        )
        assert htsource == "University of Michigan"

    def test_get_volume_enumcron_empty(self):
        """
        Some documents do not have the field volume_enumcrom, that is because it is an empty string in the second position.
        See here https://github.com/hathitrust/hathitrust_catalog_indexer/blob/main/indexers/common_ht.rb#L50 how this
        field is generated.
        :return:
        """
        volume_enumcrom = ""
        ht_id_display = [
            "mdp.39015078560292|20220910||1860|1860-1869|||RÄ\x81binsan KrÅ«so kÄ\x81 itihÄ\x81sa. "
            "The adventures of Robinson Crusoe, translated [into Hindi] by BadrÄ« LÄ\x81la, from a Bengali version ..."
        ]
        assert volume_enumcrom == ht_id_display[0].split("|")[2]

    def test_missed_enumPublishDate(self, get_item_metadata):
        ht_json = ('[{"htid":"nyp.33433069877805","newly_open":null,'
                   '"ingest":"20220501","rights":["pdus",null],"heldby":["nypl"],"collection_code":"nyp",'
                   '"enumcron":"v. 1","dig_source":"google"}]')

        doc_json = []
        for record in json.loads(ht_json):
            if (
                    _v := record.get("enum_pubdate") and "nyp.33433069877805" == record.get("htid")
            ):
                doc_json.append(record)

        if len(doc_json) > 0:
            entry = get_item_metadata.get_data_ht_json_obj(doc_json[0])

            assert "enumPublishDate" not in entry.keys()

    def test_extract_enumPublishDate(self, get_item_metadata):
        ht_json = ('[{"htid":"mdp.39015082023097","newly_open":null,"ingest":"20230114",'
                   '"rights":["pdus",null],"heldby":["cornell","emory","harvard","stanford","uiowa","umich","umn"],'
                   '"collection_code":"miu","enumcron":"1958","enum_pubdate":"1958","enum_pubdate_range":"1950-1959",'
                   '"dig_source":"google"},{"htid":"mdp.39015082023246","newly_open":null,"ingest":"20230114",'
                   '"rights":["pdus",null],"heldby":["cornell","emory","harvard","stanford","uiowa","umich","umn"],'
                   '"collection_code":"miu","enumcron":"1959","enum_pubdate":"1959","enum_pubdate_range":"1950-1959",'
                   '"dig_source":"google"}]')

        doc_json = []
        for record in json.loads(ht_json):
            if (
                    _v := record.get("enum_pubdate")
                          and "mdp.39015082023097" == record.get("htid")
            ):
                doc_json.append(record)

        if len(doc_json) > 0:
            entry = get_item_metadata.get_data_ht_json_obj(doc_json[0])
            assert "enumPublishDate" in entry.keys()
