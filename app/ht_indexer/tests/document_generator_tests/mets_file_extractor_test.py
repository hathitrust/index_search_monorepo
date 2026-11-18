from pathlib import Path

import pytest

# relative imports
from document_generator.full_text_document_generator import extract_fields_from_mets_file
from document_generator.mets_file_extractor import MetsAttributeExtractor
from ht_utils.testing import assert_log_entry, capture_logs


class TestMETSFileExtractor:
    @pytest.fixture()
    def mets_attr_extractor_obj(self) -> MetsAttributeExtractor:
        path = f"{Path(__file__).parents[1]}/document_generator_tests/data/mb.39015078560292.mets_test.xml"
        mets_obj = MetsAttributeExtractor(path)
        return mets_obj

    def test_create_mets_map(self, mets_attr_extractor_obj: MetsAttributeExtractor) -> None:
        mets_map = mets_attr_extractor_obj.create_mets_map()
        field_488 = mets_map.get("488") or {}

        assert field_488.get("features") == "CHAPTER_START, IMPLICIT_PAGE_NUMBER"
        assert field_488.get("pgnum") is None
        assert field_488.get("filename") == [
            "IMG00000488",
            "HTML00000488",
            "TXT00000488",
        ]

    def test_get_reading_order(self, mets_attr_extractor_obj: MetsAttributeExtractor) -> None:
        reading_order = mets_attr_extractor_obj.get_reading_order()
        assert reading_order.get("scanningOrder") == "left-to-right"
        assert reading_order.get("readingOrder") == "left-to-right"
        assert reading_order.get("coverTag") == "follows-reading-order"

    def test_get_unique_features(self, mets_attr_extractor_obj: MetsAttributeExtractor) -> None:
        mets_map = mets_attr_extractor_obj.create_mets_map()

        assert sorted(
            [
                "CHAPTER_START",
                "FIRST_CONTENT_CHAPTER_START",
                "UNTYPICAL_PAGE",
                "FRONT_COVER",
                "IMPLICIT_PAGE_NUMBER",
            ]
        ) == sorted(MetsAttributeExtractor.get_unique_features(mets_map))

    def test_create_mets_entry_logs_the_ht_id_as_a_field(
        self, mets_attr_extractor_obj: MetsAttributeExtractor
    ) -> None:
        with capture_logs() as entries:
            mets_attr_extractor_obj.create_mets_entry("mb.39015078560292")

        for event in ("Creating METS map", "Creating METS entry", "Retrieving document orders"):
            assert_log_entry(entries, event=event, ht_id="mb.39015078560292")

    def test_a_missing_mets_file_is_logged_with_the_ht_id_as_a_field(self, tmp_path: Path) -> None:
        with capture_logs() as entries, pytest.raises(FileNotFoundError):
            extract_fields_from_mets_file("mdp.123", str(tmp_path / "mdp.123"))

        assert_log_entry(
            entries, event="Error generating METS fields", log_level="error", ht_id="mdp.123"
        )
