import pytest
import os
import inspect
import sys

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)


class TestFullTextRetrieverService:
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
