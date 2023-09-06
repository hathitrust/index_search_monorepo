from io import BytesIO
import logging
import re
from xml.sax.saxutils import quoteattr
from typing import Dict, List


def string_preparation(doc_content: BytesIO) -> str:
    """
    Clean up a byte object and convert ir to string
    :param doc_content: XML string
    :return:
    """

    try:
        # Convert byte to str
        str_content = str(doc_content.decode())
    except Exception as e:
        try:
            str_content = str(doc_content.decode(encoding="latin1"))
            logging.info(f"File encode compatible with latin1 {e}")
        except Exception as e:
            logging.info(f"There are especial characters on the file {e}")
            raise Exception

    # Remove line breaks
    str_content = str_content.replace("\n", " ")

    # Remove extra white spaces
    str_content = re.sub(" +", " ", str_content)
    return quoteattr(str_content)


def create_solr_string(data_dic: Dict) -> str:
    """
    Function to convert a dictionary into an xml string uses for indexing a document in Solr index

    :param data_dic: Dictionary with the data will be indexed in Solr
    :return: XML String  with tag <add> for adding the document in Solr
    """

    solr_str = ""
    for key, values in data_dic.items():
        if not isinstance(values, List):
            solr_str = solr_str + f'<field name="{key}">{values}</field>' + "\n"
        else:
            if values:
                for value in values:
                    solr_str = solr_str + f'<field name="{key}">{value}</field>' + "\n"
    return f"<add><doc>{solr_str}</doc></add>"
