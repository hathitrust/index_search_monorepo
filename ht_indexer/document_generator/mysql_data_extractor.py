from ht_utils.ht_mysql import HtMysql
from ht_utils.ht_logger import get_ht_logger
import indexer_config

logger = get_ht_logger(name=__name__)


def create_coll_id_field(coll_id_result, large_coll_id_result) -> dict:
    if len(coll_id_result) > 0:
        list_coll_ids = [coll_id.get("MColl_ID") for coll_id in coll_id_result]
        list_large_coll_id = [
            coll_id.get("MColl_ID") for coll_id in large_coll_id_result
        ]

        return {"coll_id": list(set(list_coll_ids) & set(list_large_coll_id))}
    else:
        return {"coll_id": [0]}


def create_ht_heldby_brlm_field(heldby_brlm) -> dict:
    list_brl_members = [member_id.get("member_id") for member_id in heldby_brlm]
    return {"ht_heldby_brlm": list_brl_members}


def create_ht_heldby_field(heldby_brlm) -> dict:
    list_brl_members = [member_id.get("member_id") for member_id in heldby_brlm]
    return {"ht_heldby": list_brl_members}


class MysqlMetadataExtractor:
    def __init__(self, db_conn: HtMysql):
        self.mysql_obj = db_conn

    def get_results_query(self, query: str) -> list:

        results = self.mysql_obj.query_mysql(query=query)

        list_docs = []
        for row in results:
            doc = {}
            for name, value in zip(self.mysql_obj.cursor.description, row):
                doc.update({name[0]: value})
            list_docs.append(doc)

        return list_docs

    def add_large_coll_id_field(self, doc_id: str) -> [dict, dict]:
        """
        Get the list of coll_ids for the given id that are large so those
        coll_ids can be added as <coll_id> fields of the Solr doc.

        So, if sync-i found an id to have, erroneously, a *small* coll_id
        field in its Solr doc and queued it for re-indexing, this routine
        would create a Solr doc not containing that coll_id among its
        <coll_id> fields.
        """

        query_coll_item = (
            f'SELECT MColl_ID FROM mb_coll_item WHERE extern_item_id="{doc_id}"'
        )

        query_large_coll = (
            f"SELECT MColl_ID FROM mb_collection WHERE num_items>{indexer_config.MAX_ITEM_IDS}"
        )

        coll_id_entry = self.mysql_obj.query_mysql(query_coll_item)
        coll_id_large_entry = self.mysql_obj.query_mysql(query_large_coll)

        return coll_id_entry, coll_id_large_entry

    def add_rights_field(self, doc_id) -> list[tuple]:
        namespace, _id = doc_id.split(".")
        query = (
            f'SELECT * FROM rights_current WHERE namespace="{namespace}" AND id="{_id}"'
        )
        return self.mysql_obj.query_mysql(query)

    def add_ht_heldby_field(self, doc_id) -> list[tuple]:
        query = (
            f'SELECT member_id FROM holdings_htitem_htmember WHERE volume_id="{doc_id}"'
        )
        # ht_heldby is a list of institutions
        return self.mysql_obj.query_mysql(query)

    def add_heldby_brlm_field(self, doc_id) -> list[tuple]:
        query = f'SELECT member_id FROM holdings_htitem_htmember WHERE volume_id="{doc_id}" AND access_count > 0'

        return self.mysql_obj.query_mysql(query)

    def retrieve_mysql_data(self, doc_id):
        entry = {}
        logger.info(f"Retrieving data from MySql {doc_id}")

        doc_rights = self.add_rights_field(doc_id)

        # Only one element
        if len(doc_rights) == 1:
            entry.update({"rights": doc_rights[0].get("attr")})

        # It is a list of members, if the query result is empty the field does not appear in Solr index
        ht_heldby = self.add_ht_heldby_field(doc_id)
        if len(ht_heldby) > 0:
            entry.update(create_ht_heldby_field(ht_heldby))

        # It is a list of members, if the query result is empty the field does not appear in Solr index
        heldby_brlm = self.add_heldby_brlm_field(doc_id)

        if len(heldby_brlm) > 0:
            entry.update(create_ht_heldby_brlm_field(heldby_brlm))

        # It is a list of coll_id, if the query result is empty, the value of this field in Solr index will be [0]
        coll_id_result, large_coll_id_result = self.add_large_coll_id_field(doc_id)
        entry.update(create_coll_id_field(coll_id_result, large_coll_id_result))

        return entry
