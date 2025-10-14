from document_retriever_service.retriever_services_utils import RetrieverServicesUtils


class TestRetrieverServicesUtils:

    def test_create_catalog_object_by_item_id(self, get_catalog_record_metadata,
                                              get_record_data):
        """Test if the method returns only the metadata of the input item"""
        results = []
        # Create the list
        list_documents = ["mdp.39015078560292"]
        results = RetrieverServicesUtils.create_catalog_object_by_item_id(list_documents, get_record_data,
                                                                get_catalog_record_metadata)

        assert len(results) == 1
        assert results[0].ht_id == "mdp.39015078560292"
        assert results[0].metadata.get("vol_id") == "mdp.39015078560292"

    def test_extract_hathitrust_ids(self):
        docs = [
            {"ht_id": 101, "record_id": "A"},
            {"ht_id": 202, "record_id": "B"},
            {"ht_id": 303, "record_id": "C"},
        ]
        result = RetrieverServicesUtils.extract_hathitrust_ids(docs)
        assert result == [101, 202, 303]
        # Empty list
        assert RetrieverServicesUtils.extract_hathitrust_ids([]) == []

    def test_extract_catalog_record_id(self):
        docs = [
            {"ht_id": 101, "record_id": "A"},
            {"ht_id": 202, "record_id": "B"},
            {"ht_id": 303, "record_id": "C"},
        ]
        result = RetrieverServicesUtils.extract_catalog_record_id(docs)
        assert  result == ["A", "B", "C"]

        # Empty list
        assert RetrieverServicesUtils.extract_catalog_record_id([]) == []
