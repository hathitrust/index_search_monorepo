from pathlib import Path

from ht_utils.ht_utils import find_sdr1_obj

MAX_ITEM_IDS = 1000

DOCUMENT_LOCAL_PATH = "/tmp/"

# Status values for the fulltext_item_processing_status table (columns: status,
# retriever_status, generator_status, indexer_status).
# Values must match the ENUM definition in ht_indexer_monitoring.ht_indexer_tracktable.
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_FAILED = "failed"
STATUS_COMPLETED = "completed"
STATUS_REQUEUED = "requeued"


# Look for the sdr1 obj folder in the root of the container
# and if it is not found, use the default path
def get_local_document_folder() -> Path | str:
    """
    Returns the local document folder
    :return: str
    """

    try:
        return find_sdr1_obj()
    except FileNotFoundError:
        return f"{Path(__file__).parents[1]}/sdr1/obj"


# field_full_text : field catalog
RENAMED_CATALOG_METADATA = {
    "record_no": "id",
    "date": "publishDate",
    "Vauthor": "author",
    "Vtitle": "title",
}

IDENTICAL_CATALOG_METADATA = [
    "author",
    "author2",
    "lccn",
    "sdrnum",
    "rptnum",
    "oclc",
    "issn",
    "isbn",
    "edition",
    # "ht_id_display",  # Appear in full-text search schema do we want to keep it?
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
    "mainauthor",  # This is an optional field
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
    "genre",
    "era",
    "fullrecord",
]
