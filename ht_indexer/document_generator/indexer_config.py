MAX_ITEM_IDS = 1000

MYQLS_METADATA = ["coll_id", "ht_heldby", "ht_heldby_brlm", "rights"]

To_CHECK = [
    "ht_cover_tag",
    "ht_page_feature",
    "ht_reading_order",
    "ht_scanning_order",
    "numPages",
    "numChars",
    "charsPerPage",
    "seq",
    "pgnum",
    "type_s",
    "chunk_seq",
    "mainauthor",
    "timestamp",
    "ctrlnum",
    "rptnum",
    "isbn",
    "edition",
    "fullgenre",
    "genre",
    "hlb3Str",
    "hlb3Delimited",
    "enumPublishDate",
    "bothPublishDate",
    "era",
    "fullgeographic",
]

# field catalog : field_full_text
RENAMED_CATALOG_METADATA = {
    "id": "record_no",
    "publishDate": "date",
    "author": "Vauthor",
    "title": "Vtitle",
    "id": "vol_id",
    "ht_id": "id",
}

IDENTICAL_CATALOG_METADATA = [
    # 'id',
    # 'ocr',
    "author",
    "author2",
    # 'date',
    # 'record_no',
    # 'allfields',
    "lccn",
    "sdrnum",
    "oclc",
    "issn",
    "ht_id_display",  # Appear in full-text search schema do we want to keep it?
    "isn_related",
    "callnumber",
    "sudoc",
    "language",
    "language008_full",
    "format",
    "htsource",
    "publisher",
    # 'Vauthor', # eq to author
    # ====Check author fields====
    "author_top",
    "author_rest",
    "authorSort",
    "author_sortkey",
    # ============================
    # ====Check title fields====
    "vtitle",
    "title_c",
    "title_sortkey",
    "title_display",
    "title",
    "titleSort",
    # 'Vtitle', is title in Catalog
    "title_ab",
    "title_a",
    "title_top",
    "title_rest",
    # ============================
    # 'volume_enumcron', field obtain using the field ht_id_display
    "series",
    "series2",
    "serialTitle_ab",
    "serialTitle_a",
    "serialTitle",
    "serialTitle_rest",
    "topicStr",
    "publishDate",
    "geographicStr",
    "countryOfPubStr",
]
