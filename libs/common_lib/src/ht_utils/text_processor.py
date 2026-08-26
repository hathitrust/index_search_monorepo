from xml.sax.saxutils import quoteattr

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


def string_preparation(doc_content: bytes) -> str:
    """
    Clean up a byte object and convert it to a string efficiently.
    :param doc_content: XML string as bytes
    :return: Processed string
    """

    try:
        str_content = doc_content.decode("utf-8")
        # Remove line breaks and extra spaces
        str_content = str_content.replace("\r", " ").replace("\n", " ")
        return quoteattr(str_content.strip())
    except UnicodeDecodeError as e:
        logger.error(f"File encoding incompatible with UTF-8: {e}")
        raise e


def ensure_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def first_value(value: object) -> str:
    if isinstance(value, (list, tuple)):
        for item in value:
            text = ensure_text(item)
            if text:
                return text
        return ""
    return ensure_text(value)


def list_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [ensure_text(item) for item in value if ensure_text(item)]
    text = ensure_text(value)
    return [text] if text else []
