from pathlib import Path

import pytest

# relative imports
from document_generator.mets_file_extractor import MetsAttributeExtractor


class TestMETSFileExtractor:
    @pytest.fixture()
    def mets_attr_extractor_obj(self):
        path = f"{Path(__file__).parents[1]}/document_generator_tests/data/mb.39015078560292.mets_test.xml"
        mets_obj = MetsAttributeExtractor(path)
        return mets_obj

    def test_create_mets_map(self, mets_attr_extractor_obj):
        mets_map = mets_attr_extractor_obj.create_mets_map()

        assert (
                mets_map.get("488").get("features") == "CHAPTER_START, IMPLICIT_PAGE_NUMBER"
        )
        assert mets_map.get("488").get("pgnum") is None
        assert mets_map.get("488").get("filename") == [
            "IMG00000488",
            "HTML00000488",
            "TXT00000488",
        ]

    def test_get_reading_order(self, mets_attr_extractor_obj):
        reading_order = mets_attr_extractor_obj.get_reading_order()
        assert reading_order.get("scanningOrder") == "left-to-right"
        assert reading_order.get("readingOrder") == "left-to-right"
        assert reading_order.get("coverTag") == "follows-reading-order"

    def test_get_unique_features(self, mets_attr_extractor_obj):
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
