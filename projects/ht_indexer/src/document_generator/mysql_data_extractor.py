from catalog_metadata.ht_indexer_config import MAX_ITEM_IDS
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_mysql import HtMysql

logger = get_ht_logger(name=__name__)

def create_coll_id_field(large_coll_id_result: dict) -> dict:
    if len(large_coll_id_result) > 0:
        # Obtain the list with the unique coll_id from the result
        return {"coll_id": list(set([item.get("MColl_ID") for item in large_coll_id_result]))}
    else:
        return {"coll_id": [0]}


def create_ht_heldby_brlm_field(heldby_brlm: list[tuple]) -> dict:
    list_brl_members = [member_id.get("member_id") for member_id in heldby_brlm]
    return {"ht_heldby_brlm": list_brl_members}


def create_ht_heldby_field(heldby_brlm: list[tuple]) -> dict:
    list_brl_members = [member_id.get("member_id") for member_id in heldby_brlm]
    return {"ht_heldby": list_brl_members}


def extract_namespace_and_id(document_id: str):
    """
    Extracts the namespace and the id from a given document id string.
    The namespace is defined as the characters before the first period.
    The id is the remainder of the string after the first period.

    :param document_id: The document id string to extract from.
    :return: A tuple containing the namespace and the id.
    """
    parts = document_id.split(".", 1)  # Split at the first period only
    namespace = parts[0] if parts else None
    ht_id = parts[1] if len(parts) > 1 else None
    return namespace, ht_id


class MysqlMetadataExtractor:
    def __init__(self, db_conn: HtMysql):
        self.mysql_obj = db_conn

    def add_large_coll_id_field(self, doc_id: str) -> [dict]:
        """
        Get the list of coll_ids for the given id that are large so those
        coll_ids can be added as <coll_id> fields of the Solr doc.

        So, if sync-i found an id to have, erroneously, a *small* coll_id
        field in its Solr doc and queued it for re-indexing, this routine
        would create a Solr doc not containing that coll_id among its
        <coll_id> fields.
        """

        query_item_in_large_coll = (f'SELECT mb_item.MColl_ID '
                                    f'FROM mb_coll_item mb_item, mb_collection mb_coll '
                                    f'WHERE mb_item.extern_item_id="{doc_id}" '
                                    f'AND mb_coll.num_items > {MAX_ITEM_IDS} ')

        logger.info(f"MySQL query: {query_item_in_large_coll}")
        large_collection_id = self.mysql_obj.query_mysql(query_item_in_large_coll)

        return large_collection_id

    def add_rights_field(self, doc_id) -> list[tuple]:

        namespace, _id = extract_namespace_and_id(doc_id)

        query = (
            f'SELECT * FROM rights_current WHERE namespace="{namespace}" AND id="{_id}"'
        )
        logger.info(f"MySQL query: {query}")
        return self.mysql_obj.query_mysql(query)

    def add_ht_heldby_field(self, doc_id) -> list[tuple]:
        query = (
            f'SELECT member_id FROM holdings_htitem_htmember WHERE volume_id="{doc_id}"'
        )

        logger.info(f"MySQL query: {query}")
        # ht_heldby is a list of institutions
        return self.mysql_obj.query_mysql(query)

    def add_heldby_brlm_field(self, doc_id) -> list[tuple]:
        query = f'SELECT member_id FROM holdings_htitem_htmember WHERE volume_id="{doc_id}" AND access_count > 0'

        logger.info(f"MySQL query: {query}")
        return self.mysql_obj.query_mysql(query)

    def retrieve_mysql_data(self, doc_id):
        entry = {}
        logger.info(f"Retrieving data from MySql {doc_id}")

        doc_rights = self.add_rights_field(doc_id)

        # Only one element
        if len(doc_rights) == 1:
            entry.update({"rights": doc_rights[0].get("attr")})

        # It is a list of members, if the query result is empty, the field does not appear in Solr index
        ht_heldby = self.add_ht_heldby_field(doc_id)
        if len(ht_heldby) > 0:
            entry.update(create_ht_heldby_field(ht_heldby))

        # It is a list of members, if the query result is empty, the field does not appear in Solr index
        heldby_brlm = self.add_heldby_brlm_field(doc_id)

        if len(heldby_brlm) > 0:
            entry.update(create_ht_heldby_brlm_field(heldby_brlm))

        # It is a list of coll_id, if the query result is empty, the value of this field in Solr index will be [0]
        large_coll_id_result = self.add_large_coll_id_field(doc_id)
        entry.update(create_coll_id_field(large_coll_id_result))

        return entry
