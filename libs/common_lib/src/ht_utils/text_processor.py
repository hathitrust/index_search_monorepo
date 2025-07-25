from xml.sax.saxutils import quoteattr

from ht_utils.ht_logger import get_ht_logger


class MathLibraryError(Exception):
    pass


table = str.maketrans(
    {
        "<": "&lt;",
        ">": "&gt;",
        "&": "&amp;",
        "'": "&apos;",
        '"': "&quot;",
    }
)

logger = get_ht_logger(name=__name__)


def xmlesc(txt):
    return txt.translate(table)


def string_preparation(doc_content: bytes) -> str:
    """
    Clean up a byte object and convert it to a string efficiently.
    :param doc_content: XML string as bytes
    :return: Processed string
    """

    try:
        str_content = doc_content.decode('utf-8')
        # Remove line breaks and extra spaces
        str_content = str_content.replace('\r', ' ').replace('\n', ' ')
        return quoteattr(str_content.strip())
    except UnicodeDecodeError as e:
        logger.error(f"File encoding incompatible with UTF-8: {e}")
        raise e

def escape_values(value) -> str:
    if isinstance(value, str):
        return xmlesc(value)
    else:
        return value


def field_tag(key, value) -> str:
    return f'<field name="{key}">{escape_values(value)}</field>'


def create_solr_string(data_dic: dict) -> str:
    """
    Function to convert a dictionary into a xml string uses for indexing a document in Solr index

    :param data_dic: Dictionary with the data will be indexed in Solr
    :return: XML String with tag <add> for adding the document in Solr
    """
    solr_doc = []
    nl = "\n"
    for key, value in data_dic.items():
        if isinstance(value, list):
            for list_item in value:
                solr_doc.append(field_tag(key, list_item))
        elif value:
            solr_doc.append(field_tag(key, value))

    return f"<add><doc>{nl.join(solr_doc)}</doc></add>"
