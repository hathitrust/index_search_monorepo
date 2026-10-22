import zipfile
from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import quoteattr

import pytest
from document_generator.full_text_document_generator import FullTextDocumentGenerator
from document_generator.mysql_data_extractor import extract_namespace_and_id
from ht_utils.text_processor import string_preparation


@pytest.fixture
def make_ocr_zip(tmp_path: Path) -> Callable[[dict[str, bytes]], str]:
    def _make(pages: dict[str, bytes]) -> str:
        path = tmp_path / "item.zip"
        with zipfile.ZipFile(path, "w") as zip_doc:
            for name, data in pages.items():
                zip_doc.writestr(name, data)
        return str(path)

    return _make


@pytest.fixture()
def get_fullrecord_xml() -> str:
    with open(f"{Path(__file__).parents[1]}/document_generator_tests/data/fullrecord.xml") as f:
        full_record_data = f.read()
    return full_record_data


@pytest.fixture()
def get_allfield_string() -> str:
    return quoteattr(
        "Defoe, Daniel, 1661?-1731. Rābinsan Krūso kā itihāsa. The adventures of Robinson "
        "Crusoe, translated [into Hindi] by Badrī Lāla, from a Bengali version ... Benares, "
        "1860 455 p. incl. front., illus. plates. 20 cm. Title from Catalogue of Hindi "
        "books in the British museum. Badarīnātha, pandit, tr. Robinson Crusoe. "
        "UTL 9662 SPEC HUB PR 3403 .H5 39015078560292"
    )


class TestDocumentGenerator:
    def test_not_exist_zip_file_full_text_field(self) -> None:
        """Test the function when the zip file does not exist"""
        with pytest.raises(FileNotFoundError):
            FullTextDocumentGenerator.get_full_text_field("../catalog_metadata_tests/data/test.zip")

    def test_full_text_field_well_generated(self) -> None:
        """
        Test the function when the zip file exists, the zip file can contain a __MACOSX directory inside, but
        the function will ignore this directory and the full text is well generated
        """

        zip_doc_path = (
            f"{Path(__file__).parents[1]}/document_generator_tests/data/mb.39015078560292_test.zip"
        )

        zip_doc = zipfile.ZipFile(zip_doc_path, mode="r")
        full_test = FullTextDocumentGenerator.txt_files_2_full_text(zip_doc)
        assert len(full_test) > 0

    def test_string_preparation_raise_unicodedecodeerror_macosx_directory(self) -> None:
        """
        A UnicodeDecodeError is find when the zip file contains pesky __MACOSX directory inside,
        so the function should raise an exception if __MACOSX directory is not ignored
        string_preparation function should raise an exception when the received file is from the __MACOSX directory
        This use case forces the UnicodeDecodeError exception processing files inside __MACOSX folder.
        """

        zip_doc_path = (
            f"{Path(__file__).parents[1]}/document_generator_tests/data/mb.39015078560292_test.zip"
        )

        zip_doc = zipfile.ZipFile(zip_doc_path, mode="r")
        with pytest.raises(UnicodeDecodeError):
            full_text = FullTextDocumentGenerator.txt_files_2_full_text(zip_doc)

            for i_file in zip_doc.namelist():
                if i_file.startswith("__MACOSX/"):
                    if zip_doc.getinfo(i_file).filename.endswith(".txt"):
                        doc_str = string_preparation(zip_doc.read(i_file))
                        full_text = full_text + " " + doc_str

    def test_create_allfields_field(
        self, get_fullrecord_xml: str, get_allfield_string: str
    ) -> None:
        all_field = FullTextDocumentGenerator.get_all_fields_field(get_fullrecord_xml)

        assert len(all_field.strip()) == len(get_allfield_string.strip())
        assert all_field.strip() == get_allfield_string.strip()

    def test_extract_namespace_and_id(self) -> None:
        """
        Extracts the namespace and the id from a given document id string.
        The namespace is defined as the characters before the first period.
        The id is the remainder of the string after the first period.

        :param document_id: The document id string to extract from.
        :return: A tuple containing the namespace and the id.
        """

        document_id = "uc2.ark:/13960/t4mk66f1d"
        namespace, ht_id = extract_namespace_and_id(document_id)
        assert namespace == "uc2"
        assert ht_id == "ark:/13960/t4mk66f1d"

        document_id = "miun.afs8435.0001.001"
        namespace, ht_id = extract_namespace_and_id(document_id)
        assert namespace == "miun"
        assert ht_id == "afs8435.0001.001"

        document_id = "uiug.30112056400960"
        namespace, ht_id = extract_namespace_and_id(document_id)
        assert namespace == "uiug"
        assert ht_id == "30112056400960"

    @pytest.mark.parametrize(
        ("pages", "expected"),
        [
            pytest.param(
                {
                    "00000001.txt": b"hello",
                    "00000002.txt": b"  \n ",
                    "00000003.txt": b"world",
                },
                '"hello" __EMPTYOCR__ "world"',
                id="blank-page-replaced",
            ),
            pytest.param(
                {"00000001.txt": b"", "00000002.txt": b"\r\n"},
                "__EMPTYOCR__ __EMPTYOCR__",
                id="all-pages-empty",
            ),
            pytest.param({"item.xml": b"<x/>"}, "__EMPTYOCR__", id="no-txt-pages"),
            pytest.param(
                {"00000001.txt": b"a", "00000002.txt": b"b"},
                '"a" "b"',
                id="text-pages-unchanged",
            ),
        ],
    )
    def test_get_full_text_field_returns_expected_ocr(
        self,
        make_ocr_zip: Callable[[dict[str, bytes]], str],
        pages: dict[str, bytes],
        expected: str,
    ) -> None:
        """
        Test that get_full_text_field returns the expected OCR text.
        """
        assert FullTextDocumentGenerator.get_full_text_field(make_ocr_zip(pages)) == expected
