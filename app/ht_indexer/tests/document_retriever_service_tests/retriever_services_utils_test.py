from document_retriever_service.retriever_services_utils import RetrieverServicesUtils


class TestRetrieverServicesUtils:
    def test_extract_hathitrust_ids(self) -> None:
        docs = [
            {"ht_id": "101", "record_id": "A"},
            {"ht_id": "202", "record_id": "B"},
            {"ht_id": "303", "record_id": "C"},
        ]
        result = RetrieverServicesUtils.extract_hathitrust_ids(docs)
        assert result == ["101", "202", "303"]
        # Empty list
        assert RetrieverServicesUtils.extract_hathitrust_ids([]) == []

    def test_extract_catalog_record_id(self) -> None:
        docs = [
            {"ht_id": "101", "record_id": "A"},
            {"ht_id": "202", "record_id": "B"},
            {"ht_id": "303", "record_id": "C"},
        ]
        result = RetrieverServicesUtils.extract_catalog_record_id(docs)
        assert result == ["A", "B", "C"]

        # Empty list
        assert RetrieverServicesUtils.extract_catalog_record_id([]) == []
