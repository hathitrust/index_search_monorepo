from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

# The standard list: + - && || ! ( ) { } [ ] ^ " ~ * ? : \ /
# For the one-character reserved symbols, use `maketrans` as it is efficient.
# For `&&` and `||` we replace them explicitly since `maketrans` does not accept
# keys longer than one character.
SOLR_RESERVED_CHARACTER_TABLE = str.maketrans(
    {
        "+": "\\+",
        "-": "\\-",
        "!": "\\!",
        "(": "\\(",
        ")": "\\)",
        "{": "\\{",
        "}": "\\}",
        "[": "\\[",
        "]": "\\]",
        "^": "\\^",
        '"': '\\"',
        "~": "\\~",
        "*": "\\*",
        "?": "\\?",
        ":": "\\:",
        "\\": "\\\\",
        "/": "\\/",
    }
)


def make_query(list_documents: list[str], by_field: str = "item") -> str:
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
    list_documents = [_escape_solr_term(doc) for doc in list_documents]
    query_field = "ht_id"
    if by_field == "item":
        query_field = "ht_id"
    if by_field == "record":
        query_field = "id"
    if len(list_documents) == 1:
        query = f"{query_field}:{list_documents[0]}"
    else:
        values = '" OR "'.join(list_documents)
        values = '"'.join(("", values, ""))
        query = f"{query_field}:({values})"
    return query


def _escape_solr_term(term: str) -> str:
    """
    Escape each of the standard Solr reserved characters,
    special-casing the two-character `&&` and `||` which are
    incompatible with Python's`maketrans`.
    """
    # Note: the Solr docs are ambiguous as to whether both `&`/`|` characters
    # need to be escaped but it seems least surprising to assume so.
    # Doing so handles the extreme edge case of term = "&&&" (the third ampersand
    # is unescaped and Solr should treat it like a literal).
    term = term.translate(SOLR_RESERVED_CHARACTER_TABLE)
    term = term.replace("&&", "\\&\\&")
    return term.replace("||", "\\|\\|")


def make_solr_term_query(list_documents: list[str], by_field: str = "item") -> str:
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

    # We can be quite confident that space will never be allowed in ht_ids,
    # so use it as a delimiter rather than the default comma (which though not attested
    # seems not quite as unlikely to occur in the wild).
    field = "id" if by_field == "record" else "ht_id"
    return f'{{!terms f={field} separator=" "}}' + " ".join(list_documents)
