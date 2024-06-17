import re
from typing import Dict, List
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
    Clean up a byte object and convert it to string
    :param doc_content: XML string
    :return:
    """

    # Make sure you will be able to convert the byte the full text
    try:
        # Convert byte to str
        str_content = str(doc_content.decode())
    except UnicodeDecodeError as e:
        logger.error(f"File encode incompatible with UTF-8 {e}")
        raise e

        # Remove line breaks
    str_content = str_content.replace("\n", " ")

    # Remove extra white spaces
    str_content = re.sub(" +", " ", str_content)
    return quoteattr(str_content)


def escape_values(value) -> str:
    if isinstance(value, str):
        return xmlesc(value)
    else:
        return value


def field_tag(key, value) -> str:
    return f'<field name="{key}">{escape_values(value)}</field>'


def create_solr_string(data_dic: Dict) -> str:
    """
    Function to convert a dictionary into a xml string uses for indexing a document in Solr index

    :param data_dic: Dictionary with the data will be indexed in Solr
    :return: XML String with tag <add> for adding the document in Solr
    """
    solr_doc = []
    nl = "\n"
    for key, value in data_dic.items():
        if isinstance(value, List):
            for list_item in value:
                solr_doc.append(field_tag(key, list_item))
        elif value:
            solr_doc.append(field_tag(key, value))

    return f"<add><doc>{nl.join(solr_doc)}</doc></add>"
