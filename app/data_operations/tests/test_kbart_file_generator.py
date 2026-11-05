import json
import tempfile
from datetime import date
from pathlib import Path

import pytest
from dotenv import load_dotenv
from kbart_file_generator.kbart_file_generator import KBART_COLUMN_ORDER, KBARTFileGenerator

load_dotenv()


@pytest.mark.integration
def test_kbart_generator_integration() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir)
        file_prefix = f"kbart_umich_{date.today()}"

        (rows, errors) = KBARTFileGenerator(
            inst_id="umich", output_path=output_path, batch_size=1000
        ).generate_kbart_export()
        # Actual rows: 1000
        assert rows > 1000
        assert errors == 0

        assert (output_path / f"{file_prefix}.tsv").exists()
        assert (output_path / f"{file_prefix}.metadata.json").exists()

        with open(output_path / f"{file_prefix}.metadata.json") as json_fh:
            data = json.load(json_fh)
            assert data["inst_id"] == "umich"
            assert data["written_rows"] == rows
            assert data["skipped_rows"] == errors

        with open(output_path / f"{file_prefix}.tsv") as tsv_fh:
            header = tsv_fh.readline()
            assert header.startswith("publication_title\t")
            assert len(tsv_fh.readlines()) == rows


def test_build_kbart_row_maps_solr_fields_to_expected_columns_for_non_english() -> None:

    row = KBARTFileGenerator.build_kbart_row(
        {
            "id": "006288731",
            "format": ["Book"],
            "oclc": ["148105100"],
            "mainauthor": ["Murasaki Shikibu, b. 978?", "紫式部, b. 978?"],
            "title": ["Genji monogatari kogetsu shō"],
            "vtitle": "源氏物語湖月抄",
            "title_display": "Genji monogatari kogetsu shō / [Murasaki Shikibu gencho] Kitamura Kigin cho (源氏物語湖月抄 / [紫式部原著] ; 北村季吟著)",
            "display_date": "1926",
            "publisher": ["Bunken Shoin,", "文献書院,"],
            "ht_id_display": [
                "uc1.b3402480|20260816|v. 1|1929|1920-1929|||Genji monogatari kogetsu shō / [Murasaki Shikibu gencho] Kitamura Kigin cho (源氏物語湖月抄 / [紫式部原著] ; 北村季吟著), v. 1",
                "uc1.b3402481|20260816|v. 2|1929|1920-1929|||Genji monogatari kogetsu shō / [Murasaki Shikibu gencho] Kitamura Kigin cho (源氏物語湖月抄 / [紫式部原著] ; 北村季吟著), v. 2",
                "uc1.b3402482|20260811|v. 3|1929|1920-1929|||Genji monogatari kogetsu shō / [Murasaki Shikibu gencho] Kitamura Kigin cho (源氏物語湖月抄 / [紫式部原著] ; 北村季吟著), v. 3",
                "uc1.b3402483|20260816|v. 4|1929|1920-1929|||Genji monogatari kogetsu shō / [Murasaki Shikibu gencho] Kitamura Kigin cho (源氏物語湖月抄 / [紫式部原著] ; 北村季吟著), v. 4",
                "uc1.b3402484|20250117|v. 5|1929|1920-1929|||Genji monogatari kogetsu shō / [Murasaki Shikibu gencho] Kitamura Kigin cho (源氏物語湖月抄 / [紫式部原著] ; 北村季吟著), v. 5",
                "uc1.b3402485|20260810|v. 6|1929|1920-1929|||Genji monogatari kogetsu shō / [Murasaki Shikibu gencho] Kitamura Kigin cho (源氏物語湖月抄 / [紫式部原著] ; 北村季吟著), v. 6",
                "uc1.b3402514|20260810|v. 7|1929|1920-1929|||Genji monogatari kogetsu shō / [Murasaki Shikibu gencho] Kitamura Kigin cho (源氏物語湖月抄 / [紫式部原著] ; 北村季吟著), v. 7",
            ],
        }
    )

    assert list(row) == KBART_COLUMN_ORDER
    assert row == {
        "publication_title": "Genji monogatari kogetsu shō",
        "alternate_publication_title": "源氏物語湖月抄",
        "alternate_title_type": "parallel",
        "print_identifier": "",
        "online_identifier": "",
        "date_first_issue_online": "",
        "num_first_vol_online": "",
        "num_first_issue_online": "",
        "date_last_issue_online": "",
        "num_last_vol_online": "",
        "num_last_issue_online": "",
        "title_url": "https://catalog.hathitrust.org/Record/6288731",
        "contributor": "Murasaki Shikibu, b. 978?",
        "contributor_type": "author",
        "title_id": "6288731",
        "embargo_info": "",
        "coverage_depth": "full",
        "notes": "Access is variable and dependent on resource sharing participation",
        "publisher_name": "Bunken Shoin, 文献書院",
        "publication_type": "monograph",
        "content_type": "text",
        "date_monograph_published_print": "1926",
        "date_monograph_published_online": "",
        "monograph_volume": "",
        "monograph_edition": "",
        "duration": "",
        "parent_publication_title_id": "",
        "preceding_publication_title_id": "",
        "access_type": "M",
        "oclc": "148105100",
    }


def test_build_kbart_row_maps_solr_fields_to_expected_columns_for_monograph_with_edition() -> None:
    row = KBARTFileGenerator.build_kbart_row(
        {
            "id": "000631817",
            "format": ["Book"],
            "oclc": ["13759846"],
            "isbn": ["9780394536392", "0394536398"],
            "mainauthor": ["Choate, Pat."],
            "title": ["The high-flex society : shaping America's economic future"],
            "title_display": "The high-flex society : shaping America's economic future / by Pat Choate, and J.K. Linger",
            "display_date": "1986",
            "publisher": ["Knopf,"],
            "edition": ["1st ed."],
            "ht_id_display": [
                "uc1.b4397043|20250226||1986|1980-1989|||The high-flex society : shaping America's economic future / by Pat Choate, and J.K. Linger",
                "mdp.39015018649148|20261004||1986|1980-1989|||The high-flex society : shaping America's economic future / by Pat Choate, and J.K. Linger",
            ],
        }
    )

    assert list(row) == KBART_COLUMN_ORDER
    assert row == {
        "publication_title": "The high-flex society : shaping America's economic future / by Pat Choate, and J.K. Linger",
        "alternate_publication_title": "",
        "alternate_title_type": "",
        "print_identifier": "9780394536392",
        "online_identifier": "",
        "date_first_issue_online": "",
        "num_first_vol_online": "",
        "num_first_issue_online": "",
        "date_last_issue_online": "",
        "num_last_vol_online": "",
        "num_last_issue_online": "",
        "title_url": "https://catalog.hathitrust.org/Record/631817",
        "contributor": "Choate, Pat.",
        "contributor_type": "author",
        "title_id": "631817",
        "embargo_info": "",
        "coverage_depth": "full",
        "notes": "Access is variable and dependent on resource sharing participation",
        "publisher_name": "Knopf",
        "publication_type": "monograph",
        "content_type": "text",
        "date_monograph_published_print": "1986",
        "date_monograph_published_online": "",
        "monograph_volume": "",
        "monograph_edition": "1st ed.",
        "duration": "",
        "parent_publication_title_id": "",
        "preceding_publication_title_id": "",
        "access_type": "M",
        "oclc": "13759846",
    }


def test_build_kbart_row_maps_solr_fields_to_expected_columns_for_monograph() -> None:
    row = KBARTFileGenerator.build_kbart_row(
        {
            "id": "000000240",
            "format": ["Book"],
            "oclc": ["22703"],
            "isbn": ["9780822931782", "0822931788"],
            "mainauthor": ["Parrini, Carl P."],
            "title": ["Heir to empire: United States economic diplomacy, 1916-1923"],
            "title_display": "Heir to empire: United States economic diplomacy, 1916-1923 [by] Carl P. Parrini",
            "display_date": "1969",
            "publisher": ["University of Pittsburg Press"],
            "ht_id_display": [
                "uc1.b4912432|20250320||1969|1960-1969|||Heir to empire: United States economic diplomacy, 1916-1923 [by] Carl P. Parrini"
            ],
        }
    )
    assert list(row) == KBART_COLUMN_ORDER
    assert row == {
        "publication_title": "Heir to empire: United States economic diplomacy, 1916-1923 [by] Carl P. Parrini",
        "alternate_publication_title": "",
        "alternate_title_type": "",
        "print_identifier": "9780822931782",
        "online_identifier": "",
        "date_first_issue_online": "",
        "num_first_vol_online": "",
        "num_first_issue_online": "",
        "date_last_issue_online": "",
        "num_last_vol_online": "",
        "num_last_issue_online": "",
        "title_url": "https://catalog.hathitrust.org/Record/240",
        "contributor": "Parrini, Carl P.",
        "contributor_type": "author",
        "title_id": "240",
        "embargo_info": "",
        "coverage_depth": "full",
        "notes": "Access is variable and dependent on resource sharing participation",
        "publisher_name": "University of Pittsburg Press",
        "publication_type": "monograph",
        "content_type": "text",
        "date_monograph_published_print": "1969",
        "date_monograph_published_online": "",
        "monograph_volume": "",
        "monograph_edition": "",
        "duration": "",
        "parent_publication_title_id": "",
        "preceding_publication_title_id": "",
        "access_type": "M",
        "oclc": "22703",
    }


def test_build_kbart_row_maps_solr_fields_to_expected_columns_for_serial() -> None:
    row = KBARTFileGenerator.build_kbart_row(
        # from: curl "$CATALOG_SOLR_RO_URL/query?q=id:000045279&fl=id,title_display,title,vtitle,isbn,issn,mainauthor,publisher,oclc,ht_id_display,format,edition&wt=python"
        {
            "id": "000045279",
            "format": ["Serial", "Journal"],
            "oclc": ["8731707"],
            "issn": ["0734-0664"],
            "title": ["Gerodontology"],
            "title_display": "Gerodontology",
            "display_date": "1982",
            "publisher": ["Beech Hill Enterprises,"],
            "ht_id_display": [
                "uc1.31158011383618|20130809|v.02 yr.1983|1983|1980-1989|||Gerodontology, v.02 yr.1983",
                "uc1.31158011385407|20130809|v.04 yr.1985|1985|1980-1989|||Gerodontology, v.04 yr.1985",
                "uc1.31158012088026|20130809|v.05 yr.1986|1986|1980-1989|||Gerodontology, v.05 yr.1986",
                "uc1.l0051309250|20130809|v.06 yr.1987|1987|1980-1989|||Gerodontology, v.06 yr.1987",
                "uc1.l0061540274|20130809|v.07 yr.1988|1988|1980-1989|||Gerodontology, v.07 yr.1988",
                "uc1.l0061132213|20130809|v.08 yr.1989|1989|1980-1989|||Gerodontology, v.08 yr.1989",
                "uc1.l0067454678|20130809|v.09 yr.1990|1990|1990-1999|||Gerodontology, v.09 yr.1990",
                "uc1.l0078148681|20130809|v.10 no.1-2 yr.1993|1993|1990-1999|||Gerodontology, v.10 no.1-2 yr.1993",
            ],
        }
    )

    assert list(row) == KBART_COLUMN_ORDER
    assert row == {
        "publication_title": "Gerodontology",
        "alternate_publication_title": "",
        "alternate_title_type": "",
        "print_identifier": "0734-0664",
        "online_identifier": "",
        "date_first_issue_online": "1983",
        "num_first_vol_online": "",
        "num_first_issue_online": "",
        "date_last_issue_online": "1993",
        "num_last_vol_online": "",
        "num_last_issue_online": "",
        "title_url": "https://catalog.hathitrust.org/Record/45279",
        "contributor": "",
        "contributor_type": "",
        "title_id": "45279",
        "embargo_info": "",
        "coverage_depth": "full",
        "notes": "Access is variable and dependent on resource sharing participation",
        "publisher_name": "Beech Hill Enterprises",
        "publication_type": "serial",
        "content_type": "text",
        "date_monograph_published_print": "",
        "date_monograph_published_online": "",
        "monograph_volume": "",
        "monograph_edition": "",
        "duration": "",
        "parent_publication_title_id": "",
        "preceding_publication_title_id": "",
        "access_type": "M",
        "oclc": "8731707",
    }


def test_extract_dates_gets_min_and_max() -> None:
    assert KBARTFileGenerator.extract_dates(
        ["test.1|||1936||||", "test.2|||1937||||", "test.3|||1938||||"]
    ) == ("1936", "1938")
    pass


def test_extract_dates_ignores_empty() -> None:
    assert KBARTFileGenerator.extract_dates(
        ["test.1|||||||", "test.2|||1980||||", "test.3|||1990||||"]
    ) == ("1980", "1990")


def test_extract_dates_ignores_9999() -> None:
    assert KBARTFileGenerator.extract_dates(
        ["test.1|||9999||||", "test.2|||1980||||", "test.3|||1990||||"]
    ) == ("1980", "1990")


def test_extract_dates_ignores_malformed() -> None:
    assert KBARTFileGenerator.extract_dates(
        ["test.1|||notadate||||", "test.2|||1980||||", "test.3|||1990||||"]
    ) == ("1980", "1990")


def test_extract_dates_ignores_non_four_digit() -> None:
    assert KBARTFileGenerator.extract_dates(
        ["test.1|||999||||", "test.2|||1980||||", "test.3|||20001||||"]
    ) == ("1980", "1980")


def test_extract_dates_returns_same_for_min_max_with_one() -> None:
    assert KBARTFileGenerator.extract_dates(
        [
            "test.1|||1872||||",
        ]
    ) == ("1872", "1872")


def test_extract_dates_returns_empty_string_without_good_dates() -> None:
    assert KBARTFileGenerator.extract_dates(
        [
            "test.1|||||||",
            "test.2|||9999||||",
            "test.3|||baddate||||",
        ]
    ) == ("", "")
