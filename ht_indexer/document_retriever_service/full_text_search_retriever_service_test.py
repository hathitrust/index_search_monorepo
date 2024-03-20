class TestFullTextRetrieverService:

    def test_publish_document(self):
        # TODO Use the json file to index the document without the need to connect to the Catalog
        pass

    """
    def test_create_directory_to_load_xml_fields(self):
        document_local_path = "indexing_data"

        # Create the directory to load the xml files if it does not exit
        try:
            os.makedirs(os.path.join("/tmp", document_local_path))
        except FileExistsError:
            pass
        assert os.path.exists(os.path.join("/tmp", document_local_path)) == True
        # Copy an XML file for testing
        shutil.copy(
            os.path.join(parentdir, "data/document_generator/fullrecord.xml"),
            "/tmp/indexing_data",
        )

        assert os.path.exists("/tmp/indexing_data/fullrecord.xml") == True
    """
