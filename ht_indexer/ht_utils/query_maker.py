from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


def make_query(list_documents: list[str], by_field: str = 'item') -> str:
    """
    Receives a list of ht_id and returns a query to retrieve the documents from the Catalog
    Parameters
    ----------
    by_field: str
        Field to be used in the query. If item, the query will be ht_id: item_id
        If record, the query will be ht_id: (item_id1 OR item_id2 OR item_id3)
    ----------
    list_documents: list[str]
        List of ht_id
    Returns
    -------
    str
        Query to retrieve the documents from the Catalog
    """
    query_field = 'ht_id'
    if by_field == 'item':
        query_field = 'ht_id'
    if by_field == 'record':
        query_field = 'id'
    if len(list_documents) == 1:
        query = f"{query_field}:{list_documents[0]}"
    else:
        values = "\" OR \"".join(list_documents)
        values = '"'.join(("", values, ""))
        query = f"{query_field}:({values})"
    logger.info(f"Query to retrieve the documents: {query}")
    return query
