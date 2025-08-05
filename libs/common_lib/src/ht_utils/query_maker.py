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
    return query

def make_solr_term_query(list_documents: list[str], by_field: str = 'item') -> str:
    """
    Receives a list of ht_id or id and returns a query to retrieve the documents from the Catalog
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

    # Use terms query parser for faster lookup for large sets of IDs, e.g., document_retriever_service
    # The terms query parser in Solr is a highly efficient way to search for multiple exact values
    # in a specific field — great for querying by id or any other exact-match field,
    # especially when you're dealing with large lists.
    query = '{!terms f=ht_id}' + ','.join(list_documents)

    if by_field == 'record':
        query = '{!terms f=id}' + ','.join(list_documents)
    return query

def build_joined_query(query_fields, field_operators):
    defaut_op = "AND"
    joined_query = query_fields[0]
    for i in range(1, len(query_fields)):
        if i - 1 < len(field_operators):  # check if operator at i-1 exists
            op = field_operators[i - 1]
        else:
            op = defaut_op
        joined_query += f" {op} {query_fields[i]}"
    return joined_query

def build_date_filter(date_value, field_facet_mapping):
    start_date, end_date, in_date = date_value.get("start_year"),date_value.get("end_year"),date_value.get("in_year")
    date_range_facet = field_facet_mapping['date_range_facet']
    date_trie_facet = field_facet_mapping['date_trie_facet']

    fq = ""
    if in_date is not None and in_date.strip() != "":
        # During year
        facet = f'{date_range_facet}:"{in_date}"'
        fq = facet

    elif (start_date is not None and start_date.strip() != "") or (end_date is not None and end_date.strip() != ""):
        # in between / After / before dates
        start_date = start_date if start_date and start_date.strip() != "" else "*"
        end_date = end_date if end_date and end_date.strip() != "" else "*"
        fq = f'{date_trie_facet}:[ {start_date} TO {end_date} ]'
    else:
        return ""

    return fq


def build_field_filters(field,values:list|str, field_facet_mapping):
    facet = field_facet_mapping.get(field)
    fq = ""
    if isinstance(values,str):
        return f'{facet}:"{values}"'
    if facet and values:
        facet_value = " OR ".join(values)
        fq = f"{facet}:({facet_value})"

    return fq


def build_fq_query(filter_fields,config_data):
    filters_list = []
    for field,value in filter_fields.items():
        field_fq = ""
        if value:
            if field=="date":
                field_fq = build_date_filter(value,config_data["field_facet_mapping"])
            else:
                field_fq = build_field_filters(field,value,config_data["field_facet_mapping"])
        if field_fq:
            filters_list.append(field_fq)

    return " AND ".join(filters_list)
