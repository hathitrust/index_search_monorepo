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
